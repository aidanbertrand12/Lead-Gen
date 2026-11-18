"""Helpers shared by state regulator sources."""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; LeadGen/0.2)"}
_UPPER_WORDS = re.compile(r"\b(Llc|Lp|Llp|Ltd|Inc|Usa|Us|Ii|Iii|Iv|Swd|Ngl|Lng|E&P|Dba|Pc|Pllc|Ok|Tx|Nm)\b")


def download(url: str, dest: Path, max_age_days: int = 20, retries: int = 4, timeout: int = 300) -> Path:
    """Download with retries; reuse a recent local copy."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and time.time() - dest.stat().st_mtime < max_age_days * 86400 and dest.stat().st_size > 0:
        return dest
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            dest.write_bytes(r.content)
            return dest
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return dest


def title(s) -> str:
    s = re.sub(r"\s+", " ", str(s or "").strip())
    if s.isupper() or s.islower():
        s = s.title().replace("'S ", "'s ")
        s = _UPPER_WORDS.sub(lambda m: {"Inc": "Inc", "Dba": "dba"}.get(m.group(1), m.group(1).upper()), s)
    return s


def person(name) -> str:
    """'SMITH, JOHN A' or 'John A Smith' -> 'John A Smith'"""
    name = str(name or "").strip()
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    return title(name)


def phone(p) -> str:
    d = re.sub(r"\D", "", str(p or ""))
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:10]}" if len(d) == 10 and d[0] in "23456789" else ""


def zip5(z) -> str:
    return str(z or "").strip()[:5]
