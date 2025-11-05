"""Setup script for DICOM Gateway."""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="dicom-gateway",
    version="0.1.0",
    description="Lightweight DICOM Gateway for receiving and forwarding medical imaging studies",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Simon MED IMAGING",
    python_requires=">=3.11",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        # Core dependencies from requirements.txt
        # Note: Install from requirements.txt for exact versions
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "dicom-gw-api=dicom_gw.api.main:main",
            "dicom-gw-queue=dicom_gw.workers.queue_worker:main",
            "dicom-gw-forwarder=dicom_gw.workers.forwarder_worker:main",
            "dicom-gw-dbpool=dicom_gw.workers.dbpool_worker:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)

