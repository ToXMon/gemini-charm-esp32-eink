# Bridge and device setup

> **M5Stack StickS3 owners:** This firmware is for a different ESP32-S3 board with a 200×200 e-paper display and ES7210 microphone codec. It is **not compatible with the StickS3** and has not been tested on it. Do not flash this build to a StickS3; it needs a dedicated hardware port. See [M5Stack StickS3 specifications](https://docs.m5stack.com/en/core/StickS3).

Follow the original [build guide](BUILD.md) for hardware and Arduino dependencies. In this checkout, configure the bridge endpoint before compiling:

```sh
cp Gemini_Live/local_config.example.h Gemini_Live/local_config.h
# Edit BRIDGE_HOST and BRIDGE_PORT in local_config.h.
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,PSRAM=opi,FlashMode=qio,FlashSize=8M,PartitionScheme=huge_app --build-path build Gemini_Live
arduino-cli board list
arduino-cli upload --port PORT --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,PSRAM=opi,FlashMode=qio,FlashSize=8M,PartitionScheme=huge_app --input-dir build Gemini_Live
pip install -r requirements.txt
python tools/configure.py --port PORT --mode gemini
```

Enter the bridge token when prompted. The original Gemini and Hermes documentation describes upstream behavior and does not describe this bridge. The bridge uses only the device audio envelope; it ignores Gemini setup instructions and tool calls. Existing Hermes configuration may remain in NVS but is not used for bridge tool routing. Provisioning can retain prior NVS data; consider clearing it if no longer needed. The firmware compiled with ESP32 core 3.3.0 and the pinned libraries; physical audio, VAD, buffering, TLS and power behavior still require testing on the board. Speech-to-text and text-to-speech defaults are documented examples, not a promise of current seller availability. Surplus must support the selected model and output format.
