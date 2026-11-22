#pragma once
#include "image_dither.h"

// The host owns the Surplus key; the device only stores a separate bridge token.
const char *DEFAULT_VOICE="bridge";
const char *RESULT_FOOTER=MAIN_BTN_NAME ": new | " SIDE_BTN_NAME ": again";

struct BridgeReply { uint8_t *data=nullptr; size_t len=0; String action; ~BridgeReply(){free(data);} };

bool bridgeRequest(const char *method,const char *path,const uint8_t *body,size_t len,const char *type,BridgeReply &out,int &code) {
  NetworkClientSecure client; client.setCACert(HERMES_ROOTS); client.setTimeout(180);
  HTTPClient http; http.setTimeout(60000); http.setConnectTimeout(15000);
  String url=String("https://")+BRIDGE_HOST+":"+BRIDGE_PORT+path;
  if(!http.begin(client,url))return false;
  const char *keys[]={"X-Action"}; http.collectHeaders(keys,1);
  http.addHeader("Authorization",String("Bearer ")+apiKey);http.addHeader("Content-Type",type);
  code=strcmp(method,"GET")==0?http.GET():http.POST((uint8_t*)body,len);
  if(code==202&&strcmp(method,"GET")==0){http.end();return true;}
  if((code!=200&&code!=202)||genCancel){http.end();return false;}
  int n=http.getSize();
  if(n<=0||n>2*1024*1024){http.end();return false;}
  out.data=(uint8_t*)ps_malloc(n+1); if(!out.data){http.end();return false;}
  out.action=http.header("X-Action"); auto *stream=http.getStreamPtr();
  uint32_t last=millis();
  while(out.len<(size_t)n&&!genCancel){
    int available=stream->available();
    if(available>0){int got=stream->readBytes(out.data+out.len,min((size_t)available,(size_t)n-out.len));if(got>0){out.len+=got;last=millis();}}
    else if(millis()-last>30000||!http.connected())break;
    else vTaskDelay(pdMS_TO_TICKS(5));
  }
  http.end();out.data[out.len]=0;return out.len==(size_t)n&&!genCancel;
}

void bridgeTranscribe(){
  BridgeReply reply; int code=0;
  if(!bridgeRequest("POST","/stick/transcribe",recordPcm,recordLen,"application/octet-stream",reply,code)){
    createAfterTranscribe=false;appState=APP_READY;status(genCancel?"Cancelled":"Transcription failed");return;
  }
  JsonDocument doc;
  if(deserializeJson(doc,reply.data,reply.len)||!doc["text"].is<const char*>()){
    createAfterTranscribe=false;appState=APP_READY;status("Bad transcript");return;
  }
  sessionPrompt=doc["text"].as<String>();sessionPrompt.trim();
  if(sessionPrompt.isEmpty()){createAfterTranscribe=false;appState=APP_READY;status("No speech recognized");return;}
  if(createAfterTranscribe){createAfterTranscribe=false;genPrompt=sessionPrompt;transcribeJob=false;return;}
  appState=APP_PROMPT;showScreen(MODE_PROMPT,"PROMPT",sessionPrompt,PROMPT_FOOTER,false);
}

void bridgeCreate(const String &prompt){
  showScreen(MODE_BUSY,"Creating...",prompt,MAIN_BTN_NAME ": cancel",false);
  JsonDocument request;request["prompt"]=prompt;String body;serializeJson(request,body);
  BridgeReply submitted; int code=0;
  if(!bridgeRequest("POST","/stick/create",(const uint8_t*)body.c_str(),body.length(),"application/json",submitted,code)||code!=202){
    appState=APP_READY;status(genCancel?"Cancelled":"Generation failed");return;
  }
  JsonDocument result;
  if(deserializeJson(result,submitted.data,submitted.len)||!result["job_id"].is<const char*>()){
    appState=APP_READY;status("Invalid job");return;
  }
  String job=result["job_id"].as<String>();
  if(job.length()<8||job.length()>64){appState=APP_READY;status("Invalid job");return;}
  for(size_t i=0;i<job.length();i++)if(!isalnum((unsigned char)job[i])&&job[i]!='-'&&job[i]!='_'){appState=APP_READY;status("Invalid job");return;}
  String path="/stick/jobs/"+job; BridgeReply reply; uint32_t started=millis();
  do {
    if(genCancel){appState=APP_READY;status("Cancelled");return;}
    vTaskDelay(pdMS_TO_TICKS(2000));
    if(!bridgeRequest("GET",path.c_str(),nullptr,0,"application/json",reply,code)){
      appState=APP_READY;status(genCancel?"Cancelled":"Generation failed");return;
    }
  } while(code==202&&millis()-started<180000);
  if(code!=200){appState=APP_READY;status("Generation timed out");return;}
  if(reply.action=="image"){
    uint16_t *decoded=(uint16_t*)ps_malloc((size_t)SCREEN_W*SCREEN_H*sizeof(uint16_t));
    if(!decoded||!imageRgb565||!jpegToRgb565(reply.data,reply.len,decoded,SCREEN_W,SCREEN_H)){
      free(decoded);appState=APP_READY;status("Image decode failed");return;
    }
    xSemaphoreTake(screenLock,portMAX_DELAY);memcpy(imageRgb565,decoded,(size_t)SCREEN_W*SCREEN_H*sizeof(uint16_t));xSemaphoreGive(screenLock);free(decoded);
    appState=APP_RESULT;showScreen(MODE_IMAGE,"",prompt,"",false);return;
  }
  if(reply.action!="speech"&&reply.action!="song"){appState=APP_READY;status("Unknown result");return;}
  // Bridge returns raw 16 kHz signed little-endian mono PCM, bounded to 2 MiB.
  if(reply.len%2){appState=APP_READY;status("Invalid audio");return;}
  setCodecRate(16000);appState=APP_PLAYING;
  showScreen(MODE_PANEL,reply.action=="song"?"SONG":"SPEECH",prompt,MAIN_BTN_NAME ": stop",true);
  enqueueAudioWait((int16_t*)reply.data,reply.len/2);waitPlaybackDone();
  if(genCancel){clearAudio();appState=APP_READY;status("Cancelled");return;}
  appState=APP_RESULT;showScreen(MODE_PANEL,reply.action=="song"?"SONG":"SPEECH",prompt,RESULT_FOOTER,true);
}

void genTask(void*){
  for(;;){
    ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
    if(transcribeJob){bridgeTranscribe();if(!transcribeJob&&!genCancel&&!genPrompt.isEmpty())bridgeCreate(genPrompt);}
    else bridgeCreate(genPrompt);
    transcribeJob=false;genPrompt="";genBusy=false;
  }
}
