# Building the DICOM Gateway RPM

This guide explains how to build the RPM package for deployment.

## Quick Start (WSL Rocky Linux)

### 1. Install Build Tools

```bash
# Install RPM build tools
sudo dnf install -y rpm-build rpmdevtools make

# Install build dependencies (Rocky Linux 8/9)
sudo dnf install -y python3 python3-devel python3-pip gcc gcc-c++ \
    openssl-devel

# For PostgreSQL development headers, install PostgreSQL first
sudo dnf install -y postgresql postgresql-server postgresql-devel

# If you need specific Python 3.11, you may need to enable EPEL or use python3
# Rocky Linux 8 comes with Python 3.6 by default, Rocky 9 comes with Python 3.9
# For Python 3.11, you might need to:
sudo dnf install -y python3.11 python3.11-devel 2>/dev/null || \
    sudo dnf module install -y python39  # or python38 for Rocky 8
```

### Alternative: Install Python 3.11 from Source or EPEL

If Python 3.11 is not available in default repos:

```bash
# Enable EPEL (Extra Packages for Enterprise Linux)
sudo dnf install -y epel-release

# Or install Python 3.11 from source/alternative repo
# For Rocky 8, you might need to use python3.9 or python3.8
# Check available versions:
dnf list available | grep python3

# Common alternatives:
sudo dnf install -y python39 python39-devel python39-pip  # Rocky 8
# OR
sudo dnf install -y python3.9 python3.9-devel python3-pip  # Rocky 9
```

### 2. Setup RPM Build Environment

```bash
# Create RPM build directory structure
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Configure RPM (optional - creates ~/.rpmmacros)
echo "%_topdir %(echo $HOME)/rpmbuild" > ~/.rpmmacros
```

### 3. Install Node.js (for frontend build)

```bash
# Install Node.js 18+ from NodeSource
curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
sudo dnf install -y nodejs

# Or use the version available in repos
sudo dnf install -y nodejs npm
```

### 4. Clone Repository

```bash
# Clone the repository
git clone https://github.com/raxjinn/StudyFlowGateway.git
cd StudyFlowGateway
```

### 5. Build Frontend (Optional but Recommended)

```bash
# Build Vue.js frontend for production
cd frontend
npm install
npm run build
cd ..
```

### 6. Update Spec File for Your Python Version

If you're not using Python 3.11, you may need to update the spec file:

```bash
# Check your Python version
python3 --version

# If it's Python 3.9, update the spec file:
sed -i 's/python_version 3.11/python_version 3.9/' rpm/dicom-gateway.spec
sed -i 's/%{python_pkg} >= 3.11/%{python_pkg} >= 3.9/' rpm/dicom-gateway.spec
```

### 7. Build RPM

```bash
# Navigate to rpm directory
cd rpm

# Build using Makefile
make rpm

# Or build manually (see below)
```

The RPM will be created at:
```
~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

### 8. Install RPM

```bash
# Install the RPM
sudo rpm -ivh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Or upgrade if already installed
sudo rpm -Uvh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Rocky Linux Specific Notes

### Python Versions by Rocky Version

- **Rocky Linux 8**: Python 3.6 (default), Python 3.8/3.9 available via modules
- **Rocky Linux 9**: Python 3.9 (default), Python 3.11 may be available

### Installing Python 3.11 on Rocky Linux 8

```bash
# Option 1: Use Python 3.9 module (recommended for Rocky 8)
sudo dnf module reset python39
sudo dnf module enable python39
sudo dnf install -y python39 python39-devel python39-pip

# Option 2: Build Python 3.11 from source
# This is more complex but gives you the exact version

# Option 3: Use the system Python (3.6 or 3.9) and update requirements
# Update the spec file to use the available Python version
```

### PostgreSQL Installation

```bash
# For Rocky Linux 8
sudo dnf install -y postgresql postgresql-server postgresql-devel

# For PostgreSQL 14+ (if needed)
# You may need to enable PostgreSQL official repository
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm
sudo dnf install -y postgresql14-server postgresql14-devel
```

## Manual Build Process

If you prefer to build manually without the Makefile:

```bash
# 1. Setup build directory
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# 2. Create source tarball
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

# 3. Copy spec file
cp rpm/dicom-gateway.spec ~/rpmbuild/SPECS/

# 4. Build RPM
cd ~/rpmbuild
rpmbuild -ba SPECS/dicom-gateway.spec
```

## Troubleshooting

### Package Not Found Errors

**Python packages:**
```bash
# Check available Python versions
dnf list available | grep python3

# Use what's available (usually python3, python39, or python38)
sudo dnf install -y python3 python3-devel python3-pip
```

**PostgreSQL packages:**
```bash
# Check available PostgreSQL versions
dnf list available | grep postgresql

# Use what's available
sudo dnf install -y postgresql postgresql-devel

# Or enable PostgreSQL official repo for newer versions
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm
```

### Build Fails: "No such file or directory"

- Ensure you're in the project root when creating the tarball
- Check that all required files exist
- Verify the tarball was created: `tar -tzf ~/rpmbuild/SOURCES/dicom-gateway-0.1.0.tar.gz | head`

### Build Fails: Python Version Mismatch

- Check available Python: `python3 --version`
- Update the spec file to match your Python version
- Or use the system Python and update requirements

### Virtual Environment Creation Fails

- Verify Python venv module: `python3 -m venv --help`
- Check Python installation: `python3 -m pip --version`

## Verifying the RPM

```bash
# Check RPM contents
rpm -qlp ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Verify RPM signature (if signed)
rpm --checksig ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Check dependencies
rpm -qpR ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Test install (dry run)
rpm -ivh --test ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Customizing the Build

### Change Version

Edit `rpm/dicom-gateway.spec`:
```spec
Version:        0.1.0
Release:        1%{?dist}
```

Or use Makefile variables:
```bash
make rpm VERSION=0.2.0 RELEASE=1
```

### Update for Different Python Version

If your system has Python 3.9 instead of 3.11:

```bash
# Update spec file
sed -i 's/python_version 3.11/python_version 3.9/' rpm/dicom-gateway.spec
sed -i 's/%{python_pkg} >= 3.11/%{python_pkg} >= 3.9/' rpm/dicom-gateway.spec
```

## Post-Installation

After installing the RPM, follow the post-installation steps printed by the RPM, or see `docs/INSTALLATION.md`:

1. Configure database in `/etc/dicom-gw/config.yaml`
2. Run migrations: `/opt/dicom-gw/venv/bin/alembic upgrade head`
3. Configure TLS certificates
4. Enable and start services: `systemctl enable --now dicom-gw.target`
