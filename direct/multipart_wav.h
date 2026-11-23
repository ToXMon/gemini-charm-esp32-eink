#pragma once
#include "wav.h"
#include <stdio.h>
#include <limits.h>

namespace direct {
// One-shot view of existing 16 kHz mono PCM. The caller must keep PCM stable
// throughout transmission and must not retry an ambiguous paid request.
class MultipartWav {
 public:
  // boundary must be 32 lowercase hex digits from a cryptographic RNG. A
  // collision with captured PCM is rejected, so the caller can generate again.
  bool init(const char *model, const uint8_t *pcm, size_t n, const char *boundary) {
    valid_ = false; position_ = 0;
    if (!model || !pcm || !boundary || !n || n % 2 || n > 16000u * 2u * 30u) return false;
    for (size_t i = 0; i < 32; ++i) {
      char c = boundary[i];
      if (!c || !((c >= 'a' && c <= 'f') || (c >= '0' && c <= '9'))) return false;
    }
    if (boundary[32]) return false;
    char marker[37];
    memcpy(marker, "\r\n--", 4); memcpy(marker + 4, boundary, 32); marker[36] = 0;
    for (size_t i = 0; i + 36 <= n; ++i)
      if (pcm[i] == '\r' && !memcmp(pcm + i, marker, 36)) return false;
    size_t m = 0;
    for (; m < 80 && model[m]; ++m) {
      char c = model[m];
      if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.')) return false;
    }
    if (!m || m == 80) return false;
    int count = snprintf(prefix_, sizeof(prefix_),
      "--%s\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n%s\r\n"
      "--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n"
      "Content-Type: audio/wav\r\n\r\n", boundary, model, boundary);
    if (count < 0 || size_t(count) >= sizeof(prefix_)) return false;
    int end = snprintf(suffix_, sizeof(suffix_), "\r\n--%s--\r\n", boundary);
    if (end < 0 || size_t(end) >= sizeof(suffix_)) return false;
    suffix_size_ = size_t(end);
    prefix_size_ = size_t(count); pcm_ = pcm; pcm_size_ = n;
    memcpy(wav_, "RIFF", 4); put32(wav_ + 4, uint32_t(n + 36));
    memcpy(wav_ + 8, "WAVEfmt ", 8); put32(wav_ + 16, 16); put16(wav_ + 20, 1);
    put16(wav_ + 22, 1); put32(wav_ + 24, 16000); put32(wav_ + 28, 32000);
    put16(wav_ + 32, 2); put16(wav_ + 34, 16); memcpy(wav_ + 36, "data", 4); put32(wav_ + 40, uint32_t(n));
    total_ = prefix_size_ + sizeof(wav_) + n + suffix_size_;
    valid_ = true; return true;
  }
  size_t size() const { return valid_ ? total_ : 0; }
  size_t remaining() const { return valid_ ? total_ - position_ : 0; }
  size_t read(uint8_t *out, size_t capacity) {
    if (!valid_ || !out) return 0;
    size_t written = 0;
    const uint8_t *parts[] = { reinterpret_cast<const uint8_t *>(prefix_), wav_, pcm_, reinterpret_cast<const uint8_t *>(suffix_) };
    const size_t sizes[] = { prefix_size_, sizeof(wav_), pcm_size_, suffix_size_ };
    size_t base = 0;
    for (unsigned i = 0; i < 4 && written < capacity; ++i) {
      if (position_ >= base + sizes[i]) { base += sizes[i]; continue; }
      size_t offset = position_ - base;
      size_t take = sizes[i] - offset;
      if (take > capacity - written) take = capacity - written;
      memcpy(out + written, parts[i] + offset, take);
      written += take; position_ += take; base += sizes[i];
    }
    return written;
  }
 private:
  char prefix_[320]{};
  char suffix_[48]{};
  uint8_t wav_[44]{};
  const uint8_t *pcm_ = nullptr;
  size_t prefix_size_ = 0, suffix_size_ = 0, pcm_size_ = 0, total_ = 0, position_ = 0;
  bool valid_ = false;
};
} // namespace direct
