#define DR_FLAC_IMPLEMENTATION
#define DR_FLAC_NO_STDIO
#define DR_FLAC_NO_OGG
#define DR_FLAC_NO_SIMD
#include "../../StickS3/src/dr_flac.h"
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

struct Budget {
  struct alignas(16) Header {size_t size;};
  size_t used=0,peak=0;
  static constexpr size_t limit=1024*1024;
  static void *alloc(size_t n,void *ctx){
    auto *b=(Budget*)ctx;if(n>limit-b->used)return nullptr;
    auto *h=(Header*)malloc(sizeof(Header)+n);if(!h)return nullptr;
    h->size=n;b->used+=n;if(b->used>b->peak)b->peak=b->used;return h+1;
  }
  static void release(void *p,void *ctx){
    if(!p)return;auto *b=(Budget*)ctx;auto *h=((Header*)p)-1;b->used-=h->size;free(h);
  }
  static void *resize(void *p,size_t n,void *ctx){
    if(!p)return alloc(n,ctx);
    if(!n){release(p,ctx);return nullptr;}
    auto *b=(Budget*)ctx;auto *h=((Header*)p)-1;size_t old=h->size;
    if(n>limit-(b->used-old))return nullptr;
    auto *next=(Header*)realloc(h,sizeof(Header)+n);if(!next)return nullptr;
    next->size=n;b->used=b->used-old+n;if(b->used>b->peak)b->peak=b->used;return next+1;
  }
};

int main(int argc,char **argv) {
  if(argc!=2)return 2;
  std::ifstream file(argv[1],std::ios::binary|std::ios::ate);
  if(!file)return 2;
  auto size=file.tellg();
  if(size<=0||size>6*1024*1024)return 1;
  file.seekg(0);
  std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
  Budget budget;drflac_allocation_callbacks callbacks={&budget,Budget::alloc,Budget::resize,Budget::release};
  drflac *flac=drflac_open_memory(bytes.data(),bytes.size(),&callbacks);
  if(!flac)return 1;
  bool ok=flac->channels>=1&&flac->channels<=2&&flac->sampleRate>=8000&&flac->sampleRate<=48000&&
          flac->totalPCMFrameCount&&flac->totalPCMFrameCount<=uint64_t(flac->sampleRate)*65;
  uint64_t frames=0;int16_t buffer[512*2];
  while(ok) {
    auto n=drflac_read_pcm_frames_s16(flac,512,buffer);
    if(!n)break;
    frames+=n;
    if(frames>flac->totalPCMFrameCount)ok=false;
  }
  if(frames!=flac->totalPCMFrameCount)ok=false;
  if(ok)std::cout<<"Validated FLAC: rate="<<flac->sampleRate<<" channels="<<unsigned(flac->channels)<<" frames="<<frames<<" decoder_peak_bytes="<<budget.peak<<'\n';
  drflac_close(flac);
  return ok&&budget.used==0?0:1;
}
