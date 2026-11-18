"""Texas Railroad Commission P-5 Organization file (orf850): every organization licensed
to operate in the Texas oil & gas industry: operators, pipelines, gas plants, water
haulers, plugging contractors, cementers, directional surveyors...

Public data: https://www.rrc.texas.gov/resource-center/research/data-sets-available-for-download/
Includes mailing address, phone, and named officers (President, CEO, Managing Member...).
"""
from __future__ import annotations

import gzip
import re
import time
from collections import defaultdict
from pathlib import Path

import requests

from ..models import Company

LINK = "https://mft.rrc.texas.gov/link/04652169-eed6-4396-9019-2e270e790f6c"
POST = "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml"

# Status (col 41): A=active, D=delinquent (late renewal, often still operating), I=inactive
KEEP_STATUS = {"A", "D"}
ROLE_CODES = {
    "OPRS/O": "oil operator", "OPRS/G": "gas operator", "PIPE-L": "pipeline operator",
    "PIPE-A": "pipeline affiliate", "GASPLT": "gas processing plant", "REFINE": "refinery",
    "WHAUL ": "water hauler", "SWDP18": "saltwater disposal", "COMFAC": "commercial disposal",
    "PLUGGR": "plugging contractor", "CEMNTR": "cementing contractor", "DIRSUR": "directional surveying",
    "TRANSP": "transporter", "GTHS/G": "gas gatherer", "GTHS/O": "oil gatherer", "GTHS/C": "condensate gatherer",
    "RESPIT": "reserve pit cleaner", "CLENUP": "pollution cleanup contractor", "RECLPL": "reclaiming plant",
    "G/PUR ": "gas purchaser", "CSGD/G": "casinghead gas gatherer",
}
_OFFICER_TITLES = re.compile(r"PRES|CEO|CHIEF|OWNER|MANAG|MEMBER|PARTNER|VP|VICE|FOUNDER|PRINCIPAL|"
                             r"DIRECTOR|GENERAL|CHAIRMAN|SOLE|PROPRIETOR", re.I)


def download(raw_dir: Path, retries: int = 5) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / "orf850.txt"
    for attempt in range(retries):
        try:
            s = requests.Session()
            s.headers["User-Agent"] = "Mozilla/5.0"
            h = s.get(LINK, timeout=60).text
            vs = re.search(r'name="javax.faces.ViewState"[^>]*value="([^"]+)"', h).group(1)
            key = re.search(r"\{'(fileTable:\d+:j_id_\w+)':'[^']+'\}\)\.submit\('fileList'\);return false;\">"
                            r"orf850\.txt\.gz<", h).group(1)
            r = s.post(POST, data={"fileList_SUBMIT": "1", "javax.faces.ViewState": vs, key: key},
                       timeout=600)
            r.raise_for_status()
            out.write_bytes(gzip.decompress(r.content))
            return out
        except Exception as e:  # flaky host: retry with backoff
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return out


_UPPER_WORDS = re.compile(r"\b(Llc|Lp|Llp|Ltd|Inc|Usa|Us|Ii|Iii|Iv|Swd|Ngl|Lng|E&P|Dba|Pc|Pllc)\b")


def _title(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    if s.isupper():
        s = s.title().replace("'S ", "'s ")
        s = _UPPER_WORDS.sub(lambda m: {"Inc": "Inc", "Dba": "dba"}.get(m.group(1), m.group(1).upper()), s)
    return s


def _person(name: str) -> str:
    """'VOZZELLA, JAMES K' -> 'James K Vozzella'"""
    name = name.strip()
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    return _title(name)


def _phone(p: str) -> str:
    p = re.sub(r"\D", "", p)
    return f"({p[:3]}) {p[3:6]}-{p[6:10]}" if len(p) == 10 and p[0] in "23456789" else ""


def parse(path: Path) -> list[Company]:
    orgs: dict[str, dict] = {}
    officers: dict[str, list] = defaultdict(list)
    roles: dict[str, set] = defaultdict(set)
    with open(path, "rb") as f:
        for raw in f:
            line = raw.decode("latin-1").rstrip("\r\n")
            rt, num = line[:2], line[2:8]
            if rt == "A ":
                if line[41:42] not in KEEP_STATUS:
                    continue
                orgs[num] = {
                    "name": line[8:40].strip(), "status": line[41:42],
                    "address": line[70:132].strip(), "city": line[132:145].strip(),
                    "state": line[145:147].strip(), "zip": line[147:152].strip(),
                    "phone": _phone(line[258:268]),
                }
            elif rt == "K ":
                title = line[72:104].strip()
                if _OFFICER_TITLES.search(title) and "AGENT" not in title.upper():
                    officers[num].append(f"{_person(line[40:72])}, {_title(title)}")
            elif rt in ("F ", "U ", "R "):
                code = line[40:46]
                if code in ROLE_CODES:
                    roles[num].add(ROLE_CODES[code])
    out = []
    for num, o in orgs.items():
        if not o["name"]:
            continue
        out.append(Company(
            name=_title(o["name"]), address=_title(o["address"]), city=_title(o["city"]),
            state=o["state"], zip=o["zip"], phone=o["phone"], source="tx_rrc", source_id=num,
            officers=officers.get(num, [])[:5], roles=sorted(roles.get(num, [])),
        ))
    return out


def fetch(raw_dir: Path) -> list[Company]:
    cached = raw_dir / "orf850.txt"
    path = cached if cached.exists() and time.time() - cached.stat().st_mtime < 20 * 86400 else download(raw_dir)
    return parse(path)
