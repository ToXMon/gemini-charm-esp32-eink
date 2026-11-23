#include "../../direct/multipart_wav.h"
#include <assert.h>
#include <string>
#include <vector>

using namespace direct;

static std::vector<uint8_t> wav(uint32_t rate, uint16_t channels, const std::vector<uint8_t> &pcm) {
  std::vector<uint8_t> v(44 + pcm.size());
  memcpy(v.data(), "RIFF", 4); put32(v.data()+4, uint32_t(v.size()-8));
  memcpy(v.data()+8, "WAVEfmt ", 8); put32(v.data()+16, 16); put16(v.data()+20, 1);
  put16(v.data()+22, channels); put32(v.data()+24, rate); put32(v.data()+28, rate*channels*2);
  put16(v.data()+32, channels*2); put16(v.data()+34, 16);
  memcpy(v.data()+36, "data", 4); put32(v.data()+40, uint32_t(pcm.size()));
  memcpy(v.data()+44, pcm.data(), pcm.size()); return v;
}

int main() {
  std::vector<uint8_t> pcm = {0,0, 0xff,0x7f, 0,0x80, 0xff,0xff};
  auto file = wav(16000, 1, pcm);
  WavView view;
  assert(parse_wav(file.data(), file.size(), view));
  assert(view.frames == 4 && view.rate == 16000 && view.channels == 1);
  assert(view.mono(1) == 32767 && view.mono(2) == -32768 && view.mono(4) == 0);
  auto stereo = wav(24000, 2, pcm);
  assert(parse_wav(stereo.data(), stereo.size(), view));
  assert(view.frames == 2 && view.mono(0) == 16383 && view.mono(1) == -16384);
  for (size_t i = 0; i < file.size(); ++i) assert(!parse_wav(file.data(), i, view));
  auto bad = file; put16(bad.data()+20, 3); assert(!parse_wav(bad.data(), bad.size(), view));
  bad = file; put32(bad.data()+40, UINT32_MAX); assert(!parse_wav(bad.data(), bad.size(), view));
  bad = file; put32(bad.data()+28, 7); assert(!parse_wav(bad.data(), bad.size(), view));
  bad = file; put16(bad.data()+34, 8); assert(!parse_wav(bad.data(), bad.size(), view));
  assert(!parse_wav(file.data(), file.size(), view, 0));

  const char *boundary = "0123456789abcdef0123456789abcdef";
  MultipartWav body;
  assert(body.init("venice-whisper-1", pcm.data(), pcm.size(), boundary));
  const size_t expected = body.size();
  std::vector<uint8_t> result;
  uint8_t buffer[7];
  while (body.remaining()) {
    size_t got = body.read(buffer, sizeof(buffer)); assert(got);
    result.insert(result.end(), buffer, buffer + got);
  }
  assert(result.size() == expected && body.read(buffer, sizeof(buffer)) == 0);
  std::string payload(result.begin(), result.end());
  assert(payload.find("name=\"model\"\r\n\r\nvenice-whisper-1\r\n") != std::string::npos);
  size_t start = payload.find("RIFF"); assert(start != std::string::npos);
  assert(parse_wav(result.data()+start, 44+pcm.size(), view) && view.frames == 4);
  assert(payload.substr(payload.size()-40) == std::string("\r\n--")+boundary+"--\r\n");
  assert(!body.init("bad\r\nmodel", pcm.data(), pcm.size(), boundary));
  assert(!body.init("model", pcm.data(), pcm.size()-1, boundary));
  assert(!body.init("model", pcm.data(), pcm.size(), "short"));
  std::string collision = std::string("\r\n--") + boundary;
  assert(!body.init("model", reinterpret_cast<const uint8_t *>(collision.data()), collision.size(), boundary));
}
