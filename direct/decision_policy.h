#pragma once
#include <ArduinoJson.h>
#include <math.h>
#include <string.h>

namespace direct {
// Only models whose JEV request dialect is explicitly supported are eligible.
// Prices are indicative DIEM rates, not quality evidence or a bill.
inline const char *cheapest_decision(const JsonDocument &doc) {
  JsonArrayConst models=doc["data"].as<JsonArrayConst>();
  const char *best=nullptr;double best_cost=0;
  for(JsonObjectConst m:models) {
    const char *id=m["id"] | "";const char *type=m["type"] | "";
    if(strcmp(type,"decision")||(strcmp(id,"jev-latest")&&strcmp(id,"clef-api")))continue;
    JsonVariantConst spec=m["model_spec"];
    if(!spec["offline"].is<bool>()||spec["offline"].as<bool>())continue;
    JsonVariantConst in=spec["pricing"]["input"]["diem"],out=spec["pricing"]["output"]["diem"];
    if(!in.is<double>()||!out.is<double>())continue;
    double a=in.as<double>(),b=out.as<double>();
    if(!isfinite(a)||!isfinite(b)||a<0||b<0)continue;
    double cost=a*1000+b*100;
    if(!isfinite(cost))continue;
    if(!best||cost<best_cost||(cost==best_cost&&strcmp(id,best)<0)){best=id;best_cost=cost;}
  }
  return best;
}
inline bool decision_answer(const JsonDocument &doc,const char *&choice,double &confidence) {
  JsonVariantConst answer=doc["answers"]["route"];
  const char *type=answer["type"] | "";
  const char *value=answer["choice"] | "";
  JsonVariantConst c=answer["confidence"];
  if(strcmp(type,"choice")||!c.is<double>())return false;
  if(strcmp(value,"image")&&strcmp(value,"song")&&strcmp(value,"speech")&&strcmp(value,"clarify"))return false;
  double number=c.as<double>();
  if(!isfinite(number)||number<0||number>1)return false;
  choice=value;confidence=number;return true;
}
} // namespace direct
