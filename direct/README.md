# Direct firmware work in progress

The existing `StickS3/` sketch is still the bridge version. Nothing in this
directory is wired into that sketch or ready to flash.

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

The NVS adapter and crash consistency still require ESP32 build and physical
power-loss tests. The direct networking, credentials, routing and media decoders
are not implemented here.
