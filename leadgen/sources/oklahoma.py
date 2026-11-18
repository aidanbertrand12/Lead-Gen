"""Oklahoma Corporation Commission operator list (open operators, with contact + phone).
https://oklahoma.gov/occ/divisions/oil-gas/oil-gas-data.html"""
from __future__ import annotations

from pathlib import Path

import openpyxl

from ..models import Company
from .common import download, person, phone, title, zip5

URL = "https://oklahoma.gov/content/dam/ok/en/occ/documents/og/ogdatafiles/operator-list.xlsx"


def fetch(raw_dir: Path) -> list[Company]:
    path = download(URL, raw_dir / "ok_operator_list.xlsx")
    ws = openpyxl.load_workbook(path, read_only=True).active
    rows = ws.iter_rows(values_only=True)
    hdr = [str(h) for h in next(rows)]
    out = []
    for r in rows:
        d = dict(zip(hdr, r))
        if d.get("Operator_Status") != "OPEN" or not d.get("Company_Name"):
            continue
        street = d.get("Office_Street") or d.get("Alt_Street") or d.get("POBox") or ""
        out.append(Company(
            name=title(d["Company_Name"]), address=title(street),
            city=title(d.get("Office_City") or d.get("Alt_City")),
            state=str(d.get("Office_State") or d.get("Alt_State") or "").upper(),
            zip=zip5(d.get("Office_Zip") or d.get("Alt_Zip")), phone=phone(d.get("Operator_Phone")),
            source="ok_occ", source_id=str(d.get("Operator_No") or ""),
            officers=[f"{person(d['Contact_Name'])}, Contact"] if d.get("Contact_Name") else [],
            roles=["operator"],
        ))
    return out
