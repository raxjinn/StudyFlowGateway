"""TLS/SSL certificate management and Let's Encrypt automation."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class CertificateManager:
    """Manages TLS certificates including Let's Encrypt provisioning."""
    
    def __init__(
        self,
        cert_dir: str = "/etc/dicom-gw/tls",
        cert_file: str = "cert.pem",
        key_file: str = "key.pem",
        ca_file: Optional[str] = "ca.pem",
    ):
        """Initialize certificate manager.
        
        Args:
            cert_dir: Directory for certificate files
            cert_file: Certificate file name
            key_file: Private key file name
            ca_file: CA certificate file name (optional)
        """
        self.cert_dir = Path(cert_dir)
        self.cert_file = self.cert_dir / cert_file
        self.key_file = self.cert_dir / key_file
        self.ca_file = self.cert_dir / ca_file if ca_file else None
        
        # Ensure directory exists
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        self.cert_dir.chmod(0o750)
    
    def _run_command(self, command: list[str], check: bool = True) -> Tuple[int, str, str]:
        """Run a shell command.
        
        Args:
            command: Command and arguments
            check: If True, raise exception on non-zero exit code
        
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check,
                timeout=300,  # 5 minute timeout
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            logger.error("Command timed out: %s", " ".join(command))
            raise
        except subprocess.CalledProcessError as e:
            logger.error("Command failed: %s", e.stderr)
            raise
    
    def provision_letsencrypt(
        self,
        domain: str,
        email: str,
        webroot_path: Optional[str] = None,
        staging: bool = False,
    ) -> bool:
        """Provision Let's Encrypt certificate using certbot.
        
        Args:
            domain: Domain name for certificate
            email: Email address for Let's Encrypt notifications
            webroot_path: Web root path for HTTP-01 challenge (optional)
            staging: Use Let's Encrypt staging environment (for testing)
        
        Returns:
            True if certificate was provisioned successfully
        """
        if not self._check_certbot_installed():
            logger.error("certbot is not installed. Install with: dnf install certbot")
            return False
        
        # Prepare certbot command
        certbot_cmd = ["certbot", "certonly"]
        
        if staging:
            certbot_cmd.append("--staging")
        
        certbot_cmd.extend([
            "--non-interactive",
            "--agree-tos",
            "--email", email,
            "--keep-until-expiring",
        ])
        
        if webroot_path:
            certbot_cmd.extend([
                "--webroot",
                "--webroot-path", webroot_path,
                "-d", domain,
            ])
        else:
            # Standalone mode (requires port 80 to be available)
            certbot_cmd.extend([
                "--standalone",
                "-d", domain,
            ])
        
        try:
            logger.info("Provisioning Let's Encrypt certificate for %s", domain)
            returncode, stdout, stderr = self._run_command(certbot_cmd)
            
            if returncode == 0:
                # Certbot stores certificates in /etc/letsencrypt/live/domain/
                letsencrypt_cert = Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
                letsencrypt_key = Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
                
                if letsencrypt_cert.exists() and letsencrypt_key.exists():
                    # Copy certificates to our cert directory
                    self._copy_certificate(letsencrypt_cert, letsencrypt_key)
                    logger.info("Let's Encrypt certificate provisioned successfully")
                    return True
                else:
                    logger.error("Certificate files not found after certbot execution")
                    return False
            else:
                logger.error("certbot failed: %s", stderr)
                return False
        
        except Exception as e:
            logger.error("Failed to provision Let's Encrypt certificate: %s", e, exc_info=True)
            return False
    
    def _check_certbot_installed(self) -> bool:
        """Check if certbot is installed.
        
        Returns:
            True if certbot is available
        """
        try:
            self._run_command(["which", "certbot"], check=False)
            returncode, _, _ = self._run_command(["certbot", "--version"], check=False)
            return returncode == 0
        except Exception:
            return False
    
    def _copy_certificate(self, cert_path: Path, key_path: Path) -> None:
        """Copy certificate and key files to our directory.
        
        Args:
            cert_path: Source certificate file path
            key_path: Source private key file path
        """
        import shutil
        
        # Copy certificate
        shutil.copy(cert_path, self.cert_file)
        self.cert_file.chmod(0o644)
        
        # Copy private key
        shutil.copy(key_path, self.key_file)
        self.key_file.chmod(0o600)  # Private key should be readable only by owner
        
        logger.info("Certificates copied to %s", self.cert_dir)
    
    def upload_certificate(
        self,
        cert_content: bytes,
        key_content: bytes,
        ca_content: Optional[bytes] = None,
    ) -> bool:
        """Upload and save certificate files.
        
        Args:
            cert_content: Certificate file content
            key_content: Private key file content
            ca_content: CA certificate file content (optional)
        
        Returns:
            True if certificates were saved successfully
        """
        try:
            # Validate certificate format (basic check)
            if not cert_content.startswith(b"-----BEGIN CERTIFICATE-----"):
                logger.error("Invalid certificate format")
                return False
            
            if not key_content.startswith(b"-----BEGIN"):
                logger.error("Invalid private key format")
                return False
            
            # Backup existing certificates if they exist
            if self.cert_file.exists():
                backup_cert = self.cert_file.with_suffix(".pem.backup")
                backup_cert.write_bytes(self.cert_file.read_bytes())
                logger.info("Backed up existing certificate to %s", backup_cert)
            
            if self.key_file.exists():
                backup_key = self.key_file.with_suffix(".pem.backup")
                backup_key.write_bytes(self.key_file.read_bytes())
                logger.info("Backed up existing key to %s", backup_key)
            
            # Write new certificates
            self.cert_file.write_bytes(cert_content)
            self.cert_file.chmod(0o644)
            
            self.key_file.write_bytes(key_content)
            self.key_file.chmod(0o600)
            
            if ca_content:
                if self.ca_file:
                    self.ca_file.write_bytes(ca_content)
                    self.ca_file.chmod(0o644)
            
            logger.info("Certificates uploaded and saved successfully")
            return True
        
        except Exception as e:
            logger.error("Failed to upload certificates: %s", e, exc_info=True)
            return False
    
    def get_certificate_info(self) -> Optional[dict]:
        """Get information about the current certificate.
        
        Returns:
            Dictionary with certificate information or None if not found
        """
        if not self.cert_file.exists():
            return None
        
        try:
            # Use openssl to get certificate info
            returncode, stdout, stderr = self._run_command(
                ["openssl", "x509", "-in", str(self.cert_file), "-noout", "-text", "-dates"],
                check=False
            )
            
            if returncode != 0:
                logger.error("Failed to read certificate: %s", stderr)
                return None
            
            # Parse certificate info
            info = {
                "cert_file": str(self.cert_file),
                "key_file": str(self.key_file),
                "exists": True,
            }
            
            # Extract dates
            for line in stdout.split("\n"):
                if "notBefore" in line:
                    info["valid_from"] = line.split("=", 1)[1].strip()
                elif "notAfter" in line:
                    info["valid_until"] = line.split("=", 1)[1].strip()
                elif "Subject:" in line:
                    info["subject"] = line.split(":", 1)[1].strip()
                elif "Issuer:" in line:
                    info["issuer"] = line.split(":", 1)[1].strip()
            
            # Check if certificate is expired or expiring soon
            if "valid_until" in info:
                try:
                    from dateutil import parser
                    expiry = parser.parse(info["valid_until"])
                    days_until_expiry = (expiry - datetime.now()).days
                    info["days_until_expiry"] = days_until_expiry
                    info["expires_soon"] = days_until_expiry < 30
                    info["expired"] = days_until_expiry < 0
                except Exception:
                    pass
            
            return info
        
        except Exception as e:
            logger.error("Failed to get certificate info: %s", e, exc_info=True)
            return None
    
    def renew_certificate(self, domain: Optional[str] = None) -> bool:
        """Renew Let's Encrypt certificate.
        
        Args:
            domain: Domain name (optional, if None, tries to renew all)
        
        Returns:
            True if renewal was successful
        """
        if not self._check_certbot_installed():
            logger.error("certbot is not installed")
            return False
        
        certbot_cmd = ["certbot", "renew", "--quiet", "--no-self-upgrade"]
        
        if domain:
            certbot_cmd.extend(["--cert-name", domain])
        
        try:
            logger.info("Renewing Let's Encrypt certificate...")
            returncode, stdout, stderr = self._run_command(certbot_cmd)
            
            if returncode == 0:
                # If certificate was renewed, copy it
                if domain:
                    letsencrypt_cert = Path(f"/etc/letsencrypt/live/{domain}/fullchain.pem")
                    letsencrypt_key = Path(f"/etc/letsencrypt/live/{domain}/privkey.pem")
                    
                    if letsencrypt_cert.exists() and letsencrypt_key.exists():
                        self._copy_certificate(letsencrypt_cert, letsencrypt_key)
                        logger.info("Certificate renewed and copied successfully")
                        return True
                
                logger.info("Certificate renewal completed")
                return True
            else:
                logger.error("Certificate renewal failed: %s", stderr)
                return False
        
        except Exception as e:
            logger.error("Failed to renew certificate: %s", e, exc_info=True)
            return False


def get_certificate_manager(
    cert_dir: Optional[str] = None,
) -> CertificateManager:
    """Get certificate manager instance.
    
    Args:
        cert_dir: Optional certificate directory path
    
    Returns:
        CertificateManager instance
    """
    if cert_dir:
        return CertificateManager(cert_dir=cert_dir)
    
    # Default to /etc/dicom-gw/tls
    return CertificateManager()

