"""Find a company's website when the source didn't give one.

Strategy (no paid API needed): generate likely domains from the company name,
check they resolve and serve a page, then confirm the page actually mentions
the company (to avoid matching an unrelated or parked domain).
"""
from __future__ import annotations

import re
import socket
from concurrent.futures import ThreadPoolExecutor

import requests

from .http import HEADERS
from .models import Company

_SUFFIXES = re.compile(
    r"\b(l\.?l\.?c|inc|incorporated|corp|corporation|co|company|ltd|l\.?p|lp|llp|plc|"
    r"usa|u\.s\.a|us|america|the|of)\b\.?",
    re.I,
)
_GENERIC = {"oil", "gas", "energy", "offshore", "exploration", "production", "operating",
            "resources", "petroleum", "services", "and", "e&p"}


def _clean_tokens(name: str) -> list[str]:
    name = name.lower().replace("&", " and ")
    name = _SUFFIXES.sub(" ", name)
    return [t for t in re.split(r"[^a-z0-9]+", name) if t]


def candidate_domains(name: str) -> list[str]:
    toks = _clean_tokens(name)
    if not toks:
        return []
    no_and = [t for t in toks if t != "and"]
    distinctive = [t for t in no_and if t not in _GENERIC]
    stems = ["".join(no_and), "-".join(no_and)]
    if distinctive and distinctive != no_and:
        stems += ["".join(distinctive), "".join(distinctive) + no_and[-1]]
    if len(no_and) >= 2:
        stems.append("".join(no_and[:2]))
    if distinctive:
        stems += [distinctive[0] + s for s in ("energy", "oil", "offshore", "inc", "llc")]
    seen, out = set(), []
    for s in stems:
        for tld in (".com", ".net", ".us"):
            d = s + tld
            if len(s) >= 3 and d not in seen:
                seen.add(d)
                out.append(d)
    return out


def _resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, 443)
        return True
    except OSError:
        return False


_PARKED = re.compile(r"(domain (is )?for sale|buy this domain|parked free|domain parking|"
                     r"this domain may be for sale|sedoparking|hugedomains|dan\.com|afternic)", re.I)


_INDUSTRY = re.compile(r"\b(oil|gas|energy|offshore|drilling|petroleum|pipeline|wells?|exploration|"
                       r"midstream|upstream|reservoir|lease|marine|vessels?|fabrication|oilfield|"
                       r"production|hydrocarbon|lng|refin\w*)\b")


def _matches_company(html: str, name: str, domain: str) -> bool:
    """Company's distinctive name words must appear on the page itself (not just in the URL)."""
    text = html.lower()
    if _PARKED.search(text):
        return False
    text = text.replace(domain.lower(), " ").replace(domain.split(".")[0].lower(), " ")
    toks = [t for t in _clean_tokens(name) if t != "and" and len(t) > 2]
    distinctive = [t for t in toks if t not in _GENERIC] or toks
    if not distinctive or not _INDUSTRY.search(text):
        return False
    hits = sum(1 for t in distinctive if re.search(rf"\b{re.escape(t)}\b", text))
    need = len(distinctive) if len(distinctive) <= 2 else -(-2 * len(distinctive) // 3)
    return hits >= need


def guess_website(company: Company, timeout: float = 8) -> str:
    for domain in candidate_domains(company.name):
        if not _resolves(domain):
            continue
        for scheme in ("https://", "http://"):
            try:
                r = requests.get(scheme + domain, headers=HEADERS, timeout=timeout, allow_redirects=True)
            except requests.RequestException:
                continue
            if r.status_code < 400 and _matches_company(r.text[:300_000], company.name, domain):
                return r.url
            break
    return ""


def discover(companies: list[Company], workers: int = 16, log=print) -> list[Company]:
    todo = [c for c in companies if not c.website]
    log(f"Discovering websites for {len(todo)} companies (of {len(companies)})...")

    def work(c: Company):
        url = guess_website(c)
        if url:
            c.website, c.website_source = url, "guess"
        return c

    found = 0
    with ThreadPoolExecutor(workers) as pool:
        for i, c in enumerate(pool.map(work, todo), 1):
            found += bool(c.website)
            if i % 50 == 0:
                log(f"  {i}/{len(todo)} checked, {found} sites found")
    log(f"Found {found} websites.")
    return companies
