#include "../../direct/music_journal_nvs.h"
#include <assert.h>

static direct::Record stored;
static bool found = false, get_error = false, set_error = false, commit_error = false;
static int commits = 0;
esp_err_t nvs_get_blob(nvs_handle_t, const char *, void *out, size_t *size) {
  if (get_error) return ESP_FAIL;
  if (!found) return ESP_ERR_NVS_NOT_FOUND;
  if (*size != sizeof(stored)) return ESP_FAIL;
  memcpy(out, &stored, sizeof(stored)); *size = sizeof(stored); return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t, const char *, const void *data, size_t size) {
  if (set_error || size != sizeof(stored)) return ESP_FAIL;
  memcpy(&stored, data, size); found = true; return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t) { ++commits; return commit_error ? ESP_FAIL : ESP_OK; }

int main() {
  direct::NvsMusicStore store(1);
  direct::MusicJournal journal(store);
  assert(journal.load() && journal.can_submit());
  assert(journal.begin() && commits == 1);
  assert(journal.identify("job-1") && commits == 2);
  get_error = true;
  assert(!journal.load() && !journal.can_submit());
  get_error = false;
  assert(journal.load() && journal.phase() == direct::Phase::identified);
  set_error = true;
  assert(!journal.acknowledge_reconciled() && commits == 2 && !journal.can_submit());
  set_error = false;
  assert(journal.load());
  commit_error = true;
  assert(!journal.acknowledge_reconciled() && commits == 3 && !journal.can_submit());
}
