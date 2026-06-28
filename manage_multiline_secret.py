#!/usr/bin/env python3
"""
icevault.manage_multiline_secret -- human-facing helper for multi-line
secrets (PEM keys, certs, anything with embedded newlines).

Each secret gets its own standalone encrypted file under multiline/,
named after the secret (multiline/<NAME>.enc), via sops' binary mode:
the whole file is one raw opaque blob, no YAML/JSON structure, no
indentation rules -- nothing to get wrong. A botched edit on one
secret can never touch or corrupt another, since they're never parsed
or re-encrypted together.

This exists specifically because hand-indenting a YAML literal block
scalar in manage_secrets.py's interactive editor is what broke on a
real attempt -- see README.md. The fix removes the YAML structure
entirely; it does NOT remove the human from typing the value in. You
still open a real editor and paste your secret in by hand, exactly
like manage_secrets.py -- just into a blank file with nothing to
format, instead of a YAML document with indentation rules.

The secret name is a required argument, picked by whoever runs this
(you, or an agent telling you the exact command to run) -- same
division of labor as manage_secrets.py: a human decides or is told
the name, an agent never sees or types the value.

Usage:
    python3 manage_multiline_secret.py KEY_NAME
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from vault_core import MULTILINE_DIR, AGE_KEY_FILE, _sops_binary, ensure_key


def main():
    if len(sys.argv) != 2:
        print("usage: python3 manage_multiline_secret.py <KEY_NAME>", file=sys.stderr)
        print("example: python3 manage_multiline_secret.py KALSHI_PEM", file=sys.stderr)
        sys.exit(2)

    key_name = sys.argv[1]
    MULTILINE_DIR.mkdir(exist_ok=True)
    target = MULTILINE_DIR / f"{key_name}.enc"

    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)
    pubkey = ensure_key()

    print(f"About to enter the value for: {key_name}")
    print(f"Will be saved to: {target}")
    try:
        input("Press Enter to continue, Ctrl+C to abort... ")
    except KeyboardInterrupt:
        print("\nAborted -- nothing was created or changed.")
        sys.exit(1)

    if not target.exists():
        # Encrypt a truly empty file first, then reopen -- avoids sops'
        # own "Welcome to SOPS!" one-line scaffold that appears on direct
        # interactive creation. Confirmed empirically: this two-step
        # path gives a genuinely blank editor buffer instead.
        tmp = Path(tempfile.mktemp())
        tmp.touch()
        try:
            with open(target, "w") as out:
                result = subprocess.run(
                    [_sops_binary(), "--age", pubkey, "--input-type", "binary", "-e", str(tmp)],
                    stdout=out, stderr=subprocess.PIPE, text=True, env=env,
                )
            if result.returncode != 0:
                target.unlink(missing_ok=True)
                print(f"icevault: failed to create {target.name}: {result.stderr.strip()}", file=sys.stderr)
                sys.exit(1)
        finally:
            tmp.unlink()
        print(f"Created. Opening it now -- paste your secret in exactly as it exists,")
        print(f"no formatting needed, then save and close.\n")

    if 'EDITOR' not in env and sys.platform == 'win32':
        env['EDITOR'] = 'notepad'
    result = subprocess.run([_sops_binary(), "--input-type", "binary", str(target)], env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
