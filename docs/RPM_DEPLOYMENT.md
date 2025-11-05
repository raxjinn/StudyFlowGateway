# Complete RPM Deployment Guide

This guide walks you through building and deploying the DICOM Gateway as an RPM package on Rocky Linux (WSL or bare metal).

## Prerequisites

- Rocky Linux 8 or 9 (installed in WSL or on bare metal)
- sudo/root access
- Internet connection for downloading dependencies

## Step 1: Open WSL Rocky Linux

If using WSL, open your terminal:

```bash
# In PowerShell or Windows Terminal
wsl

# Or if you have multiple distributions:
wsl -d Rocky-Linux-8  # or whatever your distribution is named
```

## Step 2: Update System

```bash
# Update system packages
sudo dnf update -y

# Install EPEL repository (useful for additional packages)
sudo dnf install -y epel-release
```

## Step 3: Install Build Dependencies

Run the automated setup script:

```bash
# Clone the repository first (we'll use it for the setup script)
git clone https://github.com/raxjinn/StudyFlowGateway.git
cd StudyFlowGateway

# Make the setup script executable
chmod +x scripts/setup-build-deps.sh

# Run the setup script
./scripts/setup-build-deps.sh
```

**OR** install manually:

```bash
# Install RPM build tools
sudo dnf install -y rpm-build rpmdevtools make gcc gcc-c++ openssl-devel

# Install Python 3.9 (Rocky 8) or Python 3.9/3.11 (Rocky 9)
sudo dnf module reset python39 2>/dev/null || true
sudo dnf module enable python39 -y
sudo dnf install -y python39 python39-devel python39-pip

# Install PostgreSQL development headers
sudo dnf install -y postgresql postgresql-devel

# Install Node.js for frontend build
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo dnf install -y nodejs

# Setup RPM build directory
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
```

## Step 4: Clone Repository (if not already done)

```bash
# If you already cloned in Step 3, skip this
git clone https://github.com/raxjinn/StudyFlowGateway.git
cd StudyFlowGateway
```

## Step 5: Update Spec File for Python Version

If you're using Python 3.9 instead of 3.11, update the spec file:

```bash
# Check your Python version
python3.9 --version  # or python39 --version

# Update spec file if needed
sed -i 's/python_version 3.11/python_version 3.9/' rpm/dicom-gateway.spec
sed -i 's/%{python_pkg} >= 3.11/%{python_pkg} >= 3.9/' rpm/dicom-gateway.spec
```

## Step 6: Build Frontend (Optional but Recommended)

Build the Vue.js frontend for production:

```bash
cd frontend
npm install
npm run build
cd ..
```

## Step 7: Build the RPM

**Option A: Using Makefile (Recommended)**

```bash
cd rpm
make rpm
```

**Option B: Using the build script**

```bash
chmod +x scripts/build-rpm.sh
./scripts/build-rpm.sh
```

**Option C: Manual build**

```bash
# Create source tarball
cd /path/to/StudyFlowGateway
tar --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='venv' \
    --exclude='*.egg-info' \
    --exclude='dist' \
    --exclude='build' \
    --exclude='node_modules' \
    --exclude='frontend/dist' \
    --exclude='frontend/node_modules' \
    --exclude='.cursor' \
    -czf ~/rpmbuild/SOURCES/dicom-gateway-0.1.0.tar.gz \
    --transform 's,^\.,dicom-gateway-0.1.0,' .

# Copy spec file
cp rpm/dicom-gateway.spec ~/rpmbuild/SPECS/

# Build RPM
rpmbuild -ba ~/rpmbuild/SPECS/dicom-gateway.spec
```

The RPM will be created at:
```
~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Step 8: Verify the RPM

```bash
# Check RPM contents
rpm -qlp ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Check dependencies
rpm -qpR ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Test install (dry run - doesn't actually install)
rpm -ivh --test ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Step 9: Install PostgreSQL (if not already installed)

```bash
# Install PostgreSQL
sudo dnf install -y postgresql postgresql-server postgresql-contrib

# Initialize PostgreSQL database
sudo postgresql-setup --initdb

# Start and enable PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE dicom_gw;
CREATE USER dicom_gw WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE dicom_gw TO dicom_gw;
ALTER USER dicom_gw CREATEDB;
\q
EOF

# Enable pgcrypto extension
sudo -u postgres psql -d dicom_gw <<EOF
CREATE EXTENSION IF NOT EXISTS pgcrypto;
\q
EOF
```

## Step 10: Install the RPM

```bash
# Install the RPM
sudo rpm -ivh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Or if upgrading an existing installation
sudo rpm -Uvh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

The installation will print next steps. It will create:
- Application files in `/opt/dicom-gw/`
- Configuration in `/etc/dicom-gw/`
- Data directories in `/var/lib/dicom-gw/`
- Logs in `/var/log/dicom-gw/`
- Systemd service files

## Step 11: Configure the Gateway

### 11.1: Edit Configuration File

```bash
sudo nano /etc/dicom-gw/config.yaml
```

Update the database connection (example):

```yaml
database:
  url: postgresql+asyncpg://dicom_gw:your_secure_password_here@localhost:5432/dicom_gw
```

Or set environment variables:

```bash
sudo nano /etc/dicom-gw/dicom-gw-api.env
```

Add:
```bash
DATABASE_URL=postgresql+asyncpg://dicom_gw:your_secure_password_here@localhost:5432/dicom_gw
DICOM_GW_APP_ENV=production
DICOM_GW_APP_DEBUG=false
```

### 11.2: Set Encryption Key

```bash
# Generate a secure encryption key
openssl rand -hex 32

# Add to environment files
echo "DICOM_GW_DB_ENCRYPTION_KEY=your_generated_key_here" | sudo tee -a /etc/dicom-gw/dicom-gw-api.env
echo "DICOM_GW_DB_ENCRYPTION_KEY=your_generated_key_here" | sudo tee -a /etc/dicom-gw/dicom-gw-workers.env
```

### 11.3: Configure DICOM Settings

```bash
sudo nano /etc/dicom-gw/dicom-gw-scp.env
```

Add:
```bash
DICOM_GW_DICOM_AE_TITLE=DICOMGW
DICOM_GW_DICOM_PORT=104
```

## Step 12: Run Database Migrations

```bash
# Run Alembic migrations
sudo -u dicom-gw /opt/dicom-gw/venv/bin/alembic -c /opt/dicom-gw/alembic.ini upgrade head
```

## Step 13: Create Admin User

```bash
# Create an admin user (you'll need to create a script or use the API)
sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 <<EOF
from dicom_gw.database.connection import get_db_session
from dicom_gw.database.models import User
from dicom_gw.security.auth import get_password_hash
import asyncio

async def create_admin():
    async for session in get_db_session():
        admin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin_password_change_me"),
            is_active=True,
            is_superuser=True,
            roles=["admin"]
        )
        session.add(admin)
        await session.commit()
        print("Admin user created: admin / admin_password_change_me")
        break

asyncio.run(create_admin())
EOF
```

## Step 14: Configure Nginx (Optional but Recommended)

```bash
# Install Nginx
sudo dnf install -y nginx

# Test Nginx configuration
sudo nginx -t

# If configuration is valid, start Nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

The RPM installs the Nginx configuration at `/etc/nginx/conf.d/dicom-gateway.conf`. You may need to adjust it for your domain.

## Step 15: Configure TLS/SSL (Optional but Recommended)

See `docs/TLS_SETUP.md` for detailed TLS configuration, including Let's Encrypt setup.

Quick Let's Encrypt setup:

```bash
# Install certbot
sudo dnf install -y certbot python3-certbot-nginx

# Obtain certificate (replace with your domain)
sudo certbot --nginx -d your-domain.com

# Certificates will be auto-renewed via systemd timer
```

## Step 16: Start Services

```bash
# Enable all services
sudo systemctl enable dicom-gw.target

# Start all services
sudo systemctl start dicom-gw.target

# Check status
sudo systemctl status dicom-gw.target

# Check individual services
sudo systemctl status dicom-gw-api.service
sudo systemctl status dicom-gw-queue-worker.service
sudo systemctl status dicom-gw-forwarder-worker.service
sudo systemctl status dicom-gw-dbpool-worker.service
sudo systemctl status dicom-gw-scp.service
```

## Step 17: Verify Installation

```bash
# Check API health endpoint
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics/prometheus

# View logs
sudo journalctl -u dicom-gw-api.service -f
sudo journalctl -u dicom-gw-scp.service -f
```

## Step 18: Access Web Interface

If Nginx is configured, access:
- `http://your-domain.com` or `http://localhost`
- Default admin credentials: `admin` / `admin_password_change_me` (change immediately!)

## Troubleshooting

### Service Fails to Start

```bash
# Check service status
sudo systemctl status dicom-gw-api.service

# View logs
sudo journalctl -u dicom-gw-api.service -n 50

# Check configuration
sudo -u dicom-gw /opt/dicom-gw/venv/bin/python3 -c "from dicom_gw.config.settings import get_settings; print(get_settings())"
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
sudo -u postgres psql -d dicom_gw -c "SELECT version();"

# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify database user
sudo -u postgres psql -c "\du dicom_gw"
```

### Permission Issues

```bash
# Check ownership
ls -la /opt/dicom-gw/
ls -la /var/lib/dicom-gw/
ls -la /etc/dicom-gw/

# Fix ownership if needed
sudo chown -R dicom-gw:dicom-gw /opt/dicom-gw
sudo chown -R dicom-gw:dicom-gw /var/lib/dicom-gw
sudo chown -R dicom-gw:dicom-gw /etc/dicom-gw
```

### RPM Build Fails

```bash
# Check build logs
tail -f ~/rpmbuild/BUILD/*/build.log

# Clean and rebuild
cd rpm
make clean
make rpm
```

## Quick Reference Commands

```bash
# Start services
sudo systemctl start dicom-gw.target

# Stop services
sudo systemctl stop dicom-gw.target

# Restart services
sudo systemctl restart dicom-gw.target

# View logs
sudo journalctl -u dicom-gw.target -f

# Check all service statuses
sudo systemctl status dicom-gw.target

# Rebuild RPM
cd ~/StudyFlowGateway/rpm
make clean
make rpm

# Reinstall RPM
sudo rpm -Uvh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Next Steps

- Review `docs/OPERATIONS.md` for day-to-day operations
- Review `docs/CONFIGURATION.md` for advanced configuration
- Set up monitoring and alerting
- Configure backup procedures
- Review security hardening in `docs/INSTALLATION.md`

## Support

For issues or questions:
- Check the logs: `sudo journalctl -u dicom-gw-*.service`
- Review documentation in `docs/`
- Check GitHub issues: https://github.com/raxjinn/StudyFlowGateway/issues

