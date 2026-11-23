# Surplus StickS3

An experimental Surplus-powered adaptation of Thor's [M5StickS3 transcription and media branch](https://github.com/thorwebdev/gemini-charm-esp32-eink/tree/thor/m5sticks3-transcribe-plus-plus). Press **A** to record a request, then **B** to transcribe and create: the bridge classifies the transcript and returns spoken audio, a color image, or music to the StickS3. The bridge uses Surplus for inference; its API key stays on the host. Thor's original application sources state no new license is granted; confirm distribution rights with the author. Vendor sources retain their licenses.

> **V1 direction:** Direct StickS3-to-Surplus operation is planned but not implemented. The current StickS3 firmware below still requires a bridge. See [direct V1 plan](docs/DIRECT_V1.md) and the [decision-routing experiment](experiments/decision-routing/README.md).

**Status:** experimental and not yet tested on physical hardware or against a funded Surplus account. The StickS3 firmware compiles with the dependencies below; the older `Gemini_Live/` sketch targets a different Waveshare e-paper board and must not be flashed to a StickS3. Built artifacts containing the example bridge hostname are not configured for your host.

Unlike Thor's Gemini Live stream, this version records up to 30 seconds locally and transcribes after recording stops. The screen doesn't show interim words. A short A press stops recording and shows the transcript; B creates from it. A short B press during recording stops, transcribes, and creates. A cancels playback or requests cancellation; a request already accepted by Surplus, especially an async music job, may still finish and incur charges. Audio is half-duplex. The bridge converts generated images to 135×240 JPEG and audio to mono 16 kHz PCM, with a 55-second playback cap. Custom Gemini voice design and live transcription aren't implemented.

## 1. Run the bridge

Use a trusted always-on computer with Python 3.10+, FFmpeg and a Surplus buyer key with credit. The device cannot run this server itself. On that computer:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r bridge/requirements.txt
export SURPLUS_API_KEY='your Surplus buyer key'
export BRIDGE_TOKEN='your random URL-safe bridge token, at least 20 characters'
export SURPLUS_CHAT_MODELS='your-available-chat-model'
uvicorn bridge.app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Generate the bridge token with `python -c 'import secrets; print(secrets.token_urlsafe(32))'`. Keep it separate from the Surplus key. Environment variables must be set in the bridge process; `.env.example` is a reference and is not automatically loaded. Use [Surplus's live catalog and order book](https://www.surplusintelligence.ai/docs/api-reference/markets) to choose models with active offers. Defaults for transcription, speech, image and music are documented examples and may have no seller or not support a requested output format; override them using `SURPLUS_STT_MODELS`, `SURPLUS_TTS_MODELS`, `SURPLUS_IMAGE_MODELS`, and `SURPLUS_MUSIC_MODELS` (see [bridge/.env.example](bridge/.env.example)). The voice is set by `SURPLUS_VOICE`.

Expose this localhost service to the device with an HTTPS reverse proxy, a DNS hostname and a certificate trusted by `StickS3/bridge_roots.h` (ISRG Root X1 by default). Forward `Authorization`, disable request/URL logging, and use a proxy timeout of at least 180 seconds. Restrict access to trusted clients. The configured bridge token authorizes paid requests, so keep it private. A certificate from a different CA requires updating `StickS3/bridge_roots.h`. The device must reach the hostname on its 2.4 GHz Wi-Fi network; no bridge hostname or hosting is provisioned by this repository.

### Model selection

Each `*_MODELS` variable is a comma-separated **allowlist of models you have reviewed for the task and endpoint**. With multiple candidates the bridge consults Surplus's public market snapshot, drops missing/unpriced offers, and selects the lowest estimated price within the list. Chat compares an illustrative mix of 1,000 input and 250 output tokens; media candidates must share the same billing unit. This is not a guarantee of cheapest actual cost, quality, health, privacy, or current supply: offer data can be stale, and models may differ in output format or functionality. A single configured candidate is sent directly; Surplus then selects a seller for that model. No automatic paid retry or spending cap is implemented. Vision and video routing are not implemented. Media jobs live in the bridge process memory: run one worker, and expect pending jobs to be lost on restart. Only one generation runs at a time.

## 2. Build and flash the StickS3

Install Arduino CLI, ESP32 core 3.3.0 and the libraries listed in [StickS3 setup](docs/STICKS3.md). Then:

```sh
cp StickS3/bridge_config.example.h StickS3/bridge_config.h
# Edit BRIDGE_HOST and BRIDGE_PORT to your HTTPS proxy hostname and port.
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,PSRAM=opi,FlashMode=qio,FlashSize=8M,PartitionScheme=huge_app --build-path build/sticks3 StickS3
arduino-cli board list
arduino-cli upload --port PORT --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,PSRAM=opi,FlashMode=qio,FlashSize=8M,PartitionScheme=huge_app --input-dir build/sticks3 StickS3
```

The config header is ignored by Git. Replace `PORT` with the detected serial port. Flashing replaces existing firmware; make a backup if you need to restore it. The compiled result is only for the chosen host and trust root. Do not flash until you have configured them.

On first boot, use the on-screen QR setup to join the temporary setup network and enter your 2.4 GHz Wi-Fi and **bridge token**, not the Surplus key. The setup portal is a local unencrypted access point; use it in a trusted place, and hold A for 10 seconds to configure again. Then press A, say a request, and press B. Check volume at a low setting and have a caregiver review generated content before sharing with a child. Requests and audio go to Surplus and its selected sellers. Hardware and live-provider behavior remain unverified.

## Tests and host media

```sh
python -m unittest discover -s tests -v
```

The tests use mock Surplus responses; they don't prove seller availability, billing, TLS, hardware or real-time performance. `bridge/media.py` also generates host-side stories, reviewed text-to-speech, images and music; run `python bridge/media.py --help`. Actual calls can cost money. The older WebSocket bridge and Waveshare sketch remain for reference, not StickS3 use. See [StickS3 setup](docs/STICKS3.md) for troubleshooting and limitations.
