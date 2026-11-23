#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace direct {
// Reader::byte(uint8_t&) must have its own inactivity and total deadlines.
// Reject ambiguous framing and bound every line, header block and body. No
// automatic redirects, compression, informational responses, or close-delimited bodies.
template <typename Reader> class HttpResponse {
 public:
  explicit HttpResponse(Reader &reader) : reader_(reader) {}
  bool read(uint8_t *out, size_t cap, size_t &used, unsigned expected_status=200,
            char *location=nullptr,size_t location_cap=0) {
    used = 0; header_bytes_ = 0;
    if(location&&location_cap)location[0]=0;
    char line[4096];
    if (!out || !line_read(line, sizeof(line)) ||
        (strncmp(line,"HTTP/1.1 ",9)&&strncmp(line,"HTTP/1.0 ",9)) ||
        strlen(line)<12 || line[9]<'0'||line[9]>'9'||line[10]<'0'||line[10]>'9'||
        line[11]<'0'||line[11]>'9'||(line[12]&&line[12]!=' ')) return false;
    unsigned status=unsigned(line[9]-'0')*100+unsigned(line[10]-'0')*10+unsigned(line[11]-'0');
    if(status!=expected_status)return false;
    bool length_seen = false, chunked = false, transfer_seen = false, location_seen=false;
    size_t length = 0;
    for (unsigned count = 0; ; ++count) {
      if (count >= 64 || !line_read(line, sizeof(line))) return false;
      if (!*line) break;
      char *colon = strchr(line, ':');
      if (!colon || colon == line) return false;
      *colon++ = 0;
      for (char *p = line; *p; ++p) {
        if (*p >= 'A' && *p <= 'Z') *p += 'a' - 'A';
        else if (!((*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9') || *p == '-')) return false;
      }
      while (*colon == ' ' || *colon == '\t') ++colon;
      size_t vlen = strlen(colon);
      while (vlen && (colon[vlen-1] == ' ' || colon[vlen-1] == '\t')) colon[--vlen] = 0;
      if (!strcmp(line, "content-length")) {
        if (length_seen || !*colon) return false;
        length_seen = true;
        for (const char *p = colon; *p; ++p) {
          if (*p < '0' || *p > '9') return false;
          size_t d=size_t(*p-'0');
          if (d>cap || length>(cap-d)/10) return false;
          length = length * 10 + d;
        }
      } else if (!strcmp(line, "transfer-encoding")) {
        if (transfer_seen) return false;
        transfer_seen = true;
        for (char *p=colon; *p; ++p) if (*p >= 'A' && *p <= 'Z') *p += 'a'-'A';
        if (strcmp(colon, "chunked")) return false;
        chunked = true;
      } else if (!strcmp(line, "content-encoding")) {
        for (char *p=colon; *p; ++p) if (*p >= 'A' && *p <= 'Z') *p += 'a'-'A';
        if (strcmp(colon, "identity")) return false;
      } else if (!strcmp(line, "location")&&location) {
        if(location_seen||!location_cap||vlen>=location_cap)return false;
        location_seen=true;memcpy(location,colon,vlen+1);
      }
    }
    if (length_seen == chunked) return false;
    if (length_seen) return body(out, length, used);
    for (;;) {
      if (!line_read(line, sizeof(line))) return false;
      size_t n = 0, digits = 0;
      for (const char *p=line; *p && *p!=';'; ++p) {
        unsigned d;
        if (*p >= '0' && *p <= '9') d=unsigned(*p-'0');
        else if (*p >= 'a' && *p <= 'f') d=unsigned(*p-'a'+10);
        else if (*p >= 'A' && *p <= 'F') d=unsigned(*p-'A'+10);
        else return false;
        if (++digits > 8 || d > cap-used || n > (cap-used-d) / 16) return false;
        n = n*16+d;
      }
      if (!digits) return false;
      if (!n) {
        for (unsigned i=0; i<64; ++i) {
          if (!line_read(line,sizeof(line))) return false;
          if (!*line) return true;
          if (!strchr(line,':')) return false;
        }
        return false;
      }
      if (!body(out, n, used)) return false;
      uint8_t a, b;
      if (!reader_.byte(a) || !reader_.byte(b) || a!='\r' || b!='\n') return false;
    }
  }
 private:
  bool line_read(char *out,size_t cap) {
    size_t used=0;
    for (;;) {
      uint8_t c;
      if (!reader_.byte(c) || ++header_bytes_ > 8192 || c==0 || c=='\n') return false;
      if (c=='\r') {
        if (!reader_.byte(c) || ++header_bytes_ > 8192 || c!='\n') return false;
        out[used]=0;return true;
      }
      if (used+1>=cap || (c<32 && c!='\t') || c==127) return false;
      out[used++]=char(c);
    }
  }
  bool body(uint8_t *out,size_t len,size_t &used) {
    for (size_t i=0;i<len;++i) if (!reader_.byte(out[used++])) return false;
    return true;
  }
  Reader &reader_;
  size_t header_bytes_=0;
};
} // namespace direct
