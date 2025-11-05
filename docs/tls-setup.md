# TLS/SSL Setup Guide

This guide covers TLS/SSL certificate setup for the DICOM Gateway, including Let's Encrypt automation and manual certificate upload.

## Overview

The DICOM Gateway supports TLS/SSL encryption for:
- DICOM network connections (C-STORE)
- REST API (when using Nginx reverse proxy)
- Web interface (when using Nginx reverse proxy)

## Let's Encrypt Automatic Provisioning

### Prerequisites

1. **Install certbot**:
   ```bash
   # RHEL/Alma/Rocky Linux 8+
   sudo dnf install certbot
   
   # Ubuntu/Debian
   sudo apt-get install certbot
   ```

2. **Domain name**: You must have a domain name pointing to your server
3. **Port 80 or 443**: Port 80 must be accessible for HTTP-01 challenge (or configure webroot)
4. **Email address**: Valid email for Let's Encrypt notifications

### Provisioning via API

```bash
# Using curl
curl -X POST "https://your-gateway/api/v1/certs/letsencrypt/provision" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "domain=gateway.example.com" \
  -d "email=admin@example.com" \
  -d "staging=false"
```

**Parameters:**
- `domain`: Domain name for the certificate
- `email`: Email address for Let's Encrypt notifications
- `webroot_path`: (Optional) Web root path for HTTP-01 challenge (e.g., `/var/www/html`)
- `staging`: (Optional) Use Let's Encrypt staging environment for testing (default: false)

### Provisioning via Command Line

```bash
# Install certbot if not already installed
sudo dnf install certbot

# Provision certificate (standalone mode - requires port 80 to be free)
sudo certbot certonly --standalone \
  --non-interactive \
  --agree-tos \
  --email admin@example.com \
  -d gateway.example.com

# Or using webroot (if you have a web server running)
sudo certbot certonly --webroot \
  --webroot-path /var/www/html \
  --non-interactive \
  --agree-tos \
  --email admin@example.com \
  -d gateway.example.com
```

### Automatic Renewal

Let's Encrypt certificates expire after 90 days. Set up automatic renewal:

**Option 1: Systemd Timer (Recommended)**

Create a systemd timer service:

```bash
# Create service file
sudo tee /etc/systemd/system/dicom-gw-cert-renew.service <<EOF
[Unit]
Description=Renew DICOM Gateway Let's Encrypt Certificate
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/certbot renew --quiet --no-self-upgrade
ExecStartPost=/usr/bin/systemctl reload nginx
ExecStartPost=/usr/bin/systemctl restart dicom-gw-api
EOF

# Create timer file
sudo tee /etc/systemd/system/dicom-gw-cert-renew.timer <<EOF
[Unit]
Description=Renew DICOM Gateway Certificate Daily
Requires=dicom-gw-cert-renew.service

[Timer]
OnCalendar=daily
RandomizedDelaySec=3600
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start timer
sudo systemctl daemon-reload
sudo systemctl enable dicom-gw-cert-renew.timer
sudo systemctl start dicom-gw-cert-renew.timer

# Check timer status
sudo systemctl status dicom-gw-cert-renew.timer
```

**Option 2: Cron Job**

```bash
# Add to crontab (runs twice daily at random times)
echo "0 0,12 * * * certbot renew --quiet --no-self-upgrade && systemctl reload nginx && systemctl restart dicom-gw-api" | sudo crontab -
```

**Option 3: Via API**

You can also trigger renewal via the API:

```bash
curl -X POST "https://your-gateway/api/v1/certs/letsencrypt/renew" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Manual Certificate Upload

### Upload via API

```bash
curl -X POST "https://your-gateway/api/v1/certs/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "cert_file=@/path/to/certificate.pem" \
  -F "key_file=@/path/to/private-key.pem" \
  -F "ca_file=@/path/to/ca-certificate.pem"
```

### Manual File Copy

1. **Create certificate directory**:
   ```bash
   sudo mkdir -p /etc/dicom-gw/tls
   sudo chmod 750 /etc/dicom-gw/tls
   sudo chown dicom-gw:dicom-gw /etc/dicom-gw/tls
   ```

2. **Copy certificate files**:
   ```bash
   sudo cp certificate.pem /etc/dicom-gw/tls/cert.pem
   sudo cp private-key.pem /etc/dicom-gw/tls/key.pem
   sudo cp ca-certificate.pem /etc/dicom-gw/tls/ca.pem  # Optional
   
   # Set permissions
   sudo chmod 644 /etc/dicom-gw/tls/cert.pem
   sudo chmod 600 /etc/dicom-gw/tls/key.pem
   sudo chmod 644 /etc/dicom-gw/tls/ca.pem  # If present
   sudo chown dicom-gw:dicom-gw /etc/dicom-gw/tls/*
   ```

3. **Reload services**:
   ```bash
   sudo systemctl restart dicom-gw-api
   sudo systemctl reload nginx  # If using Nginx
   ```

## Certificate Information

Check certificate information via API:

```bash
curl -X GET "https://your-gateway/api/v1/certs/info" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response includes:
- Certificate file paths
- Valid from/until dates
- Days until expiry
- Subject and issuer information
- Expiration status

## DICOM TLS Configuration

### Enable TLS for DICOM Connections

1. **Update configuration** (`/etc/dicom-gw/config.yaml`):
   ```yaml
   tls:
     enabled: true
     cert_file: /etc/dicom-gw/tls/cert.pem
     key_file: /etc/dicom-gw/tls/key.pem
     ca_file: /etc/dicom-gw/tls/ca.pem  # Optional
     no_verify: false  # Set to true to skip peer verification (not recommended)
   ```

2. **Configure destinations with TLS**:
   ```yaml
   destinations:
     - name: "Secure_PACS"
       ae_title: "SECURE_PACS"
       host: "pacs.example.com"
       port: 2762  # Common TLS port
       tls_enabled: true
       tls_cert_path: /etc/dicom-gw/tls/cert.pem
       tls_key_path: /etc/dicom-gw/tls/key.pem
       tls_ca_path: /etc/dicom-gw/tls/ca.pem
   ```

3. **Reload configuration**:
   ```bash
   curl -X POST "https://your-gateway/api/v1/config/reload" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

## Testing TLS

### Test Certificate

```bash
# Check certificate validity
openssl x509 -in /etc/dicom-gw/tls/cert.pem -text -noout

# Check certificate expiration
openssl x509 -in /etc/dicom-gw/tls/cert.pem -noout -dates

# Test TLS connection
openssl s_client -connect gateway.example.com:2762 -showcerts
```

### Test DICOM TLS Connection

```bash
# Using dcmtk (if installed)
echoscu -aec YOUR_AE_TITLE -aet GATEWAY -P -tls -xf /etc/dicom-gw/tls/cert.pem \
  --trusted-certificates /etc/dicom-gw/tls/ca.pem \
  gateway.example.com 2762
```

## Troubleshooting

### Certificate Not Found

- Verify certificate files exist: `ls -la /etc/dicom-gw/tls/`
- Check file permissions: `stat /etc/dicom-gw/tls/cert.pem`
- Ensure service user has read access

### Certificate Expired

- Check expiration: `openssl x509 -in /etc/dicom-gw/tls/cert.pem -noout -dates`
- Renew Let's Encrypt certificate (see Automatic Renewal above)
- Or upload new certificate via API

### Let's Encrypt Provisioning Fails

**Common issues:**

1. **Port 80 not accessible**: Use webroot method instead of standalone
2. **Domain not pointing to server**: Verify DNS records
3. **Firewall blocking**: Ensure port 80/443 is open
4. **Rate limits**: Let's Encrypt has rate limits (use staging for testing)

**Check certbot logs:**
```bash
sudo tail -f /var/log/letsencrypt/letsencrypt.log
```

### TLS Connection Fails

1. **Verify certificate and key match**:
   ```bash
   openssl x509 -noout -modulus -in /etc/dicom-gw/tls/cert.pem | openssl md5
   openssl rsa -noout -modulus -in /etc/dicom-gw/tls/key.pem | openssl md5
   ```
   Both should produce the same hash.

2. **Check certificate chain**: Ensure full chain is present (including intermediate certificates)

3. **Verify TLS configuration**: Check that `tls_enabled: true` in configuration

4. **Check logs**: Review application logs for TLS errors

## Security Best Practices

1. **Certificate Storage**: Store certificates in `/etc/dicom-gw/tls/` with restrictive permissions (750 for directory, 600 for keys)

2. **Key Protection**: Private keys should be readable only by the service user

3. **Certificate Rotation**: Renew certificates before expiration (Let's Encrypt: 90 days)

4. **TLS Version**: Use TLS 1.2 or higher (configured in Nginx/application)

5. **Cipher Suites**: Use strong cipher suites (configured in Nginx)

6. **Certificate Pinning**: Consider certificate pinning for critical connections

7. **Monitoring**: Monitor certificate expiration and renewal status

## References

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://eff-certbot.readthedocs.io/)
- [DICOM TLS Specification](https://www.dicomstandard.org/current/)

