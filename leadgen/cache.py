"""Append-only JSONL caches so multi-hour runs can resume after a restart."""
from __future__ import annotations

import json
import threading
from pathlib import Path


class Cache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, object] = {}
        self._lock = threading.Lock()
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                        self.data[row["k"]] = row["v"]
                    except (ValueError, KeyError):
                        continue  # partial last line from a crash
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def put(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value
            self._fh.write(json.dumps({"k": key, "v": value}) + "\n")
            self._fh.flush()
