# Building the DICOM Gateway RPM

This guide explains how to build the RPM package for deployment.

## Quick Start (WSL Rocky Linux)

### 1. Install Build Tools

```bash
# Install RPM build tools
sudo dnf install -y rpm-build rpmdevtools make

# Install build dependencies
sudo dnf install -y python3.11 python3.11-devel python3-pip gcc gcc-c++ \
    openssl-devel postgresql14-devel
```

### 2. Setup RPM Build Environment

```bash
# Create RPM build directory structure
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Configure RPM (optional - creates ~/.rpmmacros)
echo "%_topdir %(echo $HOME)/rpmbuild" > ~/.rpmmacros
```

### 3. Clone Repository

```bash
# Clone the repository
git clone https://github.com/raxjinn/StudyFlowGateway.git
cd StudyFlowGateway
```

### 4. Build Frontend (Optional but Recommended)

```bash
# Build Vue.js frontend for production
cd frontend
npm install
npm run build
cd ..
```

### 5. Build RPM

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

### 6. Install RPM

```bash
# Install the RPM
sudo rpm -ivh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Or upgrade if already installed
sudo rpm -Uvh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
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

## Build from Windows (WSL)

You can build the RPM from Windows using WSL:

```powershell
# In PowerShell
wsl

# Then in WSL, follow the steps above
```

## Troubleshooting

### Build Fails: "No such file or directory"

- Ensure you're in the project root when creating the tarball
- Check that all required files exist
- Verify the tarball was created: `tar -tzf ~/rpmbuild/SOURCES/dicom-gateway-0.1.0.tar.gz | head`

### Build Fails: Python Version

- Ensure Python 3.11+ is installed: `python3.11 --version`
- Update the spec file if using a different Python version

### Build Fails: Missing Dependencies

- Install all BuildRequires: `sudo dnf install python3-devel gcc openssl-devel`
- Check error messages for specific missing packages

### Build Fails: Permission Denied

- Ensure you have write access to `~/rpmbuild`
- Check file permissions in the project directory

### Virtual Environment Creation Fails

- Verify Python venv module: `python3.11 -m venv --help`
- Check Python installation: `python3.11 -m pip --version`

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

### Build for Different Distribution

The spec file uses `%{?dist}` which automatically detects the distribution. For specific distributions:

```bash
# For Rocky Linux 8
rpmbuild -ba SPECS/dicom-gateway.spec --define "dist .el8"

# For AlmaLinux 8
rpmbuild -ba SPECS/dicom-gateway.spec --define "dist .el8"

# For RHEL 8
rpmbuild -ba SPECS/dicom-gateway.spec --define "dist .el8"
```

## Post-Installation

After installing the RPM, follow the post-installation steps printed by the RPM, or see `docs/INSTALLATION.md`:

1. Configure database in `/etc/dicom-gw/config.yaml`
2. Run migrations: `/opt/dicom-gw/venv/bin/alembic upgrade head`
3. Configure TLS certificates
4. Enable and start services: `systemctl enable --now dicom-gw.target`

