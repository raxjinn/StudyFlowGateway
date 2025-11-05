# DICOM Gateway Installation Guide

This guide covers the installation and initial setup of the DICOM Gateway on RHEL/Alma/Rocky Linux 8+.

## Prerequisites

### System Requirements

- **Operating System**: RHEL 8+, AlmaLinux 8+, or Rocky Linux 8+
- **Python**: 3.11 or higher
- **PostgreSQL**: 14 or higher
- **Disk Space**: Minimum 100GB for DICOM storage (varies by workload)
- **Memory**: Minimum 4GB RAM (8GB+ recommended for production)
- **CPU**: 2+ cores (4+ recommended for production)
- **Network**: Ports 104 (DICOM), 443 (HTTPS), 80 (HTTP for Let's Encrypt)

### Required Software

- PostgreSQL 14+ server
- Nginx (for reverse proxy)
- Python 3.11+ and pip
- systemd (included in RHEL/Alma/Rocky)
- certbot (for Let's Encrypt certificates)

## Installation Methods

### Method 1: RPM Installation (Recommended)

1. **Download the RPM package**:
   ```bash
   # Download from your distribution source
   wget https://example.com/dicom-gateway-0.1.0-1.el8.x86_64.rpm
   ```

2. **Install the RPM package**:
   ```bash
   sudo rpm -ivh dicom-gateway-0.1.0-1.el8.x86_64.rpm
   ```

   Or upgrade if already installed:
   ```bash
   sudo rpm -Uvh dicom-gateway-0.1.0-1.el8.x86_64.rpm
   ```

3. **Verify installation**:
   ```bash
   rpm -qi dicom-gateway
   systemctl status dicom-gateway.target
   ```

### Method 2: Manual Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourorg/dicom-gateway.git
   cd dicom-gateway
   ```

2. **Create virtual environment**:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Install systemd services**:
   ```bash
   sudo ./scripts/install-systemd-services.sh
   ```

5. **Setup storage layout**:
   ```bash
   sudo ./scripts/setup-storage-layout.sh
   ```

## PostgreSQL Setup

1. **Install PostgreSQL**:
   ```bash
   sudo dnf install -y postgresql14-server postgresql14
   ```

2. **Initialize database**:
   ```bash
   sudo postgresql-14-setup --initdb
   sudo systemctl enable postgresql-14
   sudo systemctl start postgresql-14
   ```

3. **Create database and user**:
   ```bash
   sudo -u postgres psql
   ```

   ```sql
   CREATE DATABASE dicom_gateway;
   CREATE USER dicom_gw WITH PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE dicom_gateway TO dicom_gw;
   \c dicom_gateway
   CREATE EXTENSION IF NOT EXISTS pgcrypto;
   \q
   ```

4. **Run database migrations**:
   ```bash
   cd /opt/dicom-gw
   source venv/bin/activate
   alembic upgrade head
   ```

## Initial Configuration

1. **Create configuration directory**:
   ```bash
   sudo mkdir -p /etc/dicom-gw
   sudo chown dicom-gw:dicom-gw /etc/dicom-gw
   ```

2. **Copy example configuration**:
   ```bash
   sudo cp config/config.yaml.example /etc/dicom-gw/config.yaml
   sudo chown dicom-gw:dicom-gw /etc/dicom-gw/config.yaml
   ```

3. **Edit configuration**:
   ```bash
   sudo -u dicom-gw nano /etc/dicom-gw/config.yaml
   ```

   Update at minimum:
   - Database connection settings
   - DICOM AE Title and port
   - Storage paths
   - Application settings

4. **Set environment variables** (optional):
   ```bash
   sudo mkdir -p /etc/dicom-gw
   sudo tee /etc/dicom-gw/environment <<EOF
   DICOM_GW_DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gateway
   DICOM_GW_APP_SECRET_KEY=your-secret-key-here
   DICOM_GW_JWT_SECRET_KEY=your-jwt-secret-key-here
   DICOM_GW_DB_ENCRYPTION_KEY=your-encryption-key-here
   EOF
   sudo chmod 600 /etc/dicom-gw/environment
   ```

## Nginx Setup

1. **Install Nginx**:
   ```bash
   sudo dnf install -y nginx
   ```

2. **Copy Nginx configuration**:
   ```bash
   sudo cp nginx/dicom-gateway.conf /etc/nginx/conf.d/dicom-gateway.conf
   ```

3. **Update configuration**:
   ```bash
   sudo nano /etc/nginx/conf.d/dicom-gateway.conf
   ```

   Update server_name and paths as needed.

4. **Test and start Nginx**:
   ```bash
   sudo nginx -t
   sudo systemctl enable nginx
   sudo systemctl start nginx
   ```

## Firewall Configuration

1. **Configure firewall** (firewalld):
   ```bash
   sudo firewall-cmd --permanent --add-service=http
   sudo firewall-cmd --permanent --add-service=https
   sudo firewall-cmd --permanent --add-port=104/tcp
   sudo firewall-cmd --reload
   ```

2. **Or use iptables**:
   ```bash
   sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
   sudo iptables -A INPUT -p tcp --dport 104 -j ACCEPT
   sudo service iptables save
   ```

## Start Services

1. **Start all DICOM Gateway services**:
   ```bash
   sudo systemctl start dicom-gateway.target
   sudo systemctl enable dicom-gateway.target
   ```

2. **Verify services are running**:
   ```bash
   sudo systemctl status dicom-gateway.target
   sudo systemctl status dicom-gw-api.service
   sudo systemctl status dicom-gw-scp.service
   sudo systemctl status dicom-gw-queue-worker.service
   sudo systemctl status dicom-gw-forwarder-worker.service
   sudo systemctl status dicom-gw-dbpool-worker.service
   ```

3. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gateway.target -f
   ```

## Create Initial Admin User

1. **Connect to the database**:
   ```bash
   sudo -u postgres psql -d dicom_gateway
   ```

2. **Create admin user** (using Python):
   ```bash
   cd /opt/dicom-gw
   source venv/bin/activate
   python -c "
   from dicom_gw.database.connection import init_db
   from dicom_gw.database.models import User
   from dicom_gw.security.auth import hash_password
   import asyncio
   
   async def create_admin():
       await init_db()
       from dicom_gw.database.connection import get_db_session
       async for session in get_db_session():
           admin = User(
               username='admin',
               email='admin@example.com',
               password_hash=hash_password('changeme'),
               role='admin',
               enabled=True
           )
           session.add(admin)
           await session.commit()
           print('Admin user created')
   
   asyncio.run(create_admin())
   "
   ```

3. **Change default password**:
   - Log in via web UI at https://your-server/api/docs
   - Use username: `admin`, password: `changeme`
   - Change password immediately

## Verification

1. **Check health endpoint**:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

2. **Test DICOM C-STORE**:
   ```bash
   # Use dcmtk storescu to send a test file
   storescu -aec GATEWAY_AE localhost 104 test.dcm
   ```

3. **Check web interface**:
   - Open https://your-server in a browser
   - Log in with admin credentials
   - Verify dashboard loads

## Post-Installation

1. **Configure log rotation**:
   ```bash
   sudo cp rpm/logrotate.conf /etc/logrotate.d/dicom-gw
   ```

2. **Setup monitoring** (optional):
   - Configure Prometheus scraping
   - Setup alerting rules
   - Configure Grafana dashboards

3. **Configure backups**:
   - Setup PostgreSQL backups
   - Backup configuration files
   - Backup DICOM storage (if needed)

## Troubleshooting

### Services Won't Start

1. **Check logs**:
   ```bash
   sudo journalctl -u dicom-gw-api.service -n 50
   ```

2. **Verify configuration**:
   ```bash
   sudo -u dicom-gw python -c "from dicom_gw.config.settings import get_settings; print(get_settings())"
   ```

3. **Check database connectivity**:
   ```bash
   sudo -u postgres psql -d dicom_gateway -c "SELECT 1;"
   ```

### Database Connection Issues

1. **Verify PostgreSQL is running**:
   ```bash
   sudo systemctl status postgresql-14
   ```

2. **Check connection string**:
   ```bash
   grep DICOM_GW_DATABASE_URL /etc/dicom-gw/environment
   ```

3. **Test connection**:
   ```bash
   psql -h localhost -U dicom_gw -d dicom_gateway
   ```

### Permission Issues

1. **Check file ownership**:
   ```bash
   ls -la /var/lib/dicom-gw/
   ls -la /etc/dicom-gw/
   ```

2. **Fix ownership**:
   ```bash
   sudo chown -R dicom-gw:dicom-gw /var/lib/dicom-gw
   sudo chown -R dicom-gw:dicom-gw /etc/dicom-gw
   ```

## Next Steps

- Review [Configuration Guide](CONFIGURATION.md)
- Setup [TLS/SSL Certificates](TLS_SETUP.md)
- Read [Operations Guide](OPERATIONS.md)
- Configure [Monitoring and Metrics](MONITORING.md)

