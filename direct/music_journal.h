#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

// A small, transport-independent guard for a single potentially billable job.
// Store::write must atomically persist the entire record before returning true;
// callers must serialize access and must not send a request unless begin() succeeds.
namespace direct {

enum class Load { missing, ok, error };
enum class Phase : uint8_t { empty = 0, uncertain = 1, identified = 2 };

struct Record {
  uint32_t magic;
  uint8_t version;
  Phase phase;
  char job_id[65];
};

class Store {
 public:
  virtual ~Store() = default;
  virtual Load read(Record &record) = 0;
  virtual bool write(const Record &record) = 0;
};

class MusicJournal {
 public:
  explicit MusicJournal(Store &store) : store_(store) {}

  // A corrupt or unreadable record blocks submissions, rather than acting empty.
  bool load() {
    Record next{};
    Load result = store_.read(next);
    if (result == Load::missing) next = make(Phase::empty);
    else if (result != Load::ok || !valid(next)) { healthy_ = false; return false; }
    record_ = next;
    healthy_ = true;
    return true;
  }

  bool can_submit() const { return healthy_ && record_.phase == Phase::empty; }
  Phase phase() const { return record_.phase; }
  const char *job_id() const { return record_.phase == Phase::identified ? record_.job_id : ""; }

  // Commit before any request bytes are sent. Even a crash before transmission
  // leaves an uncertain record, requiring reconciliation rather than a retry.
  bool begin() {
    if (!can_submit()) return false;
    return persist(make(Phase::uncertain));
  }

  // Call only after an authenticated successful submit with a validated job ID.
  bool identify(const char *id) {
    if (!healthy_ || record_.phase != Phase::uncertain || !valid_id(id)) return false;
    Record next = make(Phase::identified);
    memcpy(next.job_id, id, strlen(id) + 1);
    return persist(next);
  }

  // Call only after a terminal result has been handled, or the user has explicitly
  // reconciled an unknown outcome with the provider. Never call on timeout/cancel.
  bool acknowledge_reconciled() {
    if (!healthy_ || record_.phase == Phase::empty) return false;
    return persist(make(Phase::empty));
  }

 private:
  static constexpr uint32_t kMagic = 0x4d4a4f42; // MJOB
  static Record make(Phase phase) { Record r{}; r.magic = kMagic; r.version = 1; r.phase = phase; return r; }
  static bool valid_id(const char *s) {
    if (!s) return false;
    size_t n = 0;
    for (; n < 65 && s[n]; ++n) {
      char c = s[n];
      if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
    }
    return n >= 1 && n <= 64 && s[n] == '\0';
  }
  static bool valid(const Record &r) {
    if (r.magic != kMagic || r.version != 1) return false;
    if (r.phase == Phase::empty || r.phase == Phase::uncertain) return r.job_id[0] == '\0';
    if (r.phase != Phase::identified || !memchr(r.job_id, '\0', sizeof(r.job_id))) return false;
    return valid_id(r.job_id);
  }
  bool persist(const Record &next) {
    if (!store_.write(next)) { healthy_ = false; return false; }
    record_ = next;
    return true;
  }
  Store &store_;
  Record record_{};
  bool healthy_ = false;
};
} // namespace direct
