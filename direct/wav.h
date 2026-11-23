#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace direct {
inline uint16_t le16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline uint32_t le32(const uint8_t *p) {
  return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
inline void put16(uint8_t *p, uint16_t v) { p[0] = uint8_t(v); p[1] = uint8_t(v >> 8); }
inline void put32(uint8_t *p, uint32_t v) { for (unsigned i = 0; i < 4; ++i) p[i] = uint8_t(v >> (8 * i)); }

// Strictly bounded PCM16 WAV view. No allocations and no pointers outside input.
struct WavView {
  const uint8_t *samples = nullptr;
  size_t frames = 0;
  uint32_t rate = 0;
  uint16_t channels = 0;
  int16_t mono(size_t frame) const {
    if (!samples || frame >= frames) return 0;
    const uint8_t *p = samples + frame * channels * 2;
    int32_t a = int16_t(le16(p));
    return channels == 1 ? int16_t(a) : int16_t((a + int16_t(le16(p + 2))) / 2);
  }
};

inline bool parse_wav(const uint8_t *p, size_t n, WavView &out, uint32_t max_seconds = 55) {
  out = WavView{};
  if (!p || n < 12 || memcmp(p, "RIFF", 4) || memcmp(p + 8, "WAVE", 4)) return false;
  const uint32_t riff = le32(p + 4);
  if (riff < 4 || uint64_t(riff) + 8 != n) return false;
  bool have_fmt = false, have_data = false;
  uint16_t channels = 0, align = 0;
  uint32_t rate = 0, byte_rate = 0, data_size = 0;
  const uint8_t *samples = nullptr;
  size_t pos = 12;
  while (pos < n) {
    if (n - pos < 8) return false;
    const uint8_t *chunk = p + pos;
    uint32_t len = le32(chunk + 4);
    pos += 8;
    if (len > n - pos) return false;
    if (!memcmp(chunk, "fmt ", 4)) {
      if (have_fmt || len < 16 || le16(p + pos) != 1 || le16(p + pos + 14) != 16) return false;
      channels = le16(p + pos + 2); rate = le32(p + pos + 4);
      byte_rate = le32(p + pos + 8); align = le16(p + pos + 12); have_fmt = true;
    } else if (!memcmp(chunk, "data", 4)) {
      if (have_data) return false;
      samples = p + pos; data_size = len; have_data = true;
    }
    pos += len;
    if (len & 1) { if (pos == n) return false; ++pos; }
  }
  if (!have_fmt || !have_data || (channels != 1 && channels != 2) || rate < 8000 || rate > 48000 ||
      align != channels * 2 || byte_rate != rate * align || !data_size || data_size % align) return false;
  size_t frames = data_size / align;
  if (uint64_t(frames) > uint64_t(rate) * max_seconds) return false;
  out.samples = samples; out.frames = frames; out.rate = rate; out.channels = channels;
  return true;
}
} // namespace direct
