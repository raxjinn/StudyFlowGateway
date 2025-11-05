# TLS/SSL Setup Guide

This guide covers setting up TLS/SSL encryption for the DICOM Gateway.

## Overview

The DICOM Gateway supports TLS/SSL in two areas:

1. **Web Interface (HTTPS)**: Nginx reverse proxy with TLS
2. **DICOM Communication**: TLS-encrypted DICOM C-STORE connections

## Web Interface TLS (HTTPS)

### Method 1: Let's Encrypt (Recommended)

Let's Encrypt provides free, automated SSL certificates.

#### Prerequisites

1. **Install certbot**:
   ```bash
   sudo dnf install -y certbot python3-certbot-nginx
   ```

2. **Configure Nginx** (allow HTTP for ACME challenge):
   ```nginx
   # Allow Let's Encrypt ACME challenge
   location /.well-known/acme-challenge/ {
       root /var/www/html;
   }
   ```

#### Provision Certificate

1. **Via API** (recommended):
   ```bash
   curl -X POST https://your-server/api/v1/config/certificates/letsencrypt/provision \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "domain": "gateway.example.com",
       "email": "admin@example.com"
     }'
   ```

2. **Via certbot command**:
   ```bash
   sudo certbot --nginx -d gateway.example.com --email admin@example.com --agree-tos --non-interactive
   ```

3. **Manual certbot**:
   ```bash
   sudo certbot certonly --nginx \
     -d gateway.example.com \
     --email admin@example.com \
     --agree-tos \
     --non-interactive
   ```

#### Configure Nginx

1. **Update Nginx configuration**:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name gateway.example.com;
       
       ssl_certificate /etc/letsencrypt/live/gateway.example.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/gateway.example.com/privkey.pem;
       
       # Modern SSL configuration
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
       ssl_prefer_server_ciphers off;
       ssl_session_cache shared:SSL:10m;
       ssl_session_timeout 10m;
       
       # HSTS
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       
       # Rest of configuration...
   }
   ```

2. **Test and reload**:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

#### Automatic Renewal

Let's Encrypt certificates expire after 90 days. Setup automatic renewal:

1. **Test renewal**:
   ```bash
   sudo certbot renew --dry-run
   ```

2. **Setup cron job** (certbot installs this automatically):
   ```bash
   # Check cron job
   sudo systemctl status certbot-renew.timer
   
   # Enable timer
   sudo systemctl enable certbot-renew.timer
   sudo systemctl start certbot-renew.timer
   ```

3. **Renew via API** (optional):
   ```bash
   curl -X POST https://your-server/api/v1/config/certificates/letsencrypt/renew \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

### Method 2: Manual Certificate

For organizations with internal CAs or commercial certificates:

1. **Upload certificate files**:
   ```bash
   # Copy certificate files
   sudo cp server.crt /etc/nginx/ssl/gateway.crt
   sudo cp server.key /etc/nginx/ssl/gateway.key
   sudo cp ca.crt /etc/nginx/ssl/ca.crt  # Optional
   
   # Set permissions
   sudo chmod 600 /etc/nginx/ssl/gateway.key
   sudo chmod 644 /etc/nginx/ssl/gateway.crt
   ```

2. **Via API**:
   ```bash
   curl -X POST https://your-server/api/v1/config/certificates/upload \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -F "certificate=@server.crt" \
     -F "private_key=@server.key" \
     -F "ca_certificate=@ca.crt"
   ```

3. **Update Nginx configuration**:
   ```nginx
   ssl_certificate /etc/nginx/ssl/gateway.crt;
   ssl_certificate_key /etc/nginx/ssl/gateway.key;
   ssl_trusted_certificate /etc/nginx/ssl/ca.crt;  # Optional
   ```

## DICOM TLS

### Setup DICOM TLS Certificates

1. **Generate certificates** (if needed):
   ```bash
   # Generate private key
   openssl genrsa -out dicom.key 2048
   
   # Generate certificate signing request
   openssl req -new -key dicom.key -out dicom.csr
   
   # Generate self-signed certificate (for testing)
   openssl x509 -req -days 365 -in dicom.csr -signkey dicom.key -out dicom.crt
   ```

2. **Store certificates**:
   ```bash
   sudo mkdir -p /etc/dicom-gw/tls
   sudo cp dicom.crt /etc/dicom-gw/tls/
   sudo cp dicom.key /etc/dicom-gw/tls/
   sudo cp ca.crt /etc/dicom-gw/tls/  # If using CA
   
   sudo chown -R dicom-gw:dicom-gw /etc/dicom-gw/tls
   sudo chmod 600 /etc/dicom-gw/tls/*.key
   sudo chmod 644 /etc/dicom-gw/tls/*.crt
   ```

### Configure Destination TLS

1. **Via API**:
   ```bash
   curl -X PUT https://your-server/api/v1/destinations/{destination_id} \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "tls_enabled": true,
       "tls_cert_path": "/etc/dicom-gw/tls/client.crt",
       "tls_key_path": "/etc/dicom-gw/tls/client.key",
       "tls_ca_path": "/etc/dicom-gw/tls/ca.crt"
     }'
   ```

2. **Via Configuration File**:
   ```yaml
   destinations:
     - name: "Secure PACS"
       ae_title: "SECURE_PACS"
       host: "pacs.example.com"
       port: 104
       tls_enabled: true
       tls_cert_path: "/etc/dicom-gw/tls/client.crt"
       tls_key_path: "/etc/dicom-gw/tls/client.key"
       tls_ca_path: "/etc/dicom-gw/tls/ca.crt"
       tls_no_verify: false
   ```

### Enable TLS for SCP (Receiver)

1. **Update configuration**:
   ```yaml
   dicom:
     tls_enabled: true
     tls_cert_path: "/etc/dicom-gw/tls/server.crt"
     tls_key_path: "/etc/dicom-gw/tls/server.key"
     tls_ca_path: "/etc/dicom-gw/tls/ca.crt"
   ```

2. **Restart SCP service**:
   ```bash
   sudo systemctl restart dicom-gw-scp.service
   ```

## Certificate Management

### View Certificate Information

```bash
# Check certificate details
openssl x509 -in /etc/letsencrypt/live/gateway.example.com/fullchain.pem -text -noout

# Check expiration
openssl x509 -in /etc/letsencrypt/live/gateway.example.com/fullchain.pem -noout -dates

# Check certificate chain
openssl s_client -connect gateway.example.com:443 -showcerts
```

### Certificate Validation

```bash
# Test SSL configuration
openssl s_client -connect gateway.example.com:443

# Test with SSL Labs (online)
# https://www.ssllabs.com/ssltest/analyze.html?d=gateway.example.com

# Check certificate chain
openssl verify -CAfile ca.crt server.crt
```

## Security Best Practices

### TLS Configuration

1. **Use modern protocols**: TLS 1.2 and TLS 1.3 only
2. **Strong ciphers**: Use GCM ciphers
3. **HSTS**: Enable HTTP Strict Transport Security
4. **OCSP Stapling**: Enable for better performance
5. **Certificate Transparency**: Monitor certificate issuance

### Nginx SSL Configuration

```nginx
# Modern SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets off;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/letsencrypt/live/gateway.example.com/chain.pem;

# HSTS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

### Certificate Security

1. **Private key protection**:
   - Store keys with 600 permissions
   - Use separate keys for different services
   - Never commit keys to version control

2. **Certificate rotation**:
   - Renew Let's Encrypt certificates before expiration
   - Rotate certificates annually (commercial)
   - Monitor certificate expiration

3. **Certificate revocation**:
   - Monitor certificate revocation lists (CRL)
   - Enable OCSP stapling
   - Have a revocation plan

## Troubleshooting

### Certificate Not Working

1. **Check certificate files**:
   ```bash
   ls -la /etc/nginx/ssl/
   ```

2. **Verify certificate format**:
   ```bash
   openssl x509 -in server.crt -text -noout
   ```

3. **Check Nginx error logs**:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Let's Encrypt Renewal Fails

1. **Check renewal logs**:
   ```bash
   sudo journalctl -u certbot-renew.service
   ```

2. **Test renewal manually**:
   ```bash
   sudo certbot renew --dry-run
   ```

3. **Check firewall**:
   ```bash
   sudo firewall-cmd --list-all
   # Ensure port 80 is open for ACME challenge
   ```

### DICOM TLS Connection Fails

1. **Verify certificate paths**:
   ```bash
   ls -la /etc/dicom-gw/tls/
   ```

2. **Check certificate validity**:
   ```bash
   openssl verify -CAfile ca.crt client.crt
   ```

3. **Test connection**:
   ```bash
   openssl s_client -connect pacs.example.com:104 -cert client.crt -key client.key
   ```

4. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gw-forwarder-worker.service -n 50
   ```

## Next Steps

- Review [Security Guide](SECURITY.md)
- Configure [Monitoring](MONITORING.md)
- Setup [Backup and Recovery](BACKUP.md)

