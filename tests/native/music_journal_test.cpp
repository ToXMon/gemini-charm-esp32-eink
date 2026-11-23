#include "../../direct/music_journal.h"
#include <assert.h>

struct MemoryStore : direct::Store {
  direct::Record value{};
  bool present = false, fail_read = false, fail_write = false;
  direct::Load read(direct::Record &out) override {
    if (fail_read) return direct::Load::error;
    if (!present) return direct::Load::missing;
    out = value; return direct::Load::ok;
  }
  bool write(const direct::Record &v) override {
    if (fail_write) return false;
    value = v; present = true; return true;
  }
};

int main() {
  MemoryStore s;
  direct::MusicJournal first(s);
  assert(!first.can_submit() && first.load() && first.can_submit());
  assert(first.begin() && !first.can_submit());
  direct::MusicJournal after_crash(s);
  assert(after_crash.load() && after_crash.phase() == direct::Phase::uncertain);
  assert(!after_crash.begin() && !after_crash.identify("bad/path"));
  assert(after_crash.identify("job-123") && !after_crash.can_submit());
  direct::MusicJournal after_restart(s);
  assert(after_restart.load() && strcmp(after_restart.job_id(), "job-123") == 0);
  assert(!after_restart.begin() && after_restart.acknowledge_reconciled());
  assert(after_restart.can_submit());
  assert(after_restart.begin());
  s.fail_write = true;
  assert(!after_restart.identify("job-456") && !after_restart.can_submit());
  s.fail_write = false;
  direct::MusicJournal after_failed_identify(s);
  assert(after_failed_identify.load() && after_failed_identify.phase() == direct::Phase::uncertain);
  assert(after_failed_identify.acknowledge_reconciled());
  s.fail_write = true;
  assert(!after_failed_identify.begin() && !after_failed_identify.can_submit());
  s.fail_write = false;
  s.fail_read = true;
  assert(!after_restart.load() && !after_restart.can_submit());
  s.fail_read = false;
  s.value.magic = 0;
  assert(!after_restart.load() && !after_restart.can_submit());
  return 0;
}
