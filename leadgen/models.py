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
    officers: list = field(default_factory=list)  # "Name, Title" from state filings
    roles: list = field(default_factory=list)     # e.g. operator, pipeline, water hauler
    audit: dict = field(default_factory=dict)
    score: int = 0
    reasons: list = field(default_factory=list)
    pitch: list = field(default_factory=list)

    @property
    def key(self) -> str:
        """Same company across sources: normalized name (suffixes and punctuation stripped)."""
        import re
        n = self.name.lower().replace("&", " and ")
        n = re.sub(r"\b(l\.?l\.?c|inc|incorporated|corp|corporation|co|company|ltd|l\.?p|llp|the)\b\.?", " ", n)
        return re.sub(r"[^a-z0-9]+", "", n)


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
            for attr in ("officers", "roles"):
                for v in getattr(c, attr):
                    if v not in getattr(base, attr):
                        getattr(base, attr).append(v)
            if c.source not in base.source.split("+"):
                base.source += "+" + c.source
    return list(seen.values())
