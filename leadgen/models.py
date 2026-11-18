"""Shared data model and CSV/JSON persistence."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Company:
    name: str
    city: str = ""
    state: str = ""
    address: str = ""
    zip: str = ""
    phone: str = ""
    website: str = ""
    source: str = ""
    source_id: str = ""
    website_source: str = ""  # how the site was found: seed / places / guess
    audit: dict = field(default_factory=dict)
    score: int = 0
    reasons: list = field(default_factory=list)
    pitch: list = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.name.lower().strip()}|{self.state.lower()}"


def save_json(companies: list[Company], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(c) for c in companies], indent=2))


def load_json(path: Path) -> list[Company]:
    return [Company(**row) for row in json.loads(path.read_text())]


def load_seed_csv(path: Path) -> list[Company]:
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row.get("name"):
                continue
            out.append(Company(
                name=row["name"].strip(),
                city=row.get("city", "").strip(),
                state=row.get("state", "").strip().upper(),
                phone=row.get("phone", "").strip(),
                website=row.get("website", "").strip(),
                source=row.get("source", "seed").strip() or "seed",
                website_source="seed" if row.get("website") else "",
            ))
    return out


def merge(*lists: list[Company]) -> list[Company]:
    """Dedupe by name+state; keep the first record but fill blanks from later ones."""
    seen: dict[str, Company] = {}
    for lst in lists:
        for c in lst:
            if c.key not in seen:
                seen[c.key] = c
                continue
            base = seen[c.key]
            for attr in ("city", "address", "zip", "phone", "website", "website_source"):
                if not getattr(base, attr) and getattr(c, attr):
                    setattr(base, attr, getattr(c, attr))
    return list(seen.values())
