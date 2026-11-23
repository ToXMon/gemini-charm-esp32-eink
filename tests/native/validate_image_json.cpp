#define ARDUINOJSON_STRING_LENGTH_SIZE 4
#include <ArduinoJson.h>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

struct Budget : ArduinoJson::Allocator {
  struct alignas(16) Header {size_t size;};
  size_t used=0,peak=0;
  static constexpr size_t limit=2*1024*1024+65536;
  void *allocate(size_t n) override {
    if(n>limit-used)return nullptr;
    auto *h=(Header*)malloc(sizeof(Header)+n);if(!h)return nullptr;
    h->size=n;used+=n;if(used>peak)peak=used;return h+1;
  }
  void deallocate(void *p) override {
    if(!p)return;auto *h=((Header*)p)-1;used-=h->size;free(h);
  }
  void *reallocate(void *p,size_t n) override {
    if(!p)return allocate(n);
    if(!n){deallocate(p);return nullptr;}
    auto *h=((Header*)p)-1;size_t old=h->size;if(n>limit-(used-old))return nullptr;
    auto *next=(Header*)realloc(h,sizeof(Header)+n);if(!next)return nullptr;
    next->size=n;used=used-old+n;if(used>peak)peak=used;return next+1;
  }
};
int main(int argc,char **argv) {
  if(argc!=2)return 2;
  std::ifstream file(argv[1],std::ios::binary|std::ios::ate);
  if(!file||file.tellg()<=0||file.tellg()>2*1024*1024)return 1;
  file.seekg(0);std::vector<char> json((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
  Budget budget;
  {
    JsonDocument doc(&budget);
    auto error=deserializeJson(doc,json.data(),json.size());
    if(error){std::cout<<"Image JSON parse failed: "<<error.c_str()<<" peak="<<budget.peak<<'\n';return 1;}
    const char *encoded=doc["data"][0]["b64_json"] | (const char*)nullptr;
    if(!encoded||!strlen(encoded))return 1;
    std::cout<<"Image JSON parsed: encoded_bytes="<<strlen(encoded)<<" allocator_peak_bytes="<<budget.peak<<'\n';
  }
  return budget.used==0?0:1;
}
