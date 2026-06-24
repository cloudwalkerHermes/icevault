# icevault — Requirements

## Non-pip dependencies (must be installed separately — these are standalone binaries, not Python packages, so a conventional `pip install -r requirements.txt` will not pull them in)

### `age` — key generation + encryption primitive

- **Tested version:** v1.3.1 — https://github.com/FiloSottile/age/releases/tag/v1.3.1
- **Confirmed available for:** `linux-arm64`, `linux-amd64`, `windows-amd64`, `linux-arm`, `darwin-amd64`, `darwin-arm64`, `freebsd-amd64`
- **Install (Linux, no sudo required — user-space binary):**
  ```bash
  curl -sL -o age.tar.gz https://github.com/FiloSottile/age/releases/download/v1.3.1/age-v1.3.1-<platform>.tar.gz
  tar xzf age.tar.gz
  ```
  `<platform>` = `linux-arm64` (Raspberry Pi / ARM64) or `linux-amd64` (most Linux x86_64, including WSL).
- **Install (Windows):** download `age-v1.3.1-windows-amd64.zip` from the releases page, extract, add to PATH.
- **Round-trip verified:** Raspberry Pi (`aarch64`), 2026-06-24 — real keygen → encrypt → decrypt → diff, confirmed byte-identical. Not yet verified on N150 / Windows 10 / WSL (binaries confirmed to exist for all three, actual round-trip not yet run there).

### `sops` — structured-file encryption wrapper (uses `age` as the backend)

- **Tested version:** v3.13.1 — https://github.com/getsops/sops/releases/tag/v3.13.1
- **Confirmed available for:** `linux.arm64`, `linux.amd64`, `amd64.exe`/`arm64.exe` (Windows), `darwin` (amd64/arm64), plus `.deb`/`.rpm` packages
- **Install (Linux, no sudo required — user-space binary):**
  ```bash
  curl -sL -o sops https://github.com/getsops/sops/releases/download/v3.13.1/sops-v3.13.1.linux.<arch>
  chmod +x sops
  ```
  `<arch>` = `arm64` or `amd64`.
- **Install (Linux, with sudo, via `.deb`):**
  ```bash
  curl -sL -o sops.deb https://github.com/getsops/sops/releases/download/v3.13.1/sops_3.13.1_<arch>.deb
  sudo dpkg -i sops.deb
  ```
- **Install (Windows):** download `sops-v3.13.1.amd64.exe`, rename to `sops.exe`, place on PATH.
- **Round-trip verified:** Raspberry Pi (`aarch64`), 2026-06-24 — same test as above, byte-identical decrypt. Not yet verified on N150 / Windows 10 / WSL.

## Python dependencies (pip-installable)

Not finalized — `secrets_registry.py` hasn't been built yet (encryption/infra validated first, registry layer is next per the build-order decision). Placeholder for now:

- `PyYAML` — likely needed once the registry layer parses decrypted YAML content.

## Platform validation status

| Platform | Binaries confirmed to exist | Round-trip actually tested |
|---|---|---|
| Raspberry Pi (`aarch64`) | ✅ | ✅ confirmed 2026-06-24 |
| N150 mini PC (x86_64 Linux, assumed) | ✅ | ⬜ not yet run |
| Windows 10 (x86_64) | ✅ | ⬜ not yet run |
| WSL (Linux under Windows) | ✅ | ✅ confirmed 2026-06-24 |

## Validation procedure — replicate this on your platform

If you're a Claude/Hermes instance on a different machine reading this file: run the matching block below exactly as written, then **report the result back to the operator rather than pushing a commit yourself** — one coordinating session owns writes to this repo, so multiple validating instances don't risk colliding on the same file. Everything downloads to a scratch directory and is deleted at the end — nothing is installed system-wide, no sudo/admin required.

### Linux / WSL (bash) — covers N150 and WSL

```bash
mkdir -p /tmp/icevault_test && cd /tmp/icevault_test

# Detect arch automatically (arm64 or amd64)
ARCH=$(uname -m); case "$ARCH" in aarch64) ARCH=arm64 ;; x86_64) ARCH=amd64 ;; esac

# Download age + sops for this platform
curl -sL -o age.tar.gz "https://github.com/FiloSottile/age/releases/download/v1.3.1/age-v1.3.1-linux-${ARCH}.tar.gz"
tar xzf age.tar.gz
curl -sL -o sops "https://github.com/getsops/sops/releases/download/v3.13.1/sops-v3.13.1.linux.${ARCH}"
chmod +x sops age/age age/age-keygen

# Confirm both binaries actually run
./age/age --version
./sops --version

# Real round-trip: keygen -> create test file -> encrypt -> decrypt -> diff
./age/age-keygen -o test_key.txt
AGE_PUBKEY=$(grep "public key:" test_key.txt | awk '{print $NF}')
cat > secret_test.yaml <<'EOF'
ODDSAPI_KEY: this-is-a-test-value-12345
DB_PASSWORD: another-test-value-67890
EOF
SOPS_AGE_KEY_FILE=test_key.txt ./sops --age "$AGE_PUBKEY" -e secret_test.yaml > secret_test.enc.yaml
cat secret_test.enc.yaml   # sanity check: key NAMES visible, VALUES should show ENC[...] ciphertext
SOPS_AGE_KEY_FILE=test_key.txt ./sops -d secret_test.enc.yaml > secret_test.dec.yaml
diff secret_test.yaml secret_test.dec.yaml && echo "ROUND-TRIP CONFIRMED IDENTICAL"

# Clean up -- nothing should be left behind
cd / && rm -rf /tmp/icevault_test
```

### Windows 10 native (PowerShell) — Windows 10 ships `curl.exe`/`tar.exe` natively, no extra install needed

```powershell
$dir = "$env:TEMP\icevault_test"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Set-Location $dir

curl.exe -sL -o age.tar.gz "https://github.com/FiloSottile/age/releases/download/v1.3.1/age-v1.3.1-windows-amd64.zip"
Expand-Archive -Path age.tar.gz -DestinationPath . -Force
curl.exe -sL -o sops.exe "https://github.com/getsops/sops/releases/download/v3.13.1/sops-v3.13.1.amd64.exe"

.\age\age.exe --version
.\sops.exe --version

.\age\age-keygen.exe -o test_key.txt
$AGE_PUBKEY = (Select-String "public key:" test_key.txt).Line.Split(" ")[-1]
@"
ODDSAPI_KEY: this-is-a-test-value-12345
DB_PASSWORD: another-test-value-67890
"@ | Out-File -Encoding utf8 secret_test.yaml

$env:SOPS_AGE_KEY_FILE = "test_key.txt"
.\sops.exe --age $AGE_PUBKEY -e secret_test.yaml | Out-File -Encoding utf8 secret_test.enc.yaml
Get-Content secret_test.enc.yaml   # sanity check: key NAMES visible, VALUES should show ENC[...] ciphertext
.\sops.exe -d secret_test.enc.yaml | Out-File -Encoding utf8 secret_test.dec.yaml

if ((Compare-Object (Get-Content secret_test.yaml) (Get-Content secret_test.dec.yaml)).Count -eq 0) {
    Write-Output "ROUND-TRIP CONFIRMED IDENTICAL"
} else {
    Write-Output "MISMATCH -- investigate"
}

Set-Location $env:TEMP
Remove-Item -Recurse -Force $dir
```

**Note on the Windows `age` zip:** the download command above saves it as `age.tar.gz` for path-variable consistency with the Linux block, but it's actually a `.zip` — `Expand-Archive` handles it correctly regardless of that filename mismatch; rename to `age.zip` first if your PowerShell version complains about the extension.

Recommended next step for whoever picks this up: run the matching block above on N150 / Windows 10 / WSL, confirm "ROUND-TRIP CONFIRMED IDENTICAL" on each, and update the status table.
