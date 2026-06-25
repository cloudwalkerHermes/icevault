# icevault

A "cold wallet" for application secrets: encrypted at rest with [`age`](https://github.com/FiloSottile/age) via [`sops`](https://github.com/getsops/sops), decrypted locally and on demand, never sent over a network, never sitting in git history in plaintext, never injected ambiently into a process by something external to the code itself.

Every secret is exposed as a **named Python function**, not a free-text string key — a misspelled or drifted name is a hard `ImportError`, not a silent new variant of the same secret living alongside the real one.

## Why this exists

Built after a long look at cloud secrets managers (Bitwarden Secrets Manager specifically) turned up three compounding problems for a small, multi-environment, agent-operated setup: ambient global injection with no per-process scoping (a new secret's name could silently collide with something unrelated already in use), a hard dependency on *how* a process gets launched (manual scripts vs. cron-launched ones behave differently with no enforcement), and the tool's own documentation stating it isn't really meant for single-machine setups in the first place. icevault's design specifically avoids all three: nothing is ambient, nothing depends on launch method, nothing touches a network.

## Quickstart

```bash
python3 bootstrap.py   # downloads sops + age into bin/ for your platform, no sudo/admin needed
```

Try the demo (proves the mechanism works without touching anything real):

```bash
SOPS_AGE_KEY_FILE=demo/demo_age_key.txt python3 -c "from secrets_registry import get_example_key; print(bool(get_example_key()))"
```
Should print `True`. The demo key/file only protect a fake placeholder value — safe to commit, safe to ignore, never used for anything real.

## Setting up your own real vault (the "human bridge" step)

This is the one part of icevault that's deliberately **not automatable** — an agent should never see, generate, or type a real secret value. That's a human-only action, on purpose.

```bash
python3 manage_secrets.py
```

First run: generates a real `age` keypair at `age_key.txt` (gitignored — never committed) and creates `secrets.enc.yaml` for you, opening it in your `$EDITOR` so you can add your first secret as `KEY_NAME: the-real-value`. Save and close.

Every run after that: just opens the existing `secrets.enc.yaml` in your editor (decrypted), so you can add or change values. Saving re-encrypts automatically — `sops` handles that, you never touch ciphertext directly.

**⚠️ You must save and exit your editor cleanly for the encryption to actually fire.** `sops` decrypts to a temporary file, hands it to your `$EDITOR`, and only re-encrypts back into `secrets.enc.yaml` on a clean exit. If the editor exits uncleanly (a crash, a force-kill, an editor error) the real file is **not** updated — your change silently never happened. If you're not sure your last edit actually landed, check whether the key name you expect shows up: `grep -E "^[A-Za-z_]+:" secrets.enc.yaml` (safe to run — that only shows key *names* in cleartext, values stay encrypted). If it's not there, just redo the entry.

**Back up `age_key.txt` somewhere safe the moment it's generated** (your personal password manager, not this repo). There's no recovery without it — lose the key, lose access to everything encrypted with it. This is the literal cold-wallet-seed-phrase tradeoff: maximum security, zero forgiveness for losing the key.

### Adding a secret an agent will use

1. **Collision check first** — `python3 collision_check.py get_your_proposed_name`. If it flags a near-duplicate of something that already exists, reuse that instead of adding a new one.
2. **You add the real value** — `python3 manage_secrets.py`, add `KEY_NAME: value` in the editor, save. The agent should tell you exactly what key name to use; it should never type the value itself or ask you to paste it anywhere except directly into your own editor session.
3. **The agent adds the getter** in `secrets_registry.py` — references only the key *name*, never the value:
   ```python
   def get_your_new_thing() -> str:
       return decrypt_value("KEY_NAME")
   ```
4. **Verify blind** — call the getter, confirm it returns something truthy, without ever printing or logging the actual value.

## How it works under the hood

- `bootstrap.py` — fetches the right `sops`/`age` binaries for your platform into `bin/` (gitignored, large and platform-specific). Idempotent, no sudo/admin.
- `vault_core.py` — the low-level decrypt wrapper. Calls `sops --extract` to pull exactly one value at a time; never decrypts the whole file, never holds plaintext anywhere but transiently in the calling process's memory.
- `secrets_registry.py` — the actual named getters. This file *is* the human-readable, canonical list of every secret icevault manages — read it, don't grep for string literals scattered elsewhere.
- `collision_check.py` — normalized-name collision detector (case/underscores stripped before comparing), run before adding any new getter.
- `manage_secrets.py` — the human-facing helper for the real vault: auto-generates the key and creates the file on first use, otherwise just opens it for editing. Never touches a plaintext value itself.
- `secrets.enc.yaml` / `age_key.txt` — your real vault and key. Gitignored, created locally, never committed. (Not present in a fresh clone — that's correct; `manage_secrets.py` creates them.)
- `demo/` — a self-contained example proving the mechanism works, safe to commit since it only protects a fake value.

## Design rule: this lives at `<project_root>/code/icevault/`, always

If you're integrating icevault into another project, clone it as a direct subdirectory at `<that project's>/code/icevault/` — not a pip-installed package, not a sibling directory, not anywhere else. This is deliberate: it means any Claude/Hermes instance operating with that project's `code/` folder as its working root can find and use it with zero environment configuration, no `PYTHONPATH`, no per-install variance. If that's inconvenient for a packaging style you'd prefer, that's an accepted tradeoff — this is built for a specific kind of consumer (agent-operated projects with a predictable working-directory convention), not for general-purpose PyPI distribution.

## Platform support

Validated end-to-end (real keygen → encrypt → decrypt → diff, not just "the binary exists") on:

| Platform | Status |
|---|---|
| Linux ARM64 (Raspberry Pi) | ✅ |
| Linux x86_64 | ✅ |
| WSL | ✅ |
| Windows 10 native | ✅ |

See `requirements.md` for exact versions, download URLs, and the full replication procedure if you want to re-verify on your own hardware.
