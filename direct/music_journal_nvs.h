#pragma once

#include "music_journal.h"
#include <nvs.h>

namespace direct {
// One NVS blob; keep this namespace/key separate from credentials. NVS is not
// necessarily encrypted. This stores only a job ID and state, never the prompt.
class NvsMusicStore : public Store {
 public:
  explicit NvsMusicStore(nvs_handle_t handle) : handle_(handle) {}
  Load read(Record &record) override {
    size_t size = sizeof(record);
    esp_err_t err = nvs_get_blob(handle_, "music_job", &record, &size);
    if (err == ESP_ERR_NVS_NOT_FOUND) return Load::missing;
    return err == ESP_OK && size == sizeof(record) ? Load::ok : Load::error;
  }
  bool write(const Record &record) override {
    return nvs_set_blob(handle_, "music_job", &record, sizeof(record)) == ESP_OK &&
           nvs_commit(handle_) == ESP_OK;
  }
 private:
  nvs_handle_t handle_;
};
} // namespace direct
