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
  2. Add the real value to secrets.enc.yaml via `sops secrets.enc.yaml`
     (opens decrypted in your editor, re-encrypts on save) -- a human
     does this step, never an agent; see requirements.md.
  3. Add the getter function here, following the existing pattern.
  4. Verify blind: call the getter, confirm it returns something
     truthy, without ever printing/logging the actual value.
"""
from vault_core import decrypt_value


def get_example_key() -> str:
    """
    Template/example only -- demonstrates the pattern. Not a real
    secret. Replace or remove once real secrets are added; this
    exists so the mechanism is provably exercised end-to-end before
    anything real depends on it.
    """
    return decrypt_value("EXAMPLE_KEY")
