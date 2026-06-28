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
import subprocess
import sys
import tempfile
from pathlib import Path

from vault_core import ICEVAULT_DIR, AGE_KEY_FILE, SECRETS_FILE, _sops_binary, ensure_key, _windows_editor

# sops' own default scaffold for a brand-new file is a generic
# "Welcome to SOPS!" template with example_key/example_array/etc --
# confusing on a first encounter and has nothing to do with icevault.
# We avoid it entirely by encrypting our own clean starter content
# instead of letting sops seed the file itself.
_STARTER_CONTENT = (
    "# Replace the line below with your real secret(s), one per line,\n"
    "# in the form KEY_NAME: value -- then save and close.\n"
    "REPLACE_ME: replace-this-placeholder-with-a-real-value\n"
)


def _create_with_clean_starter(pubkey: str, env: dict) -> int:
    """Encrypts our own minimal starter content instead of letting sops
    seed the file with its generic 'Welcome to SOPS!' example template
    (example_key/example_array/example_booleans -- confusing on a
    first encounter, nothing to do with icevault)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp.write(_STARTER_CONTENT)
        tmp_path = tmp.name
    try:
        with open(SECRETS_FILE, "w") as out:
            result = subprocess.run(
                [_sops_binary(), "--age", pubkey, "-e", tmp_path],
                stdout=out, stderr=subprocess.PIPE, text=True, env=env,
            )
        if result.returncode != 0:
            SECRETS_FILE.unlink(missing_ok=True)
            raise RuntimeError(f"icevault: failed to create {SECRETS_FILE.name}: {result.stderr.strip()}")
    finally:
        os.unlink(tmp_path)
    return result.returncode


def main():
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)
    pubkey = ensure_key()

    if not SECRETS_FILE.exists():
        print(f"\n{SECRETS_FILE.name} doesn't exist yet -- creating it now.")
        _create_with_clean_starter(pubkey, env)
        print("Created. Opening it now -- replace the placeholder line with your")
        print("real secret(s), one per line, as KEY_NAME: value, then save and close.\n")

    if 'EDITOR' not in env and sys.platform == 'win32':
        env['EDITOR'] = _windows_editor()
    result = subprocess.run([_sops_binary(), str(SECRETS_FILE)], env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
