"""
icevault.vault_core -- low-level sops+age wrapper.

Not meant to be imported directly by consumers of icevault -- use
secrets_registry.py's named getter functions instead. This module
exists so secrets_registry.py stays a flat list of simple, named
functions with no encryption mechanics mixed in.

Design constraint this module exists to honor: decryption happens
per-value, on demand, via `sops --extract`, never by decrypting the
whole file into memory/disk as a side effect. The plaintext of any
one secret only exists transiently, in the calling process's memory,
for the duration of one lookup.
"""
import platform
import shutil
import subprocess
from pathlib import Path

ICEVAULT_DIR = Path(__file__).parent
BIN_DIR = ICEVAULT_DIR / "bin"
SECRETS_FILE = ICEVAULT_DIR / "secrets.enc.yaml"


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _sops_binary() -> str:
    """Resolve the sops binary: prefer the bootstrapped local copy,
    fall back to PATH if someone has it installed system-wide."""
    local = BIN_DIR / ("sops.exe" if _is_windows() else "sops")
    if local.exists():
        return str(local)
    on_path = shutil.which("sops")
    if on_path:
        return on_path
    raise RuntimeError(
        "icevault: sops binary not found. Run `python3 bootstrap.py` once "
        "in this directory to fetch it (no sudo/admin required)."
    )


def decrypt_value(name: str, secrets_file: Path = SECRETS_FILE) -> str:
    """
    Decrypt and return exactly one value from an encrypted YAML file by
    its top-level key name. Defaults to the real secrets.enc.yaml; the
    demo getter passes demo/demo_secrets.enc.yaml explicitly instead --
    these are deliberately separate files so a real secrets.enc.yaml
    never collides with or overwrites the demo.

    Raises clearly (never returns None/empty silently) if the file,
    the key, or the binary is missing.
    """
    if not secrets_file.exists():
        raise FileNotFoundError(
            f"icevault: {secrets_file} does not exist. Has it been created yet? "
            f"See README.md / the 'adding a new secret' procedure."
        )

    result = subprocess.run(
        [_sops_binary(), "--extract", f'["{name}"]', "-d", str(secrets_file)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"icevault: failed to decrypt '{name}' from {secrets_file.name}: "
            f"{result.stderr.strip()}"
        )
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(
            f"icevault: decrypted '{name}' but got an empty value -- "
            f"check the key actually exists in {secrets_file.name}"
        )
    return value
