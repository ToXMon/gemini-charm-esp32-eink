#include "../../direct/wav.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc,char **argv) {
  if(argc!=2)return 2;
  std::ifstream file(argv[1],std::ios::binary|std::ios::ate);
  if(!file)return 2;
  const std::streamoff size=file.tellg();
  if(size<=0||size>2*1024*1024)return 1;
  file.seekg(0);
  std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
  direct::WavView view;
  if(!direct::parse_wav(bytes.data(),bytes.size(),view))return 1;
  std::cout<<"Validated PCM16 WAV: rate="<<view.rate<<" channels="<<view.channels<<" frames="<<view.frames<<'\n';
  return 0;
}
