"""What the meadow remembers between runs: which events have been seen,
how often and when, and the first day it ever ran.

A small JSON file in the user's application-support folder.  Writing is
atomic (write a temporary file, then rename), so a screensaver killed
mid-write never leaves a broken journal behind.
"""

import datetime
import json
import os
import sys
import tempfile


def default_path():
    override = os.environ.get("MEADOW_JOURNAL")
    if override:
        return override
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "Meadow", "journal.json")


class Journal:
    """Seen events.  ``path`` None keeps everything in memory (tests)."""

    def __init__(self, path=None, today=None):
        self.path = path
        self.seen = {}           # name -> {"count": n, "first": iso, "last": iso}
        self.notes = {}          # small facts: last snow date, ...
        self.since = (today or datetime.date.today()).isoformat()
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.seen = dict(data.get("seen", {}))
                self.notes = dict(data.get("notes", {}))
                self.since = data.get("since", self.since)
            except (OSError, ValueError, AttributeError):
                pass  # unreadable: start afresh rather than refuse to run

    def record(self, name, when):
        stamp = when.isoformat(timespec="minutes")
        entry = self.seen.setdefault(name, {"count": 0, "first": stamp})
        entry["count"] += 1
        entry["last"] = stamp
        self.save()

    def note(self, key, value):
        self.notes[key] = value
        self.save()

    def count(self, name):
        return self.seen.get(name, {}).get("count", 0)

    def save(self):
        if not self.path:
            return
        data = {"since": self.since, "seen": self.seen, "notes": self.notes}
        folder = os.path.dirname(self.path)
        try:
            os.makedirs(folder, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=".journal-", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except OSError:
            pass  # a read-only home must not stop the meadow
