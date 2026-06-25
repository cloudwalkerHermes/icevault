"""
icevault.secrets_registry -- the only place a secret name exists as a
string literal in this codebase.

Every secret is exposed as a named function, never a free-text string
key. A misspelled or drifted name is a hard ImportError at the call
site, not a silent new variant living alongside the real one. This
file IS the canonical, human-readable list of every secret icevault
manages -- read it, don't grep for string literals scattered
elsewhere.

Adding a new secret:
  1. Run `python3 collision_check.py get_your_new_name` first -- it
     checks your proposed name against every name already below,
     normalized (case/underscores stripped), and refuses if it's a
     near-duplicate of something that already exists.
  2. Add the real value via `python3 manage_secrets.py` (handles
     first-time key/file creation, then opens your editor) -- a human
     does this step, never an agent; see README.md.
  3. Add the getter function here, following the existing pattern.
  4. Verify blind: call the getter, confirm it returns something
     truthy, without ever printing/logging the actual value.
"""
from pathlib import Path
from vault_core import decrypt_value

_DEMO_SECRETS_FILE = Path(__file__).parent / "demo" / "demo_secrets.enc.yaml"
_DEMO_AGE_KEY_FILE = Path(__file__).parent / "demo" / "demo_age_key.txt"


def get_example_key() -> str:
    """
    Template/example only -- demonstrates the pattern, reading from
    demo/demo_secrets.enc.yaml (its own demo key, its own demo file --
    deliberately separate from the real secrets.enc.yaml so adding
    real secrets can never collide with or overwrite this demo).
    Replace or remove once real secrets are added.
    """
    return decrypt_value("EXAMPLE_KEY", secrets_file=_DEMO_SECRETS_FILE, age_key_file=_DEMO_AGE_KEY_FILE)


def get_oddsapi_key() -> str:
    """OddsAPI paid-plan key, used by KalshiHermes's odds scrapers."""
    return decrypt_value("ODDSAPI_KEY")
