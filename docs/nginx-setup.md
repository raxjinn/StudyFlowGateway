# Nginx Reverse Proxy Setup Guide

This guide covers setting up Nginx as a reverse proxy for the DICOM Gateway with HTTPS, modern security settings, and HSTS.

## Overview

Nginx serves as a reverse proxy for the DICOM Gateway, providing:
- HTTPS termination
- Static file serving for the Vue.js frontend
- API request proxying to the FastAPI backend
- Rate limiting and security headers
- Load balancing (if multiple backend instances)

## Prerequisites

1. **Nginx installed**:
   ```bash
   # RHEL/Alma/Rocky Linux 8+
   sudo dnf install nginx
   
   # Ubuntu/Debian
   sudo apt-get install nginx
   ```

2. **TLS certificates** configured (see [TLS Setup Guide](tls-setup.md))
3. **Firewall configured** to allow HTTP (80) and HTTPS (443)

## Installation Steps

### 1. Install Nginx

```bash
# RHEL/Alma/Rocky Linux 8+
sudo dnf install nginx

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install nginx
```

### 2. Copy Configuration Files

```bash
# Copy DICOM Gateway configuration
sudo cp nginx/dicom-gateway.conf /etc/nginx/conf.d/dicom-gateway.conf

# Edit configuration and update server_name
sudo nano /etc/nginx/conf.d/dicom-gateway.conf
```

**Important**: Update the `server_name` directive with your domain name:
```nginx
server_name gateway.example.com;
```

### 3. Create Frontend Directory

```bash
# Create directory for Vue.js frontend
sudo mkdir -p /var/www/dicom-gateway
sudo chown -R nginx:nginx /var/www/dicom-gateway

# Build and copy frontend (see frontend documentation)
# cd frontend && npm run build
# sudo cp -r dist/* /var/www/dicom-gateway/
```

### 4. Configure SSL Certificates

Ensure certificates are in place:
```bash
sudo ls -la /etc/dicom-gw/tls/
# Should show: cert.pem, key.pem (and optionally ca.pem)
```

### 5. Test Configuration

```bash
# Test Nginx configuration
sudo nginx -t

# If successful, reload Nginx
sudo systemctl reload nginx
```

### 6. Enable and Start Nginx

```bash
# Enable Nginx to start on boot
sudo systemctl enable nginx

# Start Nginx
sudo systemctl start nginx

# Check status
sudo systemctl status nginx
```

### 7. Configure Firewall

```bash
# RHEL/Alma/Rocky Linux 8+ (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# Or using iptables
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo service iptables save
```

## Configuration Details

### SSL/TLS Configuration

The configuration uses modern TLS settings:
- **TLS 1.2 and 1.3** only
- **Strong cipher suites** (ECDHE, DHE with forward secrecy)
- **OCSP stapling** (if CA certificate is configured)
- **HSTS** (HTTP Strict Transport Security) with 1-year max-age
- **Session tickets disabled** for better security

### Security Headers

The following security headers are set:
- `Strict-Transport-Security`: HSTS with includeSubDomains and preload
- `X-Frame-Options`: DENY (prevents clickjacking)
- `X-Content-Type-Options`: nosniff (prevents MIME sniffing)
- `X-XSS-Protection`: 1; mode=block
- `Referrer-Policy`: strict-origin-when-cross-origin
- `Content-Security-Policy`: Restrictive CSP for XSS protection

### Rate Limiting

Two rate limiting zones are configured:
1. **API Limit**: 100 requests/second per IP (burst: 20)
2. **Login Limit**: 5 requests/minute per IP (burst: 3)

### Reverse Proxy Settings

- **Upstream**: Backend FastAPI application on `127.0.0.1:8000`
- **Keep-alive**: 32 connections maintained
- **Timeouts**: 60 seconds for connect, send, and read
- **Headers**: Proper forwarding of client IP and protocol

## Customization

### Multiple Backend Instances (Load Balancing)

Edit `/etc/nginx/conf.d/dicom-gateway.conf`:

```nginx
upstream dicom_gateway_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    
    # Load balancing method (optional)
    # least_conn;  # Use least connections
    # ip_hash;     # Sticky sessions by IP
}
```

### Custom Domain Name

Update `server_name` in both HTTP and HTTPS server blocks:
```nginx
server_name gateway.example.com;
```

### Monitoring Network Access

To allow Prometheus metrics from a monitoring network:
```nginx
location /api/v1/metrics/prometheus {
    allow 127.0.0.1;
    allow ::1;
    allow 10.0.0.0/8;  # Monitoring network
    deny all;
    # ... rest of configuration
}
```

### Custom Log Locations

Update log paths if needed:
```nginx
access_log /var/log/nginx/dicom-gateway-access.log;
error_log /var/log/nginx/dicom-gateway-error.log;
```

## Testing

### Test Configuration Syntax

```bash
sudo nginx -t
```

### Test HTTPS Connection

```bash
# Test SSL certificate
openssl s_client -connect gateway.example.com:443 -servername gateway.example.com

# Test with curl
curl -v https://gateway.example.com/api/v1/health

# Test HSTS header
curl -I https://gateway.example.com | grep -i strict-transport
```

### Test Rate Limiting

```bash
# Test API rate limit (should allow 100 req/s)
for i in {1..150}; do curl -s https://gateway.example.com/api/v1/health > /dev/null; done

# Test login rate limit (should limit after 5 req/min)
for i in {1..10}; do curl -s -X POST https://gateway.example.com/api/v1/auth/login > /dev/null; done
```

## Troubleshooting

### Nginx Won't Start

1. **Check configuration syntax**:
   ```bash
   sudo nginx -t
   ```

2. **Check error logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

3. **Check if port is already in use**:
   ```bash
   sudo netstat -tlnp | grep :80
   sudo netstat -tlnp | grep :443
   ```

### SSL Certificate Errors

1. **Verify certificate files exist**:
   ```bash
   sudo ls -la /etc/dicom-gw/tls/
   ```

2. **Check certificate permissions**:
   ```bash
   sudo ls -l /etc/dicom-gw/tls/cert.pem
   sudo ls -l /etc/dicom-gw/tls/key.pem
   # Cert should be 644, key should be 600
   ```

3. **Test certificate validity**:
   ```bash
   openssl x509 -in /etc/dicom-gw/tls/cert.pem -text -noout
   ```

### 502 Bad Gateway

This usually means Nginx can't connect to the backend:

1. **Check if backend is running**:
   ```bash
   sudo systemctl status dicom-gw-api
   ```

2. **Test backend connection**:
   ```bash
   curl http://127.0.0.1:8000/api/v1/health
   ```

3. **Check backend logs**:
   ```bash
   sudo journalctl -u dicom-gw-api -f
   ```

### Frontend Not Loading

1. **Verify frontend files exist**:
   ```bash
   sudo ls -la /var/www/dicom-gateway/
   ```

2. **Check file permissions**:
   ```bash
   sudo chown -R nginx:nginx /var/www/dicom-gateway
   ```

3. **Check Nginx error logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

## Performance Tuning

### Worker Processes

Set worker processes based on CPU cores:
```nginx
worker_processes auto;  # Automatically detects CPU cores
```

### Connection Limits

Increase if needed:
```nginx
events {
    worker_connections 2048;  # Increase from default 1024
}
```

### Keep-Alive Timeout

Adjust based on your needs:
```nginx
keepalive_timeout 65;
keepalive_requests 100;
```

### Gzip Compression

Already enabled, but can be tuned:
```nginx
gzip_comp_level 6;  # 1-9, higher = more compression but more CPU
```

## Security Checklist

- [ ] SSL certificates configured and valid
- [ ] HSTS header enabled
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] Server tokens disabled
- [ ] Firewall configured (80, 443)
- [ ] Backend only accessible via Nginx (firewall rule)
- [ ] Certificate auto-renewal configured
- [ ] Monitoring/metrics endpoint restricted
- [ ] Logs configured and monitored

## Maintenance

### Reload Configuration

```bash
# Test configuration first
sudo nginx -t

# Reload if test passes
sudo systemctl reload nginx
```

### View Logs

```bash
# Access logs
sudo tail -f /var/log/nginx/dicom-gateway-access.log

# Error logs
sudo tail -f /var/log/nginx/dicom-gateway-error.log
```

### Rotate Logs

Logs are automatically rotated by logrotate. Manual rotation:
```bash
sudo logrotate -f /etc/logrotate.d/nginx
```

## References

- [Nginx Documentation](https://nginx.org/en/docs/)
- [SSL Labs SSL Test](https://www.ssllabs.com/ssltest/) - Test your SSL configuration
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [OWASP Secure Headers](https://owasp.org/www-project-secure-headers/)

