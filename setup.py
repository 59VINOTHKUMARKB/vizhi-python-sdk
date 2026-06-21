"""Backward-compatible setup.py — all metadata lives in pyproject.toml.

This file exists so that older pip versions (< 21.3) that don't fully
support PEP 621 / pyproject.toml can still install the package from
GitHub:

    pip install git+https://github.com/Gopinathv19/vizhi-python-sdk.git

Modern pip (>= 21.3) reads pyproject.toml directly and ignores this file.
"""

from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent

setup(
    name="vizhi-sdk",
    version="0.1.0",
    description="Python SDK for the Vizhi AI gateway.",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="Vizhi",
    author_email="gopinathv19@gmail.com",
    url="https://github.com/Gopinathv19/vizhi-python-sdk",
    project_urls={
        "Repository": "https://github.com/Gopinathv19/vizhi-python-sdk",
        "Issues": "https://github.com/Gopinathv19/vizhi-python-sdk/issues",
    },
    license="MIT",
    packages=find_packages(include=["vizhi_sdk", "vizhi_sdk.*"]),
    install_requires=[],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
