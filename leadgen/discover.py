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
from bs4 import BeautifulSoup

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


def candidate_domains(name: str, limit: int = 10) -> list[str]:
    toks = _clean_tokens(name)
    no_and = [t for t in toks if t != "and"]
    if not no_and:
        return []
    distinctive = [t for t in no_and if t not in _GENERIC and len(t) > 1]
    stems = ["".join(no_and)]
    if len(no_and) > 1:
        stems.append("-".join(no_and))
    if distinctive and distinctive != no_and:
        base = "".join(distinctive)
        stems.append(base)
        if len(base) >= 4:
            stems += [base + s for s in ("energy", "oil", "oilfield", "services")]
    if len(no_and) >= 3:
        stems.append("".join(no_and[:2]))
    seen, out = set(), []
    for tld in (".com", ".net", ".us"):
        for st in stems:
            d = st + tld
            if 4 <= len(st) <= 63 and d not in seen:
                seen.add(d)
                out.append(d)
    return out[:limit]


def _resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, 443)
        return True
    except (OSError, UnicodeError):
        return False


_PARKED = re.compile(r"(domain (is )?for sale|buy this domain|parked free|domain parking|"
                     r"this domain may be for sale|sedoparking|hugedomains|dan\.com|afternic)", re.I)


_INDUSTRY = re.compile(r"\b(oil|gas|energy|offshore|drilling|petroleum|pipeline|wells?|exploration|"
                       r"midstream|upstream|reservoir|lease|marine|vessels?|fabrication|oilfield|"
                       r"production|hydrocarbon|lng|refin\w*|hauling|trucking|disposal|saltwater|vacuum|roustabout|"
                       r"welding|fabricat\w*|pipe|frac\w*|wireline|cementing|plugging|directional)\b")


_OFF_INDUSTRY = re.compile(r"\b(news|magazines?|real estate|realty|office space|apartments?|for rent|"
                           r"watercolou?rs?|art(ist|work)?|gallery|traders|restaurant|hotel|church|"
                           r"law (firm|office)|attorneys?|salon|boutique|wedding|photography|"
                           r"india|nigeria|russia|pakistan|indonesia|uae|dubai|canada|australia|uk)\b", re.I)


_FOREIGN = re.compile(r"\b(russia\w*|siberia\w*|india|nigeria\w*|china|indonesia\w*|kazakh\w*|"
                      r"north sea|norway|brazil\w*|canad\w*|alberta|australia\w*|united kingdom|"
                      r"middle east|saudi|emirates|egypt\w*|malaysia\w*|venezuela\w*)\b")
_US = re.compile(r"\b(texas|louisiana|mississippi|alabama|florida|gulf of mexico|gulf of america|houston|"
                 r"united states|usa|u\.s\.)|\b(tx|la|ms|al|fl)\s+\d{5}\b")
_NON_LATIN = re.compile(r"[\u0400-\u04ff\u0600-\u06ff\u0900-\u097f\u4e00-\u9fff]")


def _matches_company(html: str, company: Company, domain: str) -> bool:
    """Accept a guessed site only if it is plausibly *this* US oil & gas company."""
    low = html.lower()
    if _PARKED.search(low):
        return False
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "").lower()
    site_name = soup.find("meta", attrs={"property": "og:site_name"})
    header = " ".join(filter(None, [title, site_name.get("content", "").lower() if site_name else "",
                                    *(h.get_text(" ", strip=True).lower() for h in soup.find_all("h1")[:2])]))
    if _OFF_INDUSTRY.search(title):
        return False
    text = soup.get_text(" ", strip=True).lower()
    stem = domain.split(".")[0].lower()
    text_wo_domain = text.replace(domain.lower(), " ").replace(stem, " ")
    if not _INDUSTRY.search(text_wo_domain):
        return False
    # Foreign sites: declared non-English page language
    html_tag = soup.find("html")
    lang = (html_tag.get("lang") or "").lower() if html_tag else ""
    if lang and not lang.startswith("en"):
        return False
    if len(_NON_LATIN.findall(html)) > 20:
        return False
    if len(_FOREIGN.findall(text)) >= 3 and not _US.search(text):
        return False
    toks = [t for t in _clean_tokens(company.name) if t != "and" and len(t) > 2]
    distinctive = [t for t in toks if t not in _GENERIC] or toks
    if not distinctive:
        return False
    # Distinctive name words must appear in the title / site name / H1, not just somewhere on the page
    hits = sum(1 for t in distinctive if re.search(rf"\b{re.escape(t)}\b", header))
    need = len(distinctive) if len(distinctive) <= 2 else -(-2 * len(distinctive) // 3)
    return hits >= need


def guess_website(company: Company, timeout: float = 8) -> str:
    for domain in candidate_domains(company.name):
        # No DNS lookup: through the proxy a dead domain fails in ~0.1s, faster than resolving it.
        for scheme in ("https://", "http://"):
            try:
                r = requests.get(scheme + domain, headers=HEADERS, timeout=timeout, allow_redirects=True)
            except requests.exceptions.ProxyError:
                break  # host doesn't exist
            except requests.RequestException:
                continue
            if r.status_code < 400 and _matches_company(r.text[:300_000], company, domain):
                return r.url
            break
    return ""


def discover(companies: list[Company], workers: int = 16, log=print, cache=None) -> list[Company]:
    todo = []
    for c in companies:
        if c.website:
            continue
        if cache is not None and c.key in cache:
            url = cache.get(c.key)
            if url:
                c.website, c.website_source = url, "guess"
            continue
        todo.append(c)
    log(f"Discovering websites for {len(todo)} companies (of {len(companies)}; rest cached or known)...")

    def work(c: Company):
        try:
            url = guess_website(c)
        except Exception as e:  # one bad name must not kill a 2,000-company run
            log(f"  discover error for {c.name!r}: {e}")
            url = ""
        if url:
            c.website, c.website_source = url, "guess"
        if cache is not None:
            cache.put(c.key, url)
        return c

    found = 0
    with ThreadPoolExecutor(workers) as pool:
        for i, c in enumerate(pool.map(work, todo), 1):
            found += bool(c.website)
            if i % 50 == 0:
                log(f"  {i}/{len(todo)} checked, {found} sites found")
    log(f"Found {found} websites.")
    return companies
