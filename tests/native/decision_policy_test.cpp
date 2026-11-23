#include "../../direct/decision_policy.h"
#include <assert.h>

int main() {
  JsonDocument doc;
  assert(!deserializeJson(doc,R"({"data":[
    {"id":"clef-api","type":"decision","model_spec":{"offline":false,"pricing":{"input":{"diem":0.05},"output":{"diem":0.05}}}},
    {"id":"jev-latest","type":"decision","model_spec":{"offline":false,"pricing":{"input":{"diem":0.042},"output":{"diem":0}}}},
    {"id":"unknown","type":"decision","model_spec":{"offline":false,"pricing":{"input":{"diem":0},"output":{"diem":0}}}}
  ]})"));
  assert(strcmp(direct::cheapest_decision(doc),"jev-latest")==0);
  doc["data"][1]["model_spec"]["offline"]=true;
  assert(strcmp(direct::cheapest_decision(doc),"clef-api")==0);
  doc["data"][0]["model_spec"]["pricing"]["input"].remove("diem");
  assert(direct::cheapest_decision(doc)==nullptr);
  JsonDocument response;
  assert(!deserializeJson(response,R"({"answers":{"route":{"type":"choice","choice":"image","confidence":0.9}}})"));
  const char *choice=nullptr;double confidence=0;
  assert(direct::decision_answer(response,choice,confidence)&&!strcmp(choice,"image")&&confidence>0.89);
  response["answers"]["route"]["confidence"]=1.5;
  assert(!direct::decision_answer(response,choice,confidence));
  response["answers"]["route"]["confidence"]=0.8;
  response["answers"]["route"]["choice"]="video";
  assert(!direct::decision_answer(response,choice,confidence));
}
