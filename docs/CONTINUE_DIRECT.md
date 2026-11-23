# Continue direct V1

**Status: experimental; hardware acceptance is incomplete.** The
default `StickS3/` sketch still uses the bridge. On `direct-v1-wip`, the
`DIRECT_V1` compile path has USB-only configuration, experimental bounded
direct transcription, Venice decision routing, spoken response, PNG image and
music paths. The music journal persists submit uncertainty and job IDs, and a
saved job is polled after reconnect. The direct build was flashed to the
connected StickS3 on 2026-11-23; the write verified and the firmware accepted
USB configuration, joined the configured Wi-Fi and synchronized its clock.
Provider paths and physical media output still require
hardware acceptance tests.

## Local credentials

On a new checkout, create `.env` from `.env.example` only if `.env` does not
already exist, restrict it to the owner (`chmod 600 .env`), and enter the Venice
and Surplus API keys locally. The filled `.env` is ignored by Git and is not
included in the branch; move or recreate it privately when changing machines.
Never paste keys into chat, commit them, put them in command-line arguments or
include them in logs. Account-scoped keys with spending limits are preferable.
The file is not encrypted; the device's NVS may also be unencrypted.

Install the development dependencies in a local virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r bridge/requirements.txt
.venv/bin/python tools/check_providers.py
```

The last command performs read-only account requests and prints only sanitized
status. A balance read may be restricted by a key's scopes; a reported zero
should be reconciled against the wallet/workspace shown in the account, not
assumed to mean funds need to be added. The client does not automatically load
`.env` into the bridge or other existing scripts. The direct USB helper will
read the private file only after a verified direct firmware is ready; it asks
for the 2.4 GHz Wi-Fi password without echoing it.

## Evaluation and next work

One synthetic Venice decision was made on 2026-11-23: `jev-latest` selected the
expected image route in 221 ms. The repository's 12-case synthetic routing set
also returned 12 correct routes, with 216.5 ms median and 763 ms p95. This small,
non-held-out host set is not a calibrated benchmark or a hardware result. The
original results and analyzer outputs are under Git-ignored `evals/private/`;
actual DIEM charges remain unknown until reconciled. The supplied inference key
returned HTTP 401 for the read-only Venice usage-history endpoint; do not infer
charges from token counts or a changing balance. The repeatable command
`.venv/bin/python tools/decision_smoke.py --run-paid` makes one chargeable request
and does not automatically retry. Its marker remains when a submission's outcome
is uncertain. Treat the marker as a possible charge, not a safe invitation to
resubmit. See [the evaluation guide](../evals/README.md).

Next: validate Venice model selection and routing on held-out cases; test the
media paths and power-loss behavior of the music journal; verify TLS, memory and failure
behavior; then provision, flash and run the requested hardware tests. Record
separate actual Venice DIEM and Surplus charges when provider records support
them. Never invent charges or treat estimates as actuals.

Host-only Surplus smoke tests on 2026-11-23 returned 24 kHz mono PCM16 WAV for
speech, an exact transcript of that synthetic sentence, and a 1024×1024 PNG.
The provider reported USD charges of 0.000059, 0.00015 and 0.0059 respectively.
These do not prove device playback or rendering; the direct PNG renderer has
not been tested on the physical display. Two music submissions with explicit durations returned HTTP 400; a
third request using the documented default returned a 60-second, 48 kHz stereo
FLAC. The provider reports a captured amount of USD 0.0225, but its settlement
status has not been independently reconciled, so the evaluation records that
charge as unknown. Do not resubmit the existing job. State and generated files are under
`evals/private/surplus-host-smoke/`, which is ignored by Git.

The experimental music downloader allows only the currently observed Surplus S3
artifact host and verifies Amazon Root CA 1; another host or unsupported format
fails visibly. A real device song job succeeded at Surplus, but its 5,763,633-byte
ID3-tagged FLAC exceeded the original 4.5 MiB limit and playback failed. The
existing job was saved, privately retrieved and decoded on the host; no new
song submission was made. Surplus reported 0.0225 USDC as captured; independent
settlement and the full run's other charges remain unreconciled. The private
device eval records its cost as unknown pending reconciliation.

The revised build raises the bounded FLAC limit to 6 MiB, temporarily releases
the recording buffer during music playback, and restores it afterward. It
retains a 65-second duration limit and 1 MiB decoder allocation budget. This
change compiled but has not yet been installed or tested on the board; the last
upload attempt could not enter the bootloader and wrote nothing. These limits
still need measurements on the board, including TLS, PSRAM and
task stack high-water marks. `tools/reconcile_music.py` clears a saved or
uncertain job only after the user explicitly checks the provider outcome.

The current direct sketch compiled for ESP32-S3 using both the repository-pinned
Arduino-ESP32 3.3.0 core and 3.3.12 with the repo-listed library versions. The
host decoder parsed the returned FLAC with about 41 KiB of decoder allocations,
and ArduinoJson parsed the actual-size image response with about 2.1 MiB of
allocations; these are host measurements, not device memory measurements. The
existing flash was privately backed up and verified. After the user granted
full local access, serial-control ioctls succeeded; the pinned direct build was
rebuilt and installed with the Arduino ESP32 toolchain. Bootloader, partition
table, OTA selector and app writes all passed their flash hash checks, and the
running firmware acknowledged USB setup and configuration. A follow-up build
added secret-free USB diagnostics and showed a Wi-Fi connection and synced
clock after an initially disconnected period. The device has not yet passed
provider or physical media acceptance checks. The user prefers the
assistant to handle deployment and does not want to run commands themselves. The
upstream application states that no new license is granted for its code; check
distribution rights before publishing further adaptations.
