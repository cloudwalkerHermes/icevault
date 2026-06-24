#!/usr/bin/env python3
"""
icevault.bootstrap -- one-time per-environment setup.

Downloads sops + age into ./bin/ for the current platform. Idempotent
(skips anything already present). No sudo/admin required -- these are
user-space binaries, not system installs.

Versions and download URLs are pinned to what's been independently
validated across all 4 target platforms (see requirements.md):
  age  v1.3.1
  sops v3.13.1

Run this once per environment:
    python3 bootstrap.py
"""
import os
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

AGE_VERSION = "1.3.1"
SOPS_VERSION = "3.13.1"

ICEVAULT_DIR = Path(__file__).parent
BIN_DIR = ICEVAULT_DIR / "bin"


def _platform_key():
    """Returns (os_name, arch) using the same naming as the validated
    release assets in requirements.md."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64"):
        arch = "amd64"
    else:
        raise RuntimeError(f"icevault: unrecognized architecture '{machine}' -- not one of the 4 validated platforms")

    if system == "linux":
        return "linux", arch
    elif system == "windows":
        if arch != "amd64":
            raise RuntimeError(f"icevault: Windows arch '{arch}' not validated -- only windows-amd64 has been tested")
        return "windows", arch
    else:
        raise RuntimeError(f"icevault: unrecognized OS '{system}' -- not one of the 4 validated platforms (linux, windows)")


def _download(url: str, dest: Path):
    print(f"  downloading {url}")
    urllib.request.urlretrieve(url, dest)


def _make_executable(path: Path):
    if platform.system().lower() != "windows":
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def bootstrap():
    os_name, arch = _platform_key()
    BIN_DIR.mkdir(exist_ok=True)

    age_bin = BIN_DIR / ("age.exe" if os_name == "windows" else "age")
    sops_bin = BIN_DIR / ("sops.exe" if os_name == "windows" else "sops")

    if age_bin.exists() and sops_bin.exists():
        print(f"icevault: bin/ already populated for {os_name}-{arch}, nothing to do.")
        return

    print(f"icevault bootstrap: platform detected as {os_name}-{arch}")

    # --- age ---
    if not age_bin.exists():
        staging = BIN_DIR / "_age_staging"
        staging.mkdir(exist_ok=True)
        if os_name == "windows":
            url = f"https://github.com/FiloSottile/age/releases/download/v{AGE_VERSION}/age-v{AGE_VERSION}-windows-{arch}.zip"
            archive = BIN_DIR / "age_dl.zip"
            _download(url, archive)
            with zipfile.ZipFile(archive) as z:
                z.extractall(staging)
            archive.unlink()
            extracted = staging / "age" / "age.exe"
            extracted_keygen = staging / "age" / "age-keygen.exe"
        else:
            url = f"https://github.com/FiloSottile/age/releases/download/v{AGE_VERSION}/age-v{AGE_VERSION}-{os_name}-{arch}.tar.gz"
            archive = BIN_DIR / "age_dl.tar.gz"
            _download(url, archive)
            with tarfile.open(archive) as t:
                t.extractall(staging, filter="data")
            archive.unlink()
            extracted = staging / "age" / "age"
            extracted_keygen = staging / "age" / "age-keygen"

        keygen_bin = BIN_DIR / ("age-keygen.exe" if os_name == "windows" else "age-keygen")
        extracted.rename(age_bin)
        extracted_keygen.rename(keygen_bin)
        _make_executable(age_bin)
        _make_executable(keygen_bin)
        import shutil as _shutil
        _shutil.rmtree(staging)
        print(f"  age -> {age_bin}")

    # --- sops ---
    if not sops_bin.exists():
        if os_name == "windows":
            url = f"https://github.com/getsops/sops/releases/download/v{SOPS_VERSION}/sops-v{SOPS_VERSION}.{arch}.exe"
        else:
            url = f"https://github.com/getsops/sops/releases/download/v{SOPS_VERSION}/sops-v{SOPS_VERSION}.{os_name}.{arch}"
        _download(url, sops_bin)
        _make_executable(sops_bin)
        print(f"  sops -> {sops_bin}")

    print("icevault bootstrap complete.")


if __name__ == "__main__":
    try:
        bootstrap()
    except Exception as e:
        print(f"icevault bootstrap FAILED: {e}", file=sys.stderr)
        sys.exit(1)
