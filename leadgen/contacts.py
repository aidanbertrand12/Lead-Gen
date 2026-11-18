"""Pull public business contact info (emails, phones, LinkedIn, leadership names) from a
company's own website: homepage + up to 4 contact/about/team pages."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .http import HEADERS
from .models import Company

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\b([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-](\d{4})\b")
_JUNK_EMAIL = re.compile(r"\.(png|jpe?g|gif|svg|webp|css|js)$|example\.|sentry|wixpress|"
                         r"domain\.com|yourdomain|email\.com|godaddy|wordpress|@\d", re.I)
_PAGE_HINT = re.compile(r"contact|about|team|leadership|management|staff|people|officers", re.I)
TITLES = r"(?:President|CEO|Chief Executive Officer|Owner|Founder|Managing Partner|Managing Director|" \
         r"Vice President|VP|General Manager|Chairman|Principal|COO|Chief Operating Officer)"
_NAME = r"[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-z]+)?(?: [A-Z][a-zA-Z'-]+)"
_NAME_TITLE = re.compile(rf"^({_NAME})[ ]*[,\-–|][ ]*({TITLES}[A-Za-z ,&]{{0,50}})$")
_NAME_LINE = re.compile(rf"^({_NAME})$")
_TITLE_LINE = re.compile(rf"^({TITLES}\b[A-Za-z ,&]{{0,50}})$")
_NOT_NAME = re.compile(rf"^{TITLES}\b|\b(Company|Energy|Oil|Gas|Services|Inc|LLC|Contact|About|Home|Our|The)\b")


def _people(text: str) -> list[str]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    out = []
    for i, line in enumerate(lines):
        m = _NAME_TITLE.match(line)
        if m and not _NOT_NAME.search(m.group(1)):
            out.append(f"{m.group(1)}, {m.group(2).strip(' ,')}")
        elif i + 1 < len(lines) and _NAME_LINE.match(line) and not _NOT_NAME.search(line):
            t = _TITLE_LINE.match(lines[i + 1])
            if t:
                out.append(f"{line}, {t.group(1).strip(' ,')}")
    seen, uniq = set(), []
    for p in out:
        if p.split(",")[0] not in seen:
            seen.add(p.split(",")[0])
            uniq.append(p)
    return uniq[:5]


# Generic inboxes rank below named people; personal-looking addresses come first.
_ROLE_PREF = ["info", "contact", "sales", "office", "admin", "inquiries", "bd", "business"]
_BAD_ROLE = re.compile(r"^(noreply|no-reply|donotreply|webmaster|privacy|careers|jobs|hr|abuse|"
                       r"postmaster|support|billing|accounting|accountspayable|payables?|ap|jib|revenue|invoices?|land|regulatory)@", re.I)


def _fetch(url: str, timeout: float = 12) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.text if r.status_code < 400 and "html" in r.headers.get("Content-Type", "html") else ""
    except requests.RequestException:
        return ""


def _rank_email(e: str, site_domain: str) -> tuple:
    local, _, dom = e.lower().partition("@")
    same = site_domain and (dom == site_domain or dom.endswith("." + site_domain))
    generic = local in _ROLE_PREF
    return (0 if same else 1, 1 if generic else 0, _ROLE_PREF.index(local) if generic else 0, e)


def _same_site(host: str, site_hosts: set[str]) -> bool:
    host = (host or "").lower().removeprefix("www.")
    return host in site_hosts


def scrape(company: Company) -> dict:
    base = company.audit.get("final_url") or company.website
    home = _fetch(base)
    if not home:
        return {}
    site_hosts = {(urlparse(base).hostname or "").lower().removeprefix("www.")}
    docs = [(base, home)]
    # Old frame-based sites keep their real content in the framed page (sometimes on another domain).
    for fr in BeautifulSoup(home, "lxml").find_all(["frame", "iframe"], src=True)[:3]:
        u = urljoin(base, fr["src"])
        if "youtube" in u or "google" in u or "facebook" in u:
            continue
        inner = _fetch(u)
        if inner:
            docs.append((u, inner))
            site_hosts.add((urlparse(u).hostname or "").lower().removeprefix("www."))
    # Contact / about / team pages linked from those pages
    links = []
    for url, html in list(docs):
        for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
            href, text = a["href"], a.get_text(" ", strip=True)
            if _PAGE_HINT.search(href) or _PAGE_HINT.search(text):
                u = urljoin(url, href).split("#")[0]
                if _same_site(urlparse(u).hostname, site_hosts) and u not in links and u not in [d[0] for d in docs]:
                    links.append(u)
    for u in links[:4]:
        html = _fetch(u)
        if html:
            docs.append((u, html))

    site_domain = next(iter(site_hosts))
    emails, phones, people, linkedin = set(), [], [], ""
    for url, html in docs:
        s = BeautifulSoup(html, "lxml")
        for a in s.find_all("a", href=True):
            h = a["href"]
            if h.lower().startswith("mailto:"):
                emails.add(h[7:].split("?")[0].strip())
            if "linkedin.com/company" in h and not linkedin:
                linkedin = h.split("?")[0]
        text = s.get_text("\n", strip=True)
        emails.update(EMAIL.findall(text))
        for m in PHONE.finditer(text):
            p = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
            if p not in phones:
                phones.append(p)
        for p in _people(text):
            if p.split(",")[0] not in [x.split(",")[0] for x in people] and len(people) < 5:
                people.append(p)

    emails = {e.strip(".,;:").lower() for e in emails}
    emails = [e for e in emails if not _JUNK_EMAIL.search(e) and not _BAD_ROLE.match(e) and len(e) < 60]
    emails.sort(key=lambda e: _rank_email(e, site_domain))
    return {"emails": emails[:5], "phones": phones[:3], "people": people, "linkedin": linkedin,
            "pages_checked": len(docs)}


def scrape_all(companies: list[Company], workers: int = 24, log=print) -> list[Company]:
    todo = [c for c in companies if c.website]
    log(f"Collecting contact info from {len(todo)} websites...")

    def work(c: Company):
        try:
            c.audit["contacts"] = scrape(c)
        except Exception as e:
            c.audit["contacts"] = {"error": str(e)[:120]}
        if not c.phone and c.audit["contacts"].get("phones"):
            c.phone = c.audit["contacts"]["phones"][0]
        return c

    with ThreadPoolExecutor(workers) as pool:
        for i, _ in enumerate(pool.map(work, todo), 1):
            if i % 50 == 0:
                log(f"  {i}/{len(todo)} done")
    found = sum(1 for c in todo if c.audit.get("contacts", {}).get("emails"))
    log(f"Emails found for {found} of {len(todo)} companies.")
    return companies
