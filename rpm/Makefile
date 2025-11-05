# Makefile for building DICOM Gateway RPM
# Usage: make rpm

PACKAGE_NAME = dicom-gateway
VERSION = 0.1.0
RELEASE = 1
DIST = $(shell rpm --eval '%{?dist}')
BUILD_DIR = $(HOME)/rpmbuild
SOURCE_DIR = $(shell pwd)/..
TARBALL = $(PACKAGE_NAME)-$(VERSION).tar.gz

.PHONY: clean setup build rpm srpm install

all: rpm

setup:
	@echo "Setting up RPM build environment..."
	@mkdir -p $(BUILD_DIR)/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
	@echo "Build directory: $(BUILD_DIR)"

tarball: setup
	@echo "Creating source tarball..."
	@cd $(SOURCE_DIR) && tar --exclude='.git' \
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
		-czf $(BUILD_DIR)/SOURCES/$(TARBALL) \
		--transform 's,^\.,$(PACKAGE_NAME)-$(VERSION),' \
		.

spec: setup
	@echo "Copying spec file..."
	@if [ -f $(PACKAGE_NAME).spec ]; then \
		cp $(PACKAGE_NAME).spec $(BUILD_DIR)/SPECS/; \
	else \
		cp rpm/$(PACKAGE_NAME).spec $(BUILD_DIR)/SPECS/; \
	fi

build: setup tarball spec
	@echo "Building RPM..."
	@rpmbuild -ba $(BUILD_DIR)/SPECS/$(PACKAGE_NAME).spec \
		--define "_topdir $(BUILD_DIR)" \
		--define "version $(VERSION)" \
		--define "release $(RELEASE)"

rpm: build
	@echo "RPM built successfully!"
	@echo "RPM location: $(BUILD_DIR)/RPMS/noarch/$(PACKAGE_NAME)-$(VERSION)-$(RELEASE)$(DIST).noarch.rpm"
	@ls -lh $(BUILD_DIR)/RPMS/noarch/$(PACKAGE_NAME)-$(VERSION)-$(RELEASE)$(DIST).noarch.rpm

srpm: setup tarball spec
	@echo "Building source RPM..."
	@rpmbuild -bs $(BUILD_DIR)/SPECS/$(PACKAGE_NAME).spec \
		--define "_topdir $(BUILD_DIR)" \
		--define "version $(VERSION)" \
		--define "release $(RELEASE)"
	@echo "SRPM location: $(BUILD_DIR)/SRPMS/$(PACKAGE_NAME)-$(VERSION)-$(RELEASE)$(DIST).src.rpm"

install: rpm
	@echo "Installing RPM..."
	@sudo rpm -Uvh $(BUILD_DIR)/RPMS/noarch/$(PACKAGE_NAME)-$(VERSION)-$(RELEASE)$(DIST).noarch.rpm

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR)/BUILD/$(PACKAGE_NAME)-$(VERSION)
	@rm -rf $(BUILD_DIR)/BUILDROOT/$(PACKAGE_NAME)-$(VERSION)-$(RELEASE)$(DIST).noarch
	@rm -f $(BUILD_DIR)/SOURCES/$(TARBALL)
	@rm -f $(BUILD_DIR)/RPMS/noarch/$(PACKAGE_NAME)-*.rpm
	@rm -f $(BUILD_DIR)/SRPMS/$(PACKAGE_NAME)-*.rpm

distclean: clean
	@echo "Removing build directory..."
	@rm -rf $(BUILD_DIR)

help:
	@echo "DICOM Gateway RPM Build System"
	@echo ""
	@echo "Targets:"
	@echo "  make rpm      - Build binary RPM"
	@echo "  make srpm     - Build source RPM"
	@echo "  make install  - Build and install RPM"
	@echo "  make clean    - Clean build artifacts"
	@echo "  make distclean - Remove build directory"
	@echo ""
	@echo "RPM will be created in: $(BUILD_DIR)/RPMS/noarch/"

