# WSL Rocky Linux Deployment Guide

This guide covers deploying the DICOM Gateway in WSL (Windows Subsystem for Linux) running Rocky Linux.

## Prerequisites

1. **WSL 2** installed with Rocky Linux distribution
2. **Windows 11** or **Windows 10** (version 2004 or later)
3. Sufficient disk space (minimum 10GB free)

## WSL Setup

### 1. Install WSL 2 (if not already installed)

```powershell
# In PowerShell (as Administrator)
wsl --install
wsl --set-default-version 2
```

### 2. Install Rocky Linux in WSL

```powershell
# Download and install Rocky Linux WSL image
wsl --import RockyLinux C:\WSL\RockyLinux <path-to-rockylinux-wsl-image.tar>
```

Or use a pre-built Rocky Linux WSL distribution from the Microsoft Store.

### 3. Start Rocky Linux WSL

```powershell
wsl -d RockyLinux
```

Or from WSL:
```bash
wsl
```

## Clone Repository

```bash
# Update system
sudo dnf update -y

# Install git
sudo dnf install -y git

# Clone repository
git clone https://github.com/evanprohaska-studyflow/StudyFlowGateway.git
cd StudyFlowGateway
```

## Install Dependencies

### 1. Install PostgreSQL

```bash
# Install PostgreSQL 14
sudo dnf install -y postgresql14-server postgresql14

# Initialize database
sudo postgresql-14-setup --initdb

# Start PostgreSQL
sudo systemctl enable postgresql-14
sudo systemctl start postgresql-14

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE dicom_gateway;
CREATE USER dicom_gw WITH PASSWORD 'dicom_gw_password';
GRANT ALL PRIVILEGES ON DATABASE dicom_gateway TO dicom_gw;
\c dicom_gateway
CREATE EXTENSION IF NOT EXISTS pgcrypto;
\q
EOF
```

### 2. Install Python 3.11+

```bash
# Install Python 3.11
sudo dnf install -y python3.11 python3.11-pip python3.11-devel

# Install build dependencies
sudo dnf install -y gcc gcc-c++ make postgresql14-devel openssl-devel
```

### 3. Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 4. Install Node.js (for frontend)

```bash
# Install Node.js 18+
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo dnf install -y nodejs

# Verify installation
node --version
npm --version
```

## Configuration

### 1. Create Configuration Directory

```bash
# Create config directory
sudo mkdir -p /etc/dicom-gw
sudo chown $USER:$USER /etc/dicom-gw

# Copy example configuration
cp config/config.yaml.example /etc/dicom-gw/config.yaml

# Edit configuration
nano /etc/dicom-gw/config.yaml
```

### 2. Update Configuration

Update `/etc/dicom-gw/config.yaml`:

```yaml
application:
  debug: true  # Enable debug mode for development
  host: "0.0.0.0"  # Allow access from Windows host
  port: 8000

database:
  url: "postgresql+asyncpg://dicom_gw:dicom_gw_password@localhost:5432/dicom_gateway"

dicom:
  ae_title: "WSL_GATEWAY"
  port: 10404  # Use non-standard port to avoid conflicts
```

### 3. Set Environment Variables

```bash
# Create environment file
cat > ~/.env <<EOF
DICOM_GW_DATABASE_URL=postgresql+asyncpg://dicom_gw:dicom_gw_password@localhost:5432/dicom_gateway
DICOM_GW_APP_SECRET_KEY=$(python3.11 -c "import secrets; print(secrets.token_urlsafe(32))")
DICOM_GW_JWT_SECRET_KEY=$(python3.11 -c "import secrets; print(secrets.token_urlsafe(32))")
DICOM_GW_DB_ENCRYPTION_KEY=$(python3.11 -c "import secrets; print(secrets.token_hex(32))")
EOF

# Source environment variables
source ~/.env
```

## Database Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Run migrations
alembic upgrade head

# Create admin user
python3 <<EOF
import asyncio
from dicom_gw.database.connection import init_db
from dicom_gw.database.models import User
from dicom_gw.security.auth import hash_password

async def create_admin():
    await init_db()
    from dicom_gw.database.connection import get_db_session
    async for session in get_db_session():
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=hash_password('admin'),
            role='admin',
            enabled=True
        )
        session.add(admin)
        await session.commit()
        print('Admin user created: admin/admin')

asyncio.run(create_admin())
EOF
```

## Storage Setup

```bash
# Create storage directories
mkdir -p ~/dicom-gw-storage/{incoming,queue,forwarded,failed,tmp}
chmod 755 ~/dicom-gw-storage

# Update config to use this path
# Update config.yaml: dicom.storage.incoming_path = "~/dicom-gw-storage/incoming"
```

## Build Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build for development
npm run build

# Or run dev server
npm run dev

cd ..
```

## Running Services

### Option 1: Development Mode (Manual)

```bash
# Terminal 1: Run API
source venv/bin/activate
cd /path/to/StudyFlowGateway
python -m dicom_gw.api.main

# Terminal 2: Run SCP
source venv/bin/activate
python -m dicom_gw.dicom.scp_service

# Terminal 3: Run Queue Worker
source venv/bin/activate
python -m dicom_gw.workers.queue_worker

# Terminal 4: Run Forwarding Worker
source venv/bin/activate
python -m dicom_gw.workers.forwarder_worker
```

### Option 2: Using systemd (if available in WSL)

```bash
# Install systemd services
sudo ./scripts/install-systemd-services.sh

# Start services
sudo systemctl start dicom-gateway.target
```

### Option 3: Using Docker Compose (Alternative)

Create a `docker-compose.yml` for easier WSL deployment:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: dicom_gateway
      POSTGRES_USER: dicom_gw
      POSTGRES_PASSWORD: dicom_gw_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DICOM_GW_DATABASE_URL=postgresql+asyncpg://dicom_gw:dicom_gw_password@postgres:5432/dicom_gateway
    depends_on:
      - postgres
```

## Access from Windows Host

### Find WSL IP Address

```bash
# In WSL
hostname -I
```

### Port Forwarding (Optional)

If you need to access services from Windows, you can use port forwarding:

```powershell
# In PowerShell (as Administrator)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL_IP>
netsh interface portproxy add v4tov4 listenport=10404 listenaddress=0.0.0.0 connectport=10404 connectaddress=<WSL_IP>
```

### Access Services

- **API**: http://localhost:8000/api/v1/health
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **DICOM**: localhost:10404

## WSL-Specific Considerations

### 1. systemd Support

WSL may not have systemd enabled by default. Check:

```bash
# Check if systemd is available
systemctl --version

# If not available, you can enable it in WSL
# Edit /etc/wsl.conf:
sudo nano /etc/wsl.conf

# Add:
[boot]
systemd=true

# Restart WSL from PowerShell:
# wsl --shutdown
# wsl
```

### 2. File Permissions

WSL handles file permissions differently. Ensure proper ownership:

```bash
# Fix ownership if needed
sudo chown -R $USER:$USER ~/StudyFlowGateway
```

### 3. Network Access

- WSL shares networking with Windows host
- Use `localhost` or `127.0.0.1` to access from Windows
- Use actual WSL IP for access from other machines

### 4. Firewall

Windows Firewall may block connections. Allow ports if needed:

```powershell
# In PowerShell (as Administrator)
New-NetFirewallRule -DisplayName "WSL DICOM Gateway API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "WSL DICOM Gateway SCP" -Direction Inbound -LocalPort 10404 -Protocol TCP -Action Allow
```

### 5. Performance

WSL 2 uses a virtual machine, so:
- Performance is good but may be slightly slower than native Linux
- I/O operations may be slower than native
- Network performance is excellent

## Testing

### 1. Test API

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"

# Use token for authenticated requests
TOKEN="your_token_here"
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/studies
```

### 2. Test DICOM C-STORE

```bash
# Install dcmtk for testing
sudo dnf install -y dcmtk

# Send test file
storescu -aec WSL_GATEWAY localhost 10404 test.dcm
```

### 3. Test from Windows

```powershell
# In PowerShell
Invoke-WebRequest -Uri http://localhost:8000/api/v1/health
```

## Troubleshooting

### PostgreSQL Not Starting

```bash
# Check PostgreSQL status
sudo systemctl status postgresql-14

# Check logs
sudo journalctl -u postgresql-14 -n 50

# Start manually if needed
sudo -u postgres /usr/pgsql-14/bin/postgres -D /var/lib/pgsql/14/data
```

### Port Already in Use

```bash
# Check what's using the port
sudo netstat -tlnp | grep 8000
sudo netstat -tlnp | grep 10404

# Kill process if needed
sudo kill -9 <PID>
```

### Permission Denied

```bash
# Fix permissions
sudo chown -R $USER:$USER ~/StudyFlowGateway
chmod +x scripts/*.sh
```

### Database Connection Issues

```bash
# Test connection
psql -h localhost -U dicom_gw -d dicom_gateway

# Check PostgreSQL is listening
sudo netstat -tlnp | grep 5432
```

## Development Tips

1. **Use VS Code Remote-WSL**: Install "Remote - WSL" extension for better development experience
2. **Use Windows Terminal**: Better terminal experience with tabs
3. **Git Configuration**: Configure git in WSL for seamless version control
4. **File Access**: Access WSL files from Windows at `\\wsl$\RockyLinux\home\<username>`

## Next Steps

- Review [Configuration Guide](CONFIGURATION.md)
- Read [Operations Guide](OPERATIONS.md)
- Setup [Monitoring](MONITORING.md)

