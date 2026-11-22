# Surplus Charm for ESP32-S3

A local adaptation of [gemini-charm-esp32-eink](https://github.com/thorwebdev/gemini-charm-esp32-eink) for the same Waveshare ESP32-S3, microphone, speaker, and 200×200 e-paper device. It uses a separately hosted bridge and [Surplus Intelligence](https://www.surplusintelligence.ai/docs) for turn-based transcription, conversation, and speech. The bridge also has a command-line media generator for stories, illustrations, and instrumental music. A caregiver should review generated content before sharing it with a young child.

**Status:** experimental. The firmware compiles with the pinned ESP32 toolchain. No physical device or paid Surplus API calls have been tested in this workspace. The original project's application code says no new license is granted; check rights with its author before distributing a fork. Bundled vendor licenses remain in place.

## How it works

The board retains the upstream codec, e-paper, buttons, Wi-Fi, sleep and audio code. A secure WebSocket bridge accepts the existing audio envelope, detects a speech turn, and calls Surplus's transcription, chat-completions, and speech endpoints. Audio is converted to the firmware's 24 kHz PCM playback format. This is half-duplex, not Gemini Live: expect a pause between speaking and hearing a reply, and no interruption during playback. The old Hermes/Google Search tool routing is not implemented by the bridge. The display shows status rather than generated pictures; media files are saved on the host, and music is not played on the device.

## Setup

1. Get a Surplus buyer API key and prepaid balance. Check the [live models and offers](https://www.surplusintelligence.ai/docs/api-reference/models) for compatible chat, transcription, speech and media model IDs; catalog entries do not guarantee available sellers. `surp.ivc.lol` is an independent text-oriented x402 router; this project calls Surplus directly because speech and media need their own endpoints.
2. Run the bridge on a trusted host with Python 3.10+, FFmpeg and HTTPS/WSS termination. For example:

   ```sh
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r bridge/requirements.txt
   export SURPLUS_API_KEY='your-key'
   export BRIDGE_TOKEN='a-long-random-url-safe-token-at-least-20-characters'
   export SURPLUS_CHAT_MODEL='your-available-chat-model'
   uvicorn bridge.app:app --host 127.0.0.1 --port 8000 --no-access-log
   ```

   Use a reverse proxy with a publicly trusted certificate that chains to the CA in `Gemini_Live/hermes_roots.h`, WebSocket upgrade support, and access logging disabled for `/device`. The token travels in the WebSocket URL because the original client uses a query parameter; TLS is mandatory and proxies must not log URLs. Keep the bridge bound to localhost behind the proxy and restrict access. Surplus credentials stay on the host; the device stores the separate bridge token in NVS. Never expose the bridge without TLS. Change the CA file if your certificate uses another root. Generate a random URL-safe token with `python -c 'import secrets; print(secrets.token_urlsafe(32))'`. Configure STT/TTS models, voice, and VAD threshold as needed; see [bridge/.env.example](bridge/.env.example). Environment files are not loaded automatically.
3. Follow [the hardware build guide](docs/BUILD.md), but use the local checkout. Copy `Gemini_Live/local_config.example.h` to `Gemini_Live/local_config.h`, set `BRIDGE_HOST` and `BRIDGE_PORT`, compile and flash. See [setup notes](docs/SURPLUS.md) for exact commands. Use `python tools/configure.py --port PORT --mode gemini` to enter Wi-Fi and the **bridge token**; the legacy mode name is retained. Press BOOT to start/stop, and speak after Listening appears.
4. Test at a low volume and adjust `VAD_THRESHOLD` for your room. Disconnecting the session stops it; recording only happens during an active session. Speech and generated content are sent to Surplus and its selected provider. Do not send sensitive family data unless you accept that processing.

## Generate media on the host

Activate the same environment and set `SURPLUS_API_KEY`. Examples (replace model IDs with available sellers):

```sh
python bridge/media.py story --model YOUR_CHAT_MODEL --prompt 'A tiny duck says goodnight to the moon in 100 words' --output story.txt
# Review and edit story.txt, then narrate it:
python bridge/media.py speech --model YOUR_TTS_MODEL --text-file story.txt --voice alloy --output story.wav
python bridge/media.py image --model YOUR_IMAGE_MODEL --prompt 'A friendly duck under the moon, soft picture-book style' --output duck.png
python bridge/media.py music --model YOUR_MUSIC_MODEL --prompt 'A calm instrumental bedtime melody with a music box' --duration 15 --output lullaby.audio
```

Speech requests WAV, though the chosen model must support that format. Image requires a provider returning `b64_json`; music is an asynchronous job and may take several minutes. Output extensions should match the actual model output. These are paid calls, not dry runs; consult live pricing and review each result. There is no automatic quality judge, spending cap, video generator, or playback-to-device pipeline yet. The prompt emphasizes a gentle toddler-appropriate style but is not a safety guarantee.

The [media generation course](https://github.com/DataTalksClub/production-ai-agents-for-media-generation) inspired separating briefs, generation, and human review, with bounded duration and no automatic paid regeneration. For consistent results, reuse character descriptions and style prompts, review each artifact, and record model, prompt, cost, and outcome externally. Surplus seller availability and media contracts can change.
