#pragma once
#include <stddef.h>
#include <string.h>

namespace direct {
// Current Surplus artifact origin, deliberately narrow. Other origins fail
// closed until their TLS roots and redirect behavior have been reviewed.
static const char ARTIFACT_HOST[]="surplus-artifacts-569215998804.s3.us-east-1.amazonaws.com";
inline bool artifact_path(const char *url,const char *&path) {
  static const char prefix[]="https://surplus-artifacts-569215998804.s3.us-east-1.amazonaws.com";
  if(!url||strncmp(url,prefix,sizeof(prefix)-1))return false;
  path=url+sizeof(prefix)-1;
  if(*path!='/')return false;
  size_t n=strnlen(path,2048);
  if(!n||n>=2048)return false;
  for(size_t i=0;i<n;i++) {
    unsigned char c=(unsigned char)path[i];
    if(c<33||c>126||c=='#'||c=='\\')return false;
  }
  return true;
}
} // namespace direct
