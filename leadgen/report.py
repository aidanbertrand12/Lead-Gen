"""CSV (for a CRM import) and a sortable HTML report (for the sales team)."""
from __future__ import annotations

import csv
import html
from pathlib import Path

from .models import Company

CSV_FIELDS = ["score", "site_confidence", "name", "city", "state", "phone", "email", "other_emails", "people", "linkedin", "website", "website_source",
              "copyright_year", "https", "mobile_friendly", "chat_widget", "has_form",
              "analytics", "wordpress_version", "jquery_version", "load_seconds",
              "reasons", "pitch", "related_entities", "address", "zip", "source", "source_id"]


def write_csv(companies: list[Company], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for c in companies:
            a = c.audit
            w.writerow({
                "score": c.score, "site_confidence": a.get("site_confidence", ""), "name": c.name, "city": c.city, "state": c.state,
                "phone": c.phone,
                "email": (a.get("contacts", {}).get("emails") or [""])[0],
                "other_emails": "; ".join((a.get("contacts", {}).get("emails") or [])[1:]),
                "people": "; ".join(a.get("contacts", {}).get("people", [])),
                "linkedin": a.get("contacts", {}).get("linkedin", "") or ("yes" if a.get("has_linkedin") else ""),
                "website": c.website, "website_source": c.website_source,
                "copyright_year": a.get("copyright_year") or "", "https": a.get("https", ""),
                "mobile_friendly": a.get("has_viewport", ""), "chat_widget": a.get("chat_widget", ""),
                "has_form": a.get("has_form", ""), "analytics": ";".join(a.get("analytics", [])),
                "wordpress_version": a.get("wordpress_version", ""),
                "jquery_version": a.get("jquery_version", ""), "load_seconds": a.get("load_seconds", ""),
                "reasons": "; ".join(c.reasons), "pitch": "; ".join(c.pitch),
                "related_entities": "; ".join(a.get("related_entities", [])),
                "address": c.address, "zip": c.zip, "source": c.source, "source_id": c.source_id,
            })


def _subs(c: Company) -> str:
    rel = c.audit.get("related_entities") or []
    return f'<br><small title="{html.escape("; ".join(rel))}">+{len(rel)} related entities</small>' if rel else ""


def write_html(companies: list[Company], path: Path) -> None:
    rows = []
    for c in companies:
        site = (f'<a href="{html.escape(c.website)}" target="_blank" rel="noopener">'
                f'{html.escape(c.website.split("//")[-1].rstrip("/"))}</a>') if c.website else "<em>none found</em>"
        rows.append(
            f"<tr><td class=s>{c.score}</td><td>{c.audit.get('site_confidence','')}</td><td>{html.escape(c.name)}{_subs(c)}</td>"
            f"<td>{html.escape(c.city)}, {c.state}</td><td>{site}</td>"
            f"<td>{html.escape('; '.join(c.reasons))}</td><td>{html.escape(', '.join(c.pitch))}</td></tr>"
        )
    with_site = sum(1 for c in companies if c.website)
    hot = sum(1 for c in companies if c.score >= 50)
    path.write_text(f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Gulf Lead Audit</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e5e5e5;--hot:#c2410c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141414;--fg:#eee;--mut:#999;--line:#333;--hot:#fb923c}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif;margin:0;padding:16px}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{cursor:pointer;position:sticky;top:0;background:var(--bg)}}td.s{{font-weight:700;color:var(--hot)}}
p{{color:var(--mut)}}input{{padding:6px;width:min(400px,100%);margin-bottom:8px}}
.wrap{{overflow-x:auto}}
</style></head><body>
<h1>Gulf Coast lead audit</h1>
<p>{len(companies)} companies · {with_site} with websites · {hot} scored 50+ (hot leads). Click a header to sort.</p>
<input id=q placeholder="Filter…" oninput="f()">
<div class=wrap><table id=t><thead><tr><th>Score</th><th>Site match</th><th>Company</th><th>Location</th><th>Website</th><th>Findings</th><th>Pitch</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<script>
function f(){{const q=document.getElementById('q').value.toLowerCase();for(const r of document.querySelectorAll('#t tbody tr'))r.style.display=r.textContent.toLowerCase().includes(q)?'':'none'}}
document.querySelectorAll('th').forEach((th,i)=>th.onclick=()=>{{const b=th.closest('table').tBodies[0],rs=[...b.rows],d=th.dataset.d=th.dataset.d==='a'?'d':'a';
rs.sort((x,y)=>{{const A=x.cells[i].textContent,B=y.cells[i].textContent,n=!isNaN(A)&&!isNaN(B);const c=n?A-B:A.localeCompare(B);return d==='a'?c:-c}});rs.forEach(r=>b.appendChild(r))}});
</script></body></html>""", encoding="utf-8")
