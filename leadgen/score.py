"""Turn an audit into an opportunity score (0-100) plus a list of talking points.

Higher score = more outdated / more to sell. Each finding maps to a line item
in PRICING.md so the sales pitch writes itself.
"""
from __future__ import annotations

from .audit import THIS_YEAR
from .models import Company

# (points, reason, pitch item)
RULES = [
    (lambda a: not a.get("reachable"), 35, "Website is down or erroring", "Website rebuild"),
    (lambda a: a.get("parked"), 35, "Domain is parked / for sale", "Website rebuild"),
    (lambda a: a.get("ssl_error"), 15, "Broken SSL certificate (browser shows 'Not Secure')", "Website rebuild"),
    (lambda a: a.get("reachable") and not a.get("https"), 12, "No HTTPS", "Website rebuild"),
    (lambda a: (a.get("cert_days_left") is not None and a["cert_days_left"] < 14), 6, "SSL certificate about to expire", "Website rebuild"),
    (lambda a: a.get("reachable") and not a.get("has_viewport"), 14, "Not mobile-friendly (no viewport)", "Website rebuild"),
    (lambda a: a.get("uses_flash"), 12, "Uses Flash (dead since 2020)", "Website rebuild"),
    (lambda a: a.get("uses_frames"), 10, "Uses HTML frames", "Website rebuild"),
    (lambda a: a.get("uses_table_layout"), 6, "1990s-style table layout", "Website rebuild"),
    (lambda a: a.get("legacy_doctype"), 5, "Legacy HTML4/XHTML markup", "Website rebuild"),
    (lambda a: bool(a.get("deprecated_tags")), 4, "Deprecated HTML tags (font/center/marquee)", "Website rebuild"),
    (lambda a: a.get("ie_conditional_comments"), 3, "Internet Explorer hacks in code", "Website rebuild"),
    (lambda a: a.get("old_jquery"), 5, "Outdated jQuery (security risk)", "Website rebuild"),
    (lambda a: a.get("old_php"), 6, "End-of-life PHP version exposed", "Website rebuild"),
    (lambda a: a.get("copyright_year") and a["copyright_year"] <= THIS_YEAR - 3, 8, "Copyright footer is 3+ years old", "Website rebuild"),
    (lambda a: a.get("load_seconds", 0) > 4, 6, "Slow homepage (>4s)", "Website rebuild"),
    (lambda a: a.get("page_kb", 0) > 4000, 3, "Very heavy homepage (>4MB)", "Website rebuild"),
    (lambda a: a.get("reachable") and not a.get("has_meta_description"), 4, "Missing meta description (SEO)", "Website rebuild"),
    (lambda a: a.get("reachable") and not a.get("has_schema"), 2, "No structured data (SEO)", "Website rebuild"),
    (lambda a: a.get("builder") in {"godaddy_builder", "weebly"}, 4, "Cheap DIY site builder", "Website rebuild"),
    (lambda a: a.get("reachable") and not a.get("chat_widget"), 8, "No chat / AI assistant to capture visitors", "AI assistant + RFQ intake"),
    (lambda a: a.get("reachable") and not a.get("has_form"), 8, "No contact/lead form on homepage", "AI assistant + RFQ intake"),
    (lambda a: a.get("mailto_only"), 3, "Leads go to a bare email link", "CRM + automation"),
    (lambda a: a.get("reachable") and not a.get("has_quote_cta"), 4, "No 'Request a Quote / Bid' call-to-action", "AI assistant + RFQ intake"),
    (lambda a: a.get("reachable") and not a.get("analytics"), 6, "No analytics — can't measure leads", "CRM + automation"),
    (lambda a: a.get("analytics") == ["universal_analytics_only"], 5, "Only dead Universal Analytics (stopped in 2023)", "CRM + automation"),
    (lambda a: a.get("reachable") and "hubspot" not in a.get("analytics", []), 2, "No marketing automation / CRM detected", "CRM + automation"),
]


def score(c: Company) -> Company:
    a = c.audit
    if not c.website:
        c.score = 40
        c.reasons = ["No website found (verify the company is still operating)"]
        c.pitch = ["Website rebuild", "AI assistant + RFQ intake", "AI lead-gen engine", "CRM + automation"]
        return c
    pts, reasons, pitch = 0, [], []
    for test, p, reason, item in RULES:
        try:
            hit = test(a)
        except Exception:
            hit = False
        if hit:
            pts += p
            reasons.append(reason)
            if item not in pitch:
                pitch.append(item)
    # Every company gets pitched the outbound engine — it's the revenue story.
    pitch.append("AI lead-gen engine")
    c.score = min(100, pts)
    c.reasons, c.pitch = reasons, pitch
    return c


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url if "//" in url else "//" + url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def group_by_site(companies: list[Company]) -> list[Company]:
    """Subsidiaries sharing one website become one lead (one sale)."""
    groups: dict[str, Company] = {}
    out = []
    for c in companies:
        d = _domain(c.website) if c.website else ""
        if not d:
            out.append(c)
            continue
        if d in groups:
            g = groups[d]
            g.audit.setdefault("related_entities", []).append(c.name)
            if len(c.name) < len(g.name):  # parent usually has the shortest name
                g.audit["related_entities"].append(g.name)
                g.audit["related_entities"].remove(c.name)
                g.name = c.name
        else:
            groups[d] = c
            out.append(c)
    return out


def score_all(companies: list[Company]) -> list[Company]:
    return sorted((score(c) for c in group_by_site(companies)), key=lambda c: c.score, reverse=True)
