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
// Local USB diagnostics may report a job identifier, never a key or prompt.
// Refuse while the worker is active so the record is not inspected mid-update.
void directMusicDiagnostics(){
  if(genBusy){Serial.println("DIRECT_MUSIC_STATE busy");return;}
  nvs_handle_t handle;
  if(nvs_open("directmusic",NVS_READWRITE,&handle)!=ESP_OK){Serial.println("DIRECT_MUSIC_STATE storage_error");return;}
  direct::NvsMusicStore store(handle);direct::MusicJournal journal(store);
  if(!journal.load())Serial.println("DIRECT_MUSIC_STATE unreadable");
  else if(journal.phase()==direct::Phase::uncertain)Serial.println("DIRECT_MUSIC_STATE uncertain");
  else if(journal.phase()==direct::Phase::identified)Serial.printf("DIRECT_MUSIC_STATE identified %s\n",journal.job_id());
  else Serial.println("DIRECT_MUSIC_STATE empty");
  nvs_close(handle);
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
      Serial.printf("DIRECT_MUSIC_STAGE artifact_redirect=%d\n",ok);
      const char *path=nullptr;
      if(ok)ok=direct::artifact_path(location,path);
      Serial.printf("DIRECT_MUSIC_STAGE artifact_origin=%d\n",ok);
      // Recording and music playback are exclusive. Release the recording
      // buffer while holding a bounded larger artifact, then restore it.
      bool releasedRecording=false;
      if(ok&&recordPcm){free(recordPcm);recordPcm=nullptr;recordLen=0;releasedRecording=true;}
      uint8_t *audio=ok?(uint8_t*)ps_malloc(MAX_DIRECT_FLAC):nullptr;
      if(!audio)ok=false;
      Serial.printf("DIRECT_MUSIC_STAGE audio_buffer=%d\n",audio!=nullptr);
      n=0;
      if(ok)ok=directJsonRequest(direct::ARTIFACT_HOST,ARTIFACT_ROOTS,"GET",path,"","",audio,MAX_DIRECT_FLAC,n);
      Serial.printf("DIRECT_MUSIC_STAGE audio_download=%d bytes=%u\n",ok,(unsigned)n);
      free(location);
      if(ok&&!genCancel){
        appState=APP_PLAYING;showScreen(MODE_PANEL,"SONG",prompt.isEmpty()?String("Generated song"):prompt,MAIN_BTN_NAME ": stop",true);
        ok=directPlayFlac(audio,n);
        Serial.printf("DIRECT_MUSIC_STAGE playback=%d\n",ok);
      }
      free(audio);
      if(releasedRecording)recordPcm=(uint8_t*)ps_malloc(RECORD_MAX);
      bool recordReady=recordPcm!=nullptr;
      Serial.printf("DIRECT_MUSIC_STAGE recording_buffer=%d\n",recordReady);
      if(!ok){free(buffer);nvs_close(handle);appState=APP_READY;status(genCancel?"Song stopped; job saved":"Song download or format failed");return DirectMusicOutcome::attention;}
      bool saved=journal.acknowledge_reconciled();
      free(buffer);nvs_close(handle);appState=APP_RESULT;
      if(saved&&recordReady)showScreen(MODE_PANEL,"SONG","Song finished",RESULT_FOOTER,true);
      else if(saved)status("Song finished; restart to record");
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
