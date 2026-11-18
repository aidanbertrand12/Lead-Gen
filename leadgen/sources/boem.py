"""BOEM (Bureau of Ocean Energy Management) list of active qualified Gulf companies.

Public data: https://www.data.boem.gov/Main/Company.aspx
File: compactdelimit.zip -> compactdelimit.txt (quoted, comma-delimited, no header).

Observed column layout (0-indexed):
  0 company number   1 qualification date   2 name   3 sort name
  4 termination date 5 ?  6 region (G = Gulf)  7-12 status/flags
  13 address line 1  14 address line 2  15 city  16 state  17 zip  18 country
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

import requests

from ..models import Company

URL = "https://www.data.boem.gov/Company/Files/compactdelimit.zip"
GULF_STATES = {"TX", "LA", "MS", "AL", "FL"}
ALL_STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
              "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
              "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
              "WV", "WI", "WY"}

# Entities that are almost never buyers of a website/AI package.
_PAPER_ENTITY = re.compile(
    r"\b(trust|drilling program|partnership|partners? (i|ii|iii|iv|v)\b|program|"
    r"holdings?|royalt\w*|individual|funds?|estate|bank|capital|investments?|minerals?)\b",
    re.I,
)


# Majors / large public companies and their subsidiaries: they have in-house
# marketing departments and won't buy a $35k package. Extend as needed.
_MAJORS = re.compile(
    r"\b(exxon|mobil|chevron|shell|bp\b|b\.p\.|conoco|phillips 66|marathon|occidental|anadarko|"
    r"atlantic richfield|arco\b|texaco|gulf oil|hess\b|apache|apa corp|eni\b|equinor|statoil|total|"
    r"repsol|petrobras|woodside|bhp|murphy|devon|eog\b|pioneer natural|kerr-mcgee|unocal|xto|enserch|enron|georgia power|southern company|duke energy|entergy|coterra|diamondback|ovintiv|permian resources|civitas|chord energy|matador|sm energy|range resources|antero|eqt\\b|chesapeake|expand energy|southwestern energy|cnx\\b|continental resources|hilcorp|kinder morgan|energy transfer|enterprise products|williams (companies|partners|field services|midstream|production)|oneok|targa|plains (all american|marketing|pipeline)|western midstream|magellan|halliburton|schlumberger|slb\\b|baker hughes|nabors|helmerich|patterson-uti|liberty (energy|oilfield)|transocean|valaris|weatherford|cheniere|sempra|enbridge|tc energy|transcanada|phillips 66|valero|citgo|motiva|flint hills|koch (industries|pipeline|minerals)|berry corp|california resources|aera energy|"
    r"sinopec|cnooc|petronas|mitsui|ecopetrol)\b",
    re.I,
)


def download(raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        out = raw_dir / "boem_companies.txt"
        out.write_bytes(zf.read(name))
    return out


def parse(path: Path, states: set[str] | None = None, skip_paper_entities: bool = True) -> list[Company]:
    states = states or GULF_STATES
    seen: set[str] = set()
    out: list[Company] = []
    with open(path, newline="", encoding="latin-1") as f:
        for row in csv.reader(f):
            if len(row) < 18:
                continue
            number, name, terminated, region = row[0], row[2].strip(), row[4].strip(), row[6]
            state = row[16].strip().upper()
            if terminated or state not in states:
                continue
            if number in seen:  # same company, multiple addresses
                continue
            if skip_paper_entities and (_PAPER_ENTITY.search(name) or _MAJORS.search(name)):
                continue
            seen.add(number)
            out.append(Company(
                name=name,
                address=" ".join(p for p in (row[13].strip(), row[14].strip()) if p),
                city=row[15].strip().title(),
                state=state,
                zip=row[17].strip(),
                source="boem",
                source_id=number,
            ))
    return out


def fetch(raw_dir: Path, states: set[str] | None = None, skip_paper_entities: bool = True) -> list[Company]:
    return parse(download(raw_dir), states, skip_paper_entities)
