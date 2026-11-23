#include "../../direct/http_response.h"
#include "../../direct/artifact_url.h"
#include <assert.h>
#include <string>

struct Reader {
  explicit Reader(const std::string &value):input(value) {}
  std::string input; size_t pos=0;
  bool byte(uint8_t &c) { if(pos>=input.size())return false;c=uint8_t(input[pos++]);return true; }
};
static bool parse(const std::string &data, size_t cap, std::string &out,unsigned status=200) {
  Reader r{data}; direct::HttpResponse<Reader> parser(r);
  uint8_t buffer[32]{};size_t n=0;
  bool ok=parser.read(buffer,cap,n,status);
  if(ok)out.assign(reinterpret_cast<char *>(buffer),n);
  return ok;
}
int main() {
  std::string out;
  assert(parse("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello",5,out)&&out=="hello");
  assert(parse("HTTP/1.1 202 Accepted\r\nContent-Length: 2\r\n\r\n{}",5,out,202)&&out=="{}");
  assert(!parse("HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n\r\n",5,out));
  assert(parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhe\r\n3;ext=x\r\nllo\r\n0\r\nX-T: yes\r\n\r\n",5,out)&&out=="hello");
  assert(!parse("HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nhello!",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nContent-Length: 99999999999999999999\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nContent-Length: 0\r\nTransfer-Encoding: chunked\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 302 Found\r\nContent-Length: 0\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nabc",5,out));
  assert(!parse("HTTP/1.1 200 OK\nContent-Length: 0\n\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n6\r\nhello!\r\n0\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\nhiX\n0\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\nContent-Length: 0\r\n\r\n",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\n\r\nabc",5,out));
  assert(!parse("HTTP/1.1 200 OK\r\nX-Test: "+std::string(4200,'x')+"\r\nContent-Length: 0\r\n\r\n",5,out));
  Reader redirect("HTTP/1.1 302 Found\r\nLocation: https://example.test/"+std::string(1800,'a')+"\r\nContent-Length: 0\r\n\r\n");
  direct::HttpResponse<Reader> parser(redirect);uint8_t buf[1];size_t used=0;char location[2048];
  assert(parser.read(buf,sizeof(buf),used,302,location,sizeof(location)));
  assert(strlen(location)>1800);
  const char *path=nullptr;
  assert(direct::artifact_path("https://surplus-artifacts-569215998804.s3.us-east-1.amazonaws.com/object?sig=test",path));
  assert(path[0]=='/');
  assert(!direct::artifact_path("https://surplus-artifacts-569215998804.s3.us-east-1.amazonaws.com.evil.test/object",path));
  assert(!direct::artifact_path("http://surplus-artifacts-569215998804.s3.us-east-1.amazonaws.com/object",path));
  assert(!direct::artifact_path("https://surplus-artifacts-569215998804.s3.us-east-1.amazonaws.com/a\nAuthorization:bad",path));
}
