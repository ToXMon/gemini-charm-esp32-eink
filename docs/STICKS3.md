# StickS3 setup and verification

Hardware target: M5Stack StickS3, 135×240 ST7789 LCD, ES8311 half-duplex microphone and speaker. This is based on Thor's `thor/m5sticks3-transcribe-plus-plus` branch, commit `6c86e389880005f81821dabb4892339e69897904`. The firmware compiles using the dependencies below, but has not been physically verified in this project.

## Dependencies

```sh
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@3.3.0 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli lib install 'ArduinoJson@7.4.3' 'Adafruit GFX Library@1.12.6' 'Adafruit BusIO@1.17.4' 'JPEGDEC@1.8.4' 'M5Unified@0.3.0' 'M5GFX@0.3.0'
arduino-cli lib install 'U8g2_for_Adafruit_GFX@1.8.0' --no-deps
```

Follow the [README](../README.md) for bridge setup, configuration, build and upload. Use a public certificate trusted by the firmware; do not disable certificate validation. The bridge listens only on localhost by default and needs a separately configured TLS reverse proxy. The bridge token must be a URL-safe string between 20 and 200 characters, saved on both the host and device. Do not enter the Surplus API key on the device.

## Use

- A starts recording; A stops and transcribes, then B creates. B during recording stops and directly creates after transcription.
- A cancels generation or playback locally. A running HTTP call may take time to return, and cancellation does not cancel a remote music job.
- The 30-second recording limit stops and transcribes automatically. Transcription is not live; wait for the result. Longer generated audio is truncated to 55 seconds.
- Hold A for 10 seconds for setup. Existing NVS data may survive flashing; if an old Gemini credential is present, replace it with the bridge token. Never upload NVS backups or serial logs publicly.

## Test sequence

1. Start the bridge and check your proxy certificate and hostname from a separate client. Ensure the process has a funded key and at least one compatible model configured for each desired modality.
2. Compile after setting the hostname, then flash using a USB data cable and detected port. Confirm the display, buttons, mic and speaker.
3. Record a short sentence, stop with A, and verify transcription. Ask for a brief spoken reply, a simple picture, then a short song. Compare device behavior, actual cost, latency, and provider errors against expectations.
4. If generation fails, check the bridge logs without sharing secrets, verify model IDs and seller availability on Surplus, and check that the selected image provider supports `b64_json` and the speech provider supports audio output.

External APIs and pricing change. Default models are examples, not guaranteed working offers. The router has no quality benchmark or budget enforcement. No camera input, video generation, live transcription, custom voice design, or automatic Gemini fallback is provided.
