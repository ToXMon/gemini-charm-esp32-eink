#pragma once
#include "../direct/music_journal_nvs.h"

// Experimental direct music path. Unknown and failed jobs retain their ID or
// uncertainty marker; the user must reconcile them before another submission.
enum class DirectMusicOutcome {pending,finished,attention};
bool directHasPendingMusic(){
  nvs_handle_t handle;if(nvs_open("directmusic",NVS_READWRITE,&handle)!=ESP_OK)return false;
  direct::NvsMusicStore store(handle);direct::MusicJournal journal(store);
  bool pending=journal.load()&&journal.phase()==direct::Phase::identified;
  nvs_close(handle);return pending;
}
bool directReconcileMusic(){
  nvs_handle_t handle;if(nvs_open("directmusic",NVS_READWRITE,&handle)!=ESP_OK)return false;
  direct::NvsMusicStore store(handle);direct::MusicJournal journal(store);
  bool ok=journal.load()&&journal.acknowledge_reconciled();nvs_close(handle);return ok;
}
DirectMusicOutcome directMusic(const String &prompt){
  nvs_handle_t handle;
  if(nvs_open("directmusic",NVS_READWRITE,&handle)!=ESP_OK){appState=APP_READY;status("Music storage error");return DirectMusicOutcome::attention;}
  direct::NvsMusicStore store(handle);direct::MusicJournal journal(store);
  if(!journal.load()){nvs_close(handle);appState=APP_READY;status("Music state unreadable");return DirectMusicOutcome::attention;}
  if(journal.phase()==direct::Phase::uncertain){
    nvs_close(handle);appState=APP_READY;status("Check previous music job");return DirectMusicOutcome::attention;
  }
  if(journal.can_submit()&&prompt.isEmpty()){nvs_close(handle);return DirectMusicOutcome::finished;}
  constexpr size_t MAX_JSON=16384;
  uint8_t *buffer=(uint8_t*)ps_malloc(MAX_JSON+1);
  if(!buffer){nvs_close(handle);appState=APP_READY;status("Memory unavailable");return DirectMusicOutcome::attention;}
  if(journal.can_submit()){
    showScreen(MODE_BUSY,"Writing...","Preparing music",MAIN_BTN_NAME ": cancel",false);
    String musicPrompt;
    if(!directDraft(prompt,"Write a concise music generation prompt for the user's request. Return only the prompt.",musicPrompt)){
      free(buffer);nvs_close(handle);appState=APP_READY;status(genCancel?"Cancelled":"Music prompt failed");return DirectMusicOutcome::attention;
    }
    JsonDocument request;request["model"]="venice-ace-step-15";request["prompt"]=musicPrompt;
    String body;serializeJson(request,body);
    if(body.length()>8192||genCancel||!journal.begin()){
      free(buffer);nvs_close(handle);appState=APP_READY;status(genCancel?"Cancelled":"Music storage error");return DirectMusicOutcome::attention;
    }
    showScreen(MODE_BUSY,"Creating...","Music may be charged",MAIN_BTN_NAME ": cancel",false);
    size_t n=0;
    bool ok=directJsonRequest("api.surplusintelligence.ai",HERMES_ROOTS,"POST","/v1/music/generations",surplusKey,body,buffer,MAX_JSON,n,202);
    JsonDocument submitted;
    if(ok)ok=!deserializeJson(submitted,buffer,n);
    const char *id=ok?(submitted["id"] | (const char*)nullptr):nullptr;
    if(!id||!journal.identify(id)){
      free(buffer);nvs_close(handle);appState=APP_READY;status("Music outcome unknown");return DirectMusicOutcome::attention;
    }
  }
  String job=journal.job_id();uint32_t started=millis();uint32_t interval=2000;
  while(!genCancel&&millis()-started<180000){
    vTaskDelay(pdMS_TO_TICKS(interval));interval=min((uint32_t)10000,interval+1000);
    String path=String("/v1/music/generations/")+job;size_t n=0;
    bool ok=directJsonRequest("api.surplusintelligence.ai",HERMES_ROOTS,"GET",path.c_str(),surplusKey,"",buffer,MAX_JSON,n);
    JsonDocument result;
    if(!ok||deserializeJson(result,buffer,n))break;
    String state=result["status"] | "";
    if(state=="succeeded"||state=="completed"){
      char *location=(char*)ps_malloc(2048);
      if(!location){free(buffer);nvs_close(handle);appState=APP_READY;status("Memory unavailable");return DirectMusicOutcome::attention;}
      String artifact=String("/v1/media/artifacts/")+job+"/0";n=0;
      ok=directJsonRequest("api.surplusintelligence.ai",HERMES_ROOTS,"GET",artifact.c_str(),surplusKey,"",buffer,MAX_JSON,n,302,location,2048);
      const char *path=nullptr;
      if(ok)ok=direct::artifact_path(location,path);
      constexpr size_t MAX_FLAC=4608*1024;
      uint8_t *audio=ok?(uint8_t*)ps_malloc(MAX_FLAC):nullptr;
      if(!audio)ok=false;
      n=0;
      if(ok)ok=directJsonRequest(direct::ARTIFACT_HOST,ARTIFACT_ROOTS,"GET",path,"","",audio,MAX_FLAC,n);
      free(location);
      if(ok&&!genCancel){
        appState=APP_PLAYING;showScreen(MODE_PANEL,"SONG",prompt.isEmpty()?String("Generated song"):prompt,MAIN_BTN_NAME ": stop",true);
        ok=directPlayFlac(audio,n);
      }
      free(audio);
      if(!ok){free(buffer);nvs_close(handle);appState=APP_READY;status(genCancel?"Song stopped; job saved":"Song download or format failed");return DirectMusicOutcome::attention;}
      bool saved=journal.acknowledge_reconciled();
      free(buffer);nvs_close(handle);appState=APP_RESULT;
      if(saved)showScreen(MODE_PANEL,"SONG","Song finished",RESULT_FOOTER,true);
      else {appState=APP_READY;status("Music storage error");}
      return saved?DirectMusicOutcome::finished:DirectMusicOutcome::attention;
    }
    if(state=="failed"||state=="expired"||state=="canceled"||state=="cancelled"){
      free(buffer);nvs_close(handle);appState=APP_READY;status("Music failed; check account");return DirectMusicOutcome::attention;
    }
    if(state!="queued"&&state!="submitted"&&state!="running")break;
  }
  free(buffer);nvs_close(handle);appState=APP_READY;status(genCancel?"Song stopped; job saved":"Music pending; no retry sent");
  return genCancel?DirectMusicOutcome::attention:DirectMusicOutcome::pending;
}
