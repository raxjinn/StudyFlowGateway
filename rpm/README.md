# RPM Packaging for DICOM Gateway

This directory contains files for building an RPM package for the DICOM Gateway.

## Prerequisites

1. **RPM build tools installed**:
   ```bash
   sudo dnf install rpm-build rpmdevtools
   ```

2. **Build dependencies**:
   ```bash
   sudo dnf install python3 python3-devel python3-pip gcc openssl-devel
   ```

3. **Source code**: Ensure you're in the project root directory

## Building the RPM

### Option 1: Using Makefile (Recommended)

```bash
# From the project root directory
cd rpm
make rpm
```

This will:
1. Create the RPM build directory structure
2. Create a source tarball
3. Build the RPM package
4. Output the RPM location

### Option 2: Manual Build

```bash
# Setup RPM build directory
mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

# Create source tarball
cd ..
tar --exclude='.git' --exclude='*.pyc' --exclude='__pycache__' \
    --exclude='venv' --exclude='node_modules' \
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

## Installing the RPM

```bash
# Install RPM
sudo rpm -ivh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Or upgrade if already installed
sudo rpm -Uvh ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Post-Installation Steps

After installing the RPM:

1. **Configure database**:
   ```bash
   sudo nano /etc/dicom-gw/config.yaml
   ```

2. **Run database migrations**:
   ```bash
   sudo -u dicom-gw /opt/dicom-gw/venv/bin/alembic upgrade head
   ```

3. **Configure TLS certificates** (see `docs/tls-setup.md`)

4. **Enable and start services**:
   ```bash
   sudo systemctl enable dicom-gw.target
   sudo systemctl start dicom-gw.target
   ```

## RPM Spec File Details

The `dicom-gateway.spec` file includes:

- **Metadata**: Name, version, description, dependencies
- **Build process**: Creates virtual environment and installs dependencies
- **File layout**: Defines all files to be packaged
- **Pre-install script**: Creates user, checks prerequisites
- **Post-install script**: Sets up directories, permissions, environment files
- **Pre-uninstall script**: Stops services before removal
- **Post-uninstall script**: Cleans up systemd, preserves data

## Customizing the Build

### Change Version

Edit `rpm/dicom-gateway.spec`:
```spec
Version:        0.1.0
Release:        1%{?dist}
```

Or use Makefile:
```bash
make rpm VERSION=0.2.0 RELEASE=1
```

### Add Dependencies

Edit `rpm/dicom-gateway.spec`:
```spec
Requires:       your-package >= 1.0
```

### Modify Install Paths

Edit the macros in `rpm/dicom-gateway.spec`:
```spec
%global app_path /opt/dicom-gw
%global config_path /etc/dicom-gw
```

## Building Source RPM (SRPM)

```bash
make srpm
```

The SRPM will be created at:
```
~/rpmbuild/SRPMS/dicom-gateway-0.1.0-1.el8.src.rpm
```

SRPMs can be used to rebuild the RPM on different systems.

## Testing the RPM

### Check RPM Contents

```bash
rpm -qlp ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

### Verify RPM

```bash
rpm --checksig ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

### Test Install (Dry Run)

```bash
rpm -ivh --test ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

### Check Dependencies

```bash
rpm -qpR ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm
```

## Troubleshooting

### Build Fails with "No such file or directory"

- Ensure you're running from the project root
- Check that all source files exist
- Verify the tarball was created correctly

### Virtual Environment Creation Fails

- Ensure Python 3.11+ is installed
- Check that `python3 -m venv` works
- Verify pip is available

### Missing Dependencies

- Install all BuildRequires packages
- Check that system packages are available
- Review error messages for specific missing dependencies

### Permission Errors

- Ensure you have write access to `~/rpmbuild`
- Check that you can create directories and files
- Verify user permissions

## Distribution

### Local Repository

Create a local YUM repository:

```bash
# Create repository directory
sudo mkdir -p /var/www/html/repos/dicom-gateway

# Copy RPM
sudo cp ~/rpmbuild/RPMS/noarch/*.rpm /var/www/html/repos/dicom-gateway/

# Create repository metadata
sudo createrepo /var/www/html/repos/dicom-gateway
```

### Sign RPM (Optional)

```bash
# Generate GPG key (if not exists)
gpg --gen-key

# Export public key
gpg --export -a "Your Name" > RPM-GPG-KEY

# Sign RPM
rpm --addsign ~/rpmbuild/RPMS/noarch/dicom-gateway-0.1.0-1.el8.noarch.rpm

# Import key on target system
sudo rpm --import RPM-GPG-KEY
```

## References

- [RPM Packaging Guide](https://rpm-packaging-guide.github.io/)
- [Fedora Packaging Guidelines](https://docs.fedoraproject.org/en-US/packaging-guidelines/)
- [RPM Spec File Reference](https://rpm.org/documentation.html)

