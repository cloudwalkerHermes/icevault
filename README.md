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
SOPS_AGE_KEY_FILE=demo/demo_age_key.txt python3 -c "from secrets_registry import get_example_key, get_example_multiline_key; print(bool(get_example_key()), bool(get_example_multiline_key()))"
```
Should print `True True`. The demo key/files only protect fake placeholder values — safe to commit, safe to ignore, never used for anything real.

## Setting up your own real vault (the "human bridge" step)

This is the one part of icevault that's deliberately **not automatable** — an agent should never see, generate, or type a real secret value. That's a human-only action, on purpose.

```bash
python3 manage_secrets.py
```

First run: generates a real `age` keypair at `age_key.txt` (gitignored — never committed) and creates `secrets.enc.yaml` for you, opening it in your `$EDITOR` so you can add your first secret as `KEY_NAME: the-real-value`. Save and close.

Every run after that: just opens the existing `secrets.enc.yaml` in your editor (decrypted), so you can add or change values. Saving re-encrypts automatically — `sops` handles that, you never touch ciphertext directly.

If `$EDITOR` isn't set in your shell, `sops` will fall back to `vi`. If you're not comfortable in `vi`, set a friendlier editor first: `export EDITOR=nano` (or your preference) before running `manage_secrets.py`. On **Windows**, `manage_secrets.py` and `manage_multiline_secret.py` automatically default to `notepad` when `EDITOR` isn't set — no manual configuration needed.

**⚠️ You must save and exit your editor cleanly for the encryption to actually fire.** `sops` decrypts to a temporary file, hands it to your `$EDITOR`, and only re-encrypts back into `secrets.enc.yaml` on a clean exit. If the editor exits uncleanly (a crash, a force-kill, an editor error) the real file is **not** updated — your change silently never happened. If you're not sure your last edit actually landed, check whether the key name you expect shows up: `grep -E "^[A-Za-z_]+:" secrets.enc.yaml` (safe to run — that only shows key *names* in cleartext, values stay encrypted). If it's not there, just redo the entry.

**Back up `age_key.txt` somewhere safe the moment it's generated** (your personal password manager, not this repo). There's no recovery without it — lose the key, lose access to everything encrypted with it. This is the literal cold-wallet-seed-phrase tradeoff: maximum security, zero forgiveness for losing the key.

**Set permissions to `400` immediately after generation:**
```bash
chmod 400 age_key.txt
```
Owner read-only. Nothing — not another process, not a misconfigured tool, not an agent — should ever need to write to the key file after it's created.

### Multi-line secrets (PEM keys, certs, anything with embedded newlines)

**Use a separate tool: `manage_multiline_secret.py`, not `manage_secrets.py`.**

```bash
python3 manage_multiline_secret.py KEY_NAME
```

This exists because of a real incident (2026-06-25): pasting a multi-line PEM directly into `manage_secrets.py`'s YAML editor broke (`yaml: line N: could not find expected ':'`) on a lost-indentation paste — hand-indenting a YAML literal block scalar correctly, line by line, in an interactive editor is a genuine trap, not user error. The fix isn't to remove the human from typing the value in — it's to remove the YAML structure entirely, so there's nothing to indent in the first place.

Each multi-line secret gets its **own standalone encrypted file** under `multiline/<KEY_NAME>.enc`, using `sops`' binary mode: the whole file is one raw opaque blob, no YAML/JSON structure at all. You still open a real editor and paste your secret in by hand, exactly like `manage_secrets.py` — just into a genuinely blank file with nothing to format, instead of a YAML document with indentation rules. First run for a given name creates it blank; running the same name again reopens it with whatever you last saved, so you can correct it.

This also means a botched edit on one multi-line secret **cannot corrupt another** — they're separate files, never parsed or re-encrypted together, unlike the single shared `secrets.enc.yaml`.

**Alternative: use `manage_multiline_secret.py` for everything, single-line included.** Nothing prevents this. Each secret — regardless of whether it actually contains newlines — gets its own standalone encrypted file under `multiline/`, with zero cross-contamination risk by construction and easier per-secret rotation (just replace one file). The tradeoff: `manage_secrets.py`'s convenient batch workflow (open once, paste all your keys, save) goes away — each secret requires its own invocation. Both approaches are fully supported; the split is just a preference call.

Getters use `decrypt_file_secret(name)` instead of `decrypt_value(name)` — see `get_oddsapi_key()` vs. `get_example_multiline_key()` in `secrets_registry.py` for the pattern. Same collision-check step applies before naming one.

### Adding a secret an agent will use

1. **Collision check first** — `python3 collision_check.py get_your_proposed_name`. If it flags a near-duplicate of something that already exists, reuse that instead of adding a new one.
2. **You add the real value** — `python3 manage_secrets.py` for single-line, or `python3 manage_multiline_secret.py KEY_NAME` for anything with embedded newlines. The agent should tell you exactly what key name to use; it should never type the value itself or ask you to paste it anywhere except directly into your own editor session.
3. **The agent adds the getter** in `secrets_registry.py` — references only the key *name*, never the value:
   ```python
   def get_your_new_thing() -> str:
       return decrypt_value("KEY_NAME")              # single-line
       # or: return decrypt_file_secret("KEY_NAME")   # multi-line
   ```
4. **Verify blind** — call the getter, confirm it returns something truthy, without ever printing or logging the actual value.

## How it works under the hood

- `bootstrap.py` — fetches the right `sops`/`age` binaries for your platform into `bin/` (gitignored, large and platform-specific). Idempotent, no sudo/admin.
- `vault_core.py` — the low-level decrypt wrapper. `decrypt_value()` calls `sops --extract` to pull exactly one value at a time from the shared YAML file; `decrypt_file_secret()` decrypts a standalone binary-mode file for multi-line secrets. Neither ever decrypts more than one secret's worth of plaintext, never holds it anywhere but transiently in the calling process's memory.
- `secrets_registry.py` — the actual named getters. This file *is* the human-readable, canonical list of every secret icevault manages — read it, don't grep for string literals scattered elsewhere.
- `collision_check.py` — normalized-name collision detector (case/underscores stripped before comparing), run before adding any new getter.
- `manage_secrets.py` — the human-facing helper for single-line secrets in the shared vault: auto-generates the key and creates the file on first use, otherwise just opens it for editing. Never touches a plaintext value itself.
- `manage_multiline_secret.py` — the human-facing helper for multi-line secrets, one standalone encrypted file per secret under `multiline/`. Same never-touches-a-plaintext-value guarantee.
- `secrets.enc.yaml` / `age_key.txt` / `multiline/` — your real vault, key, and multi-line secrets. Gitignored, created locally, never committed. (Not present in a fresh clone — that's correct; the `manage_*` scripts create them.)
- `demo/` — self-contained examples (single-line and multi-line) proving both mechanisms work, safe to commit since they only protect fake values.

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
