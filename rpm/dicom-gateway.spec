# DICOM Gateway RPM Specification
# Build for RHEL/Alma/Rocky Linux 8+

%global python_version 3.11
%global python_pkg python3
%global venv_path /opt/dicom-gw/venv
%global app_path /opt/dicom-gw
%global config_path /etc/dicom-gw
%global data_path /var/lib/dicom-gw
%global log_path /var/log/dicom-gw
%global service_user dicom-gw

%define _python3_version %{python_version}

Name:           dicom-gateway
Version:        0.1.0
Release:        1%{?dist}
Summary:        HIPAA-compliant Linux DICOM Gateway for receiving and forwarding medical imaging studies
License:        Proprietary
Group:          Applications/Medical
URL:            https://github.com/raxjinn/StudyFlowGateway
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  %{python_pkg} >= 3.11
BuildRequires:  %{python_pkg}-devel
BuildRequires:  %{python_pkg}-pip
BuildRequires:  %{python_pkg}-setuptools
BuildRequires:  gcc
BuildRequires:  openssl-devel
Requires:       %{python_pkg} >= 3.11
Requires:       postgresql-server >= 12
Requires:       postgresql-contrib
Requires:       nginx >= 1.18
Requires:       systemd
Requires:       openssl
Requires:       cryptsetup
Requires:       certbot

%description
DICOM Gateway is a lightweight, HIPAA-compliant Linux DICOM Gateway designed for
receiving and forwarding DICOM studies quickly while preserving exact byte integrity
(including the 128-byte preamble and 4-byte "DICM" prefix). The gateway tracks
performance, provides a modern web UI, and ensures robust security.

Features:
- Byte-preserving DICOM I/O with exact integrity verification
- PostgreSQL-backed job queue with LISTEN/NOTIFY
- Asynchronous I/O for high throughput
- Prometheus-style metrics and health endpoints
- Vue.js 3 frontend for management and monitoring
- TLS/SSL encryption with Let's Encrypt support
- Role-based access control (RBAC)
- Comprehensive audit logging

%prep
%setup -q

%build
# Create virtual environment
%{__python3} -m venv %{venv_path}

# Install Python dependencies
%{venv_path}/bin/pip install --upgrade pip setuptools wheel
%{venv_path}/bin/pip install -r requirements.txt

# Install the package itself
%{venv_path}/bin/pip install .

%install
# Create directories
mkdir -p %{buildroot}%{app_path}
mkdir -p %{buildroot}%{config_path}
mkdir -p %{buildroot}%{config_path}/tls
mkdir -p %{buildroot}%{data_path}
mkdir -p %{buildroot}%{log_path}
mkdir -p %{buildroot}%{_unitdir}
mkdir -p %{buildroot}%{_sysconfdir}/nginx/conf.d
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d
mkdir -p %{buildroot}%{_docdir}/%{name}-%{version}
mkdir -p %{buildroot}%{_mandir}/man1

# Copy application files
cp -r dicom_gw %{buildroot}%{app_path}/
cp -r migrations %{buildroot}%{app_path}/
cp setup.py %{buildroot}%{app_path}/
cp requirements.txt %{buildroot}%{app_path}/
cp README.md %{buildroot}%{app_path}/
cp alembic.ini %{buildroot}%{app_path}/
cp pytest.ini %{buildroot}%{app_path}/

# Copy configuration files
cp config/config.yaml.example %{buildroot}%{config_path}/config.yaml.example
if [ ! -f %{buildroot}%{config_path}/config.yaml ]; then
    cp config/config.yaml.example %{buildroot}%{config_path}/config.yaml
fi

# Copy systemd service files (including template files for scaling)
# Copy regular service files
cp systemd/dicom-gw-api.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-queue-worker.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-forwarder-worker.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-dbpool-worker.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-scp.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-autoscaler.service %{buildroot}%{_unitdir}/
# Copy template service files for horizontal scaling
cp systemd/dicom-gw-queue-worker@.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-forwarder-worker@.service %{buildroot}%{_unitdir}/
cp systemd/dicom-gw-dbpool-worker@.service %{buildroot}%{_unitdir}/
# Copy target file
cp systemd/dicom-gw.target %{buildroot}%{_unitdir}/

# Copy Nginx configuration
cp nginx/dicom-gateway.conf %{buildroot}%{_sysconfdir}/nginx/conf.d/

# Copy logrotate configuration
cp rpm/logrotate.conf %{buildroot}%{_sysconfdir}/logrotate.d/dicom-gateway

# Copy scripts (create directory first)
mkdir -p %{buildroot}%{app_path}/scripts
# Copy scripts explicitly (check both relative and absolute paths)
if [ -d scripts ] && [ -n "$(ls -A scripts/*.sh 2>/dev/null)" ]; then
    cp scripts/*.sh %{buildroot}%{app_path}/scripts/ 2>/dev/null || true
    chmod +x %{buildroot}%{app_path}/scripts/*.sh 2>/dev/null || true
fi
# Also check if we're in the extracted source directory
if [ -d %{name}-%{version}/scripts ] && [ -n "$(ls -A %{name}-%{version}/scripts/*.sh 2>/dev/null)" ]; then
    cp %{name}-%{version}/scripts/*.sh %{buildroot}%{app_path}/scripts/ 2>/dev/null || true
    chmod +x %{buildroot}%{app_path}/scripts/*.sh 2>/dev/null || true
fi

# Copy documentation
cp -r docs/* %{buildroot}%{_docdir}/%{name}-%{version}/ 2>/dev/null || true

# Create virtual environment (symlink to actual location)
# The actual venv will be created in %post script

# Set permissions
chmod 750 %{buildroot}%{app_path}
chmod 750 %{buildroot}%{config_path}
chmod 750 %{buildroot}%{data_path}
chmod 750 %{buildroot}%{log_path}

%pre
# Pre-install script
# Check if user exists, create if not
if ! id -u %{service_user} >/dev/null 2>&1; then
    /usr/sbin/useradd -r -s /bin/false -d %{app_path} -c "DICOM Gateway Service User" %{service_user} 2>/dev/null || true
fi

# Check PostgreSQL
if ! /usr/bin/systemctl is-active --quiet postgresql 2>/dev/null; then
    echo "Warning: PostgreSQL service is not running. Please start it before using DICOM Gateway."
fi

%post
# Post-install script
# Create virtual environment
if [ ! -d %{venv_path} ]; then
    %{__python3} -m venv %{venv_path}
    %{venv_path}/bin/pip install --upgrade pip setuptools wheel
    %{venv_path}/bin/pip install -r %{app_path}/requirements.txt
    %{venv_path}/bin/pip install %{app_path}
fi

# Set ownership
chown -R %{service_user}:%{service_user} %{app_path}
chown -R %{service_user}:%{service_user} %{config_path}
chown -R %{service_user}:%{service_user} %{data_path}
chown -R %{service_user}:%{service_user} %{log_path}

# Create necessary subdirectories
mkdir -p %{data_path}/storage
mkdir -p %{data_path}/incoming
mkdir -p %{data_path}/queue
mkdir -p %{data_path}/forwarded
mkdir -p %{data_path}/failed
mkdir -p %{data_path}/tmp
mkdir -p %{config_path}/tls
mkdir -p %{log_path}

chown -R %{service_user}:%{service_user} %{data_path}
chown -R %{service_user}:%{service_user} %{config_path}
chown -R %{service_user}:%{service_user} %{log_path}

# Set permissions
chmod 750 %{data_path}
chmod 750 %{config_path}
chmod 750 %{config_path}/tls
chmod 750 %{log_path}

# Create environment files if they don't exist
if [ ! -f %{config_path}/dicom-gw-api.env ]; then
    cat > %{config_path}/dicom-gw-api.env <<EOF
# DICOM Gateway API Service Environment Variables
# DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
# DICOM_GW_APP_ENV=production
# DICOM_GW_APP_DEBUG=false
EOF
    chmod 640 %{config_path}/dicom-gw-api.env
    chown %{service_user}:%{service_user} %{config_path}/dicom-gw-api.env
fi

if [ ! -f %{config_path}/dicom-gw-workers.env ]; then
    cat > %{config_path}/dicom-gw-workers.env <<EOF
# DICOM Gateway Workers Environment Variables
# DATABASE_URL=postgresql+asyncpg://dicom_gw:password@localhost:5432/dicom_gw
EOF
    chmod 640 %{config_path}/dicom-gw-workers.env
    chown %{service_user}:%{service_user} %{config_path}/dicom-gw-workers.env
fi

if [ ! -f %{config_path}/dicom-gw-scp.env ]; then
    cat > %{config_path}/dicom-gw-scp.env <<EOF
# DICOM Gateway SCP Service Environment Variables
# DICOM_GW_DICOM_AE_TITLE=DICOMGW
# DICOM_GW_DICOM_PORT=104
EOF
    chmod 640 %{config_path}/dicom-gw-scp.env
    chown %{service_user}:%{service_user} %{config_path}/dicom-gw-scp.env
fi

# Reload systemd
/usr/bin/systemctl daemon-reload

# Test Nginx configuration if Nginx is installed
if command -v nginx >/dev/null 2>&1; then
    /usr/sbin/nginx -t >/dev/null 2>&1 || echo "Warning: Nginx configuration test failed. Please check /etc/nginx/conf.d/dicom-gateway.conf"
fi

echo ""
echo "DICOM Gateway installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Configure database: Edit %{config_path}/config.yaml or set environment variables"
echo "  2. Run database migrations: %{venv_path}/bin/alembic upgrade head"
echo "  3. Configure TLS certificates (see docs/tls-setup.md)"
echo "  4. Enable services: systemctl enable dicom-gw.target"
echo "  5. Start services: systemctl start dicom-gw.target"
echo ""

%preun
# Pre-uninstall script
if [ $1 -eq 0 ]; then
    # Package is being removed, not upgraded
    /usr/bin/systemctl stop dicom-gw.target 2>/dev/null || true
    /usr/bin/systemctl disable dicom-gw.target 2>/dev/null || true
fi

%postun
# Post-uninstall script
/usr/bin/systemctl daemon-reload

if [ $1 -eq 0 ]; then
    # Package is being removed, not upgraded
    # Optionally remove user (commented out to preserve data)
    # userdel %{service_user} 2>/dev/null || true
    echo "DICOM Gateway removed. Data in %{data_path} and %{config_path} has been preserved."
fi

%files
# Application files
%dir %{app_path}
%dir %{app_path}/dicom_gw
%{app_path}/dicom_gw/*
%dir %{app_path}/migrations
%{app_path}/migrations/*
%{app_path}/setup.py
%{app_path}/requirements.txt
%{app_path}/README.md
%{app_path}/alembic.ini
%{app_path}/pytest.ini

# Configuration files
%config(noreplace) %{config_path}/config.yaml.example
%config(noreplace) %{config_path}/config.yaml
%dir %{config_path}/tls

# Systemd service files
%{_unitdir}/dicom-gw-api.service
%{_unitdir}/dicom-gw-queue-worker.service
%{_unitdir}/dicom-gw-forwarder-worker.service
%{_unitdir}/dicom-gw-dbpool-worker.service
%{_unitdir}/dicom-gw-scp.service
%{_unitdir}/dicom-gw-autoscaler.service
%{_unitdir}/dicom-gw.target
# Template service files for horizontal scaling
%{_unitdir}/dicom-gw-queue-worker@.service
%{_unitdir}/dicom-gw-forwarder-worker@.service
%{_unitdir}/dicom-gw-dbpool-worker@.service

# Scripts
%dir %{app_path}/scripts
%{app_path}/scripts/build-rpm.sh
%{app_path}/scripts/check-rpm-build.sh
%{app_path}/scripts/check-user.sh
%{app_path}/scripts/cleanup-storage.sh
%{app_path}/scripts/create-admin-user.sh
%{app_path}/scripts/debug-settings.sh
%{app_path}/scripts/generate-encryption-key.sh
%{app_path}/scripts/generate-self-signed-cert.sh
%{app_path}/scripts/install-systemd-services.sh
%{app_path}/scripts/reset-admin-password.sh
%{app_path}/scripts/scale-workers.sh
%{app_path}/scripts/setup-build-deps.sh
%{app_path}/scripts/setup-letsencrypt.sh
%{app_path}/scripts/setup-luks-encryption.sh
%{app_path}/scripts/setup-nginx.sh
%{app_path}/scripts/setup-storage-layout.sh
%{app_path}/scripts/test-db-connection.sh
%{app_path}/scripts/unlock-user.sh
%{app_path}/scripts/verify-rpm-contents.sh
%{app_path}/scripts/verify-storage-layout.sh

# Nginx configuration
%config(noreplace) %{_sysconfdir}/nginx/conf.d/dicom-gateway.conf

# Logrotate configuration
%config(noreplace) %{_sysconfdir}/logrotate.d/dicom-gateway

# Documentation
%doc %{_docdir}/%{name}-%{version}

# Data directories (created but not owned by package)
%dir %{data_path}
%dir %{log_path}

%changelog
* Mon Jan 06 2025 DICOM Gateway Team <noreply@example.com> - 0.1.0-1
- Initial release of DICOM Gateway
- Byte-preserving DICOM I/O
- PostgreSQL-backed job queue
- Vue.js 3 frontend
- Prometheus metrics
- TLS/SSL support with Let's Encrypt
- RBAC and audit logging

