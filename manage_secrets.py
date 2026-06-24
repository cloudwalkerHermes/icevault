#!/usr/bin/env python3
"""
icevault.manage_secrets -- human-facing helper for the real
secrets.enc.yaml.

Handles the two fiddly parts (first-time key generation, first-time
file creation with the right --age recipient) automatically. The
actual editing -- typing or pasting a real secret value -- always
opens your real $EDITOR interactively via plain `sops`. This script
never sees, stores, or passes along a plaintext secret value itself;
it only ever handles the *mechanics* of getting you to your editor
with the right key in scope.

Usage:
    python3 manage_secrets.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from vault_core import ICEVAULT_DIR, BIN_DIR, _sops_binary, _is_windows

AGE_KEY_FILE = ICEVAULT_DIR / "age_key.txt"
SECRETS_FILE = ICEVAULT_DIR / "secrets.enc.yaml"


def _age_keygen_binary() -> str:
    local = BIN_DIR / ("age-keygen.exe" if _is_windows() else "age-keygen")
    if local.exists():
        return str(local)
    on_path = shutil.which("age-keygen")
    if on_path:
        return on_path
    raise RuntimeError("icevault: age-keygen not found. Run `python3 bootstrap.py` first.")


def ensure_key() -> str:
    """Returns the public key for AGE_KEY_FILE, generating a new
    keypair there first if one doesn't exist yet."""
    if not AGE_KEY_FILE.exists():
        print(f"No age key found at {AGE_KEY_FILE} -- generating one now.")
        result = subprocess.run(
            [_age_keygen_binary(), "-o", str(AGE_KEY_FILE)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"icevault: key generation failed: {result.stderr.strip()}")
        if not _is_windows():
            AGE_KEY_FILE.chmod(0o600)
        print(f"Generated a new key at {AGE_KEY_FILE}.")
        print("IMPORTANT: back this up somewhere safe (e.g. your personal password manager).")
        print("Losing this file means losing access to every secret encrypted with it --")
        print("there is no recovery without it. It is gitignored and will never be committed.")

    lines = [l for l in AGE_KEY_FILE.read_text().splitlines() if "public key:" in l]
    if not lines:
        raise RuntimeError(f"icevault: {AGE_KEY_FILE} exists but has no recognizable public key line.")
    return lines[0].split()[-1]


def main():
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)
    pubkey = ensure_key()

    if not SECRETS_FILE.exists():
        print(f"\n{SECRETS_FILE.name} doesn't exist yet -- creating it now.")
        print("Your editor will open. Add your first secret as:")
        print("  KEY_NAME: the-real-value")
        print("then save and close.\n")
        result = subprocess.run([_sops_binary(), "--age", pubkey, str(SECRETS_FILE)], env=env)
    else:
        print(f"Opening {SECRETS_FILE.name} for editing...")
        result = subprocess.run([_sops_binary(), str(SECRETS_FILE)], env=env)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
