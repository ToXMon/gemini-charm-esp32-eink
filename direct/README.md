# Direct firmware work in progress

The default `StickS3/` build remains the bridge version. An experimental
`DIRECT_V1` compile path contains USB provisioning, bounded direct
transcription, Venice model selection and decisions, spoken response, PNG image,
and a music submit/poll/download/playback path. These paths have not been tested
on hardware; decision confidence is uncalibrated. Do not flash it for V1 until
the remaining verification in [the continuation guide](../docs/CONTINUE_DIRECT.md).

`music_journal.h` and `music_journal_nvs.h` are an initial, single-job guard for
future direct firmware. A caller must open a dedicated NVS namespace, load the
journal, and commit `begin()` successfully **before** transmitting a paid music
submission. It must record a valid returned job ID before polling. On restart,
an `identified` job must be polled; an `uncertain` job requires reconciliation
with the provider and explicit user acknowledgement. Timeout, local cancellation,
or loss of a response never makes another submission safe. The caller must
serialize access and surface storage errors. This guard does not implement the
HTTP request, reconciliation UI, NVS initialization, cancellation, or billing.
It is not a substitute for provider-side idempotency.

Run the portable guard test on a host:

```sh
clang++ -std=c++11 -Wall -Wextra -Werror tests/native/music_journal_test.cpp -o /tmp/music-journal-test
/tmp/music-journal-test
clang++ -std=c++11 -Wall -Wextra -Werror -Itests/native/stubs tests/native/music_journal_nvs_test.cpp -o /tmp/music-journal-nvs-test
/tmp/music-journal-nvs-test
```

The music journal is connected to the experimental sketch. Its NVS adapter and
crash consistency still require physical power-loss tests. An ambiguous submit
stays blocked; an identified pending job is polled after reconnect without
another POST. A failed or ambiguous job must be reconciled explicitly before
clearing its state with `tools/reconcile_music.py`.

`multipart_wav.h` provides a bounded, zero-copy PCM16 multipart reader with a
caller-generated random boundary. `wav.h` checks bounded PCM16 mono/stereo WAV
responses before playback. The multipart reader is used by the experimental
transcription path; WAV playback is connected experimentally but not tested on
the physical device.
The bounded HTTP response parser supports Content-Length and chunked responses,
rejects redirects and compressed or ambiguous framing, and has host tests.
Run the portable checks with:

```sh
clang++ -std=c++11 -Wall -Wextra -Werror tests/native/audio_format_test.cpp -o /tmp/audio-format-test
/tmp/audio-format-test
clang++ -std=c++11 -Wall -Wextra -Werror tests/native/http_response_test.cpp -o /tmp/http-response-test
/tmp/http-response-test
```

The USB setup helper is `tools/configure_direct.py`; it prompts locally and
does not write credentials to a file. It must be used only after the correct
direct build is verified on the device. Device NVS may be unencrypted and can
expose keys to someone with physical access. No provider call or physical
provisioning has yet validated this path.

`decision_policy.h` validates the account catalog and JEV decision shape. Its
host test needs the repo-pinned ArduinoJson headers on the compiler include path:

```sh
clang++ -std=c++11 -Wall -Wextra -Werror -I/path/to/ArduinoJson/src tests/native/decision_policy_test.cpp -o /tmp/decision-policy-test
/tmp/decision-policy-test
```
