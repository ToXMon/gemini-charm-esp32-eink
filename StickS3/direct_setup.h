#pragma once

// Direct provisioning accepts credentials only over the local USB serial port.
// NVS is not necessarily encrypted: physical access may expose stored secrets.
constexpr uint32_t SETUP_HOLD_MS=10000;
struct DirectConfig {
  uint32_t magic;
  char ssid[33], password[64], venice[256], surplus[256];
};
constexpr uint32_t DIRECT_CONFIG_MAGIC=0x44563101;

bool directSafe(const char *s,size_t capacity,size_t low,bool noSpaces) {
  size_t n=strnlen(s,capacity);
  if(n<low||n>=capacity)return false;
  for(size_t i=0;i<n;i++) {
    unsigned char c=(unsigned char)s[i];
    if(c<32||c==127||(noSpaces&&c<=32))return false;
  }
  return true;
}
bool directConfigValid(const DirectConfig &c) {
  return c.magic==DIRECT_CONFIG_MAGIC&&directSafe(c.ssid,sizeof(c.ssid),1,false)&&
         directSafe(c.password,sizeof(c.password),8,false)&&
         directSafe(c.venice,sizeof(c.venice),10,true)&&directSafe(c.surplus,sizeof(c.surplus),10,true);
}
bool loadDirectConfig() {
  DirectConfig c{};
  bool ok=prefs.getBytesLength("config")==sizeof(c)&&prefs.getBytes("config",&c,sizeof(c))==sizeof(c)&&directConfigValid(c);
  if(ok){ssid=c.ssid;password=c.password;veniceKey=c.venice;surplusKey=c.surplus;}
  memset(&c,0,sizeof(c));
  return ok;
}
void enterSetupMode() {
  if(setupMode)return;
  stopSession("USB setup");
  setupMode=true;
  WiFi.disconnect(false,false);WiFi.mode(WIFI_OFF);
  showScreen(MODE_PANEL,"USB SETUP","Use the Mac to configure Wi-Fi and API keys over USB.","A: cancel",false);
  Serial.println("DIRECT_SETUP_READY");
}
void cancelSetupMode() {
  if(!configured)return;
  Serial.println("DIRECT_SETUP_CANCELLED");Serial.flush();delay(100);ESP.restart();
}
void setupLoop() {}

bool directCopy(char *out,size_t n,JsonVariantConst value) {
  const char *s=value.as<const char*>();
  if(!s)return false;
  size_t len=strnlen(s,n);if(len>=n)return false;
  memcpy(out,s,len+1);return true;
}
void readDirectSetup() {
  static bool overflow=false;
  while(Serial.available()) {
    char ch=Serial.read();
    if(ch!='\n') {
      if(!overflow&&serialLine.length()<2048)serialLine+=ch;
      else overflow=true;
      continue;
    }
    if(overflow){serialLine="";overflow=false;Serial.println("DIRECT_CONFIG_INVALID");continue;}
    JsonDocument doc;
    DeserializationError error=deserializeJson(doc,serialLine);
    serialLine="";
    if(error)continue;
    if(doc["command"]=="direct_status") {
      Serial.println(setupMode?"DIRECT_SETUP_READY":"DIRECT_SETUP_INACTIVE");continue;
    }
    if(setupMode&&doc["command"]=="music_reconciled") {
      Serial.println(directReconcileMusic()?"DIRECT_MUSIC_RECONCILED":"DIRECT_MUSIC_RECONCILE_FAILED");continue;
    }
    if(!setupMode||doc["command"]!="configure_direct")continue;
    DirectConfig c{};c.magic=DIRECT_CONFIG_MAGIC;
    bool ok=directCopy(c.ssid,sizeof(c.ssid),doc["ssid"])&&
            directCopy(c.password,sizeof(c.password),doc["password"])&&
            directCopy(c.venice,sizeof(c.venice),doc["venice_key"])&&
            directCopy(c.surplus,sizeof(c.surplus),doc["surplus_key"])&&directConfigValid(c);
    if(ok)ok=prefs.putBytes("config",&c,sizeof(c))==sizeof(c);
    memset(&c,0,sizeof(c));
    if(!ok){Serial.println("DIRECT_CONFIG_INVALID");continue;}
    Serial.println("DIRECT_CONFIG_SAVED");Serial.flush();delay(100);ESP.restart();
  }
}
