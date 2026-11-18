"""Homepage audit: detects outdated tech, missing basics, and missing lead-capture/AI.

One GET per site (plus a TLS handshake to read the certificate), so it's light on
the target servers.
"""
from __future__ import annotations

import datetime as dt
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .http import HEADERS
from .models import Company

THIS_YEAR = dt.date.today().year

CHAT_SIGNATURES = {
    "intercom": "widget.intercom.io", "drift": "js.driftt.com", "tawk.to": "embed.tawk.to",
    "livechat": "cdn.livechatinc.com", "hubspot_chat": "js.usemessages.com",
    "zendesk": "static.zdassets.com", "crisp": "client.crisp.chat", "tidio": "code.tidio.co",
    "olark": "static.olark.com", "gohighlevel": "leadconnectorhq.com", "podium": "podium.com",
    "birdeye": "birdeye.com", "smith.ai": "smith.ai",
}
ANALYTICS_SIGNATURES = {
    "ga4": re.compile(r"gtag\(['\"]config['\"],\s*['\"]G-|googletagmanager\.com/gtag/js\?id=G-"),
    "universal_analytics_only": re.compile(r"\bUA-\d{4,}-\d+"),
    "gtm": re.compile(r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+"),
    "meta_pixel": re.compile(r"connect\.facebook\.net/.+/fbevents\.js"),
    "linkedin_insight": re.compile(r"snap\.licdn\.com|_linkedin_partner_id"),
    "hubspot": re.compile(r"js\.hs-scripts\.com|js\.hsforms\.net"),
}
BUILDERS = {
    "wix": "wix.com", "squarespace": "squarespace.com", "godaddy_builder": "img1.wsimg.com",
    "weebly": "weebly.com", "webflow": "webflow.com", "duda": "dudaone", "shopify": "cdn.shopify.com",
}


def _cert_days_left(host: str, timeout: float = 8) -> int | None:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                not_after = s.getpeercert()["notAfter"]
        exp = dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        return (exp - dt.datetime.utcnow()).days
    except Exception:
        return None


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def audit_url(url: str, timeout: float = 15) -> dict:
    if not url.startswith("http"):
        url = "https://" + url
    a: dict = {"url": url, "reachable": False}
    t0 = time.monotonic()
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except requests.exceptions.SSLError:
        a["ssl_error"] = True
        try:
            r = requests.get(url.replace("https://", "http://", 1), headers=HEADERS,
                             timeout=timeout, allow_redirects=True)
        except requests.RequestException as e:
            a["error"] = str(e)[:200]
            return a
    except requests.RequestException as e:
        a["error"] = str(e)[:200]
        return a

    a["load_seconds"] = round(time.monotonic() - t0, 2)
    a["status"] = r.status_code
    a["final_url"] = r.url
    a["reachable"] = r.status_code < 400
    a["https"] = r.url.startswith("https://")
    a["page_kb"] = round(len(r.content) / 1024, 1)
    a["server"] = r.headers.get("Server", "")
    a["powered_by"] = r.headers.get("X-Powered-By", "")
    a["last_modified"] = r.headers.get("Last-Modified", "")
    if not a["reachable"]:
        return a

    html = r.text
    low = html.lower()
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(r.url).hostname or ""

    if a["https"]:
        a["cert_days_left"] = _cert_days_left(host)

    # Parked / for-sale domains
    a["parked"] = bool(re.search(r"(domain (is )?for sale|buy this domain|parked free|"
                                 r"this domain may be for sale|sedoparking|hugedomains)", low))

    # Basics
    title = soup.title.get_text(strip=True) if soup.title else ""
    desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    a["title"] = title[:150]
    a["has_meta_description"] = bool(desc and desc.get("content", "").strip())
    a["has_viewport"] = bool(soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}))
    a["has_h1"] = bool(soup.find("h1"))
    a["has_open_graph"] = bool(soup.find("meta", attrs={"property": re.compile("^og:", re.I)}))
    a["has_schema"] = "application/ld+json" in low or "schema.org" in low
    a["has_favicon"] = bool(soup.find("link", rel=lambda v: v and "icon" in " ".join(v).lower()))

    # Legacy tech
    doctype = html.lstrip()[:200].lower()
    a["legacy_doctype"] = doctype.startswith("<!doctype html public") or "xhtml" in doctype[:120]
    a["uses_flash"] = ".swf" in low or "application/x-shockwave-flash" in low
    a["uses_frames"] = bool(soup.find(["frameset", "frame"]))
    a["uses_table_layout"] = len(soup.find_all("table")) >= 4 and not soup.find(["nav", "header", "section"])
    a["deprecated_tags"] = sorted({t.name for t in soup.find_all(["font", "center", "marquee", "blink"])})
    a["ie_conditional_comments"] = "<!--[if ie" in low or "<!--[if lt ie" in low

    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})", low)]
    a["copyright_year"] = max(years) if years else None

    gen = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    a["generator"] = gen.get("content", "")[:80] if gen else ""
    wp = re.search(r"wordpress\s*([\d.]+)", a["generator"], re.I) or re.search(r"ver=([\d.]+)['\"&].{0,40}wp-", low)
    a["wordpress"] = "wp-content" in low or "wordpress" in a["generator"].lower()
    a["wordpress_version"] = wp.group(1) if wp and a["wordpress"] else ""

    jq = re.search(r"jquery[.-]?(\d+\.\d+(?:\.\d+)?)(?:\.min)?\.js", low) or \
        re.search(r"jquery(?:\.min)?\.js\?ver=(\d+\.\d+(?:\.\d+)?)", low)
    a["jquery_version"] = jq.group(1) if jq else ""
    a["old_jquery"] = bool(jq and _version_tuple(jq.group(1)) < (3, 0))
    php = re.search(r"php/([\d.]+)", a["powered_by"].lower())
    a["old_php"] = bool(php and _version_tuple(php.group(1)) < (8, 0))
    a["builder"] = next((k for k, sig in BUILDERS.items() if sig in low), "")

    # Lead capture / marketing / AI
    a["chat_widget"] = next((k for k, sig in CHAT_SIGNATURES.items() if sig in low), "")
    a["analytics"] = sorted(k for k, rx in ANALYTICS_SIGNATURES.items() if rx.search(html))
    if "ga4" in a["analytics"] or "gtm" in a["analytics"]:
        a["analytics"] = [x for x in a["analytics"] if x != "universal_analytics_only"]
    forms = soup.find_all("form")
    a["has_form"] = any(f.find(["input", "textarea"], attrs={"type": lambda t: t != "search"}) for f in forms)
    links = " ".join((l.get("href") or "") + " " + l.get_text(" ", strip=True) for l in soup.find_all("a")).lower()
    a["has_contact_page"] = "contact" in links
    a["has_quote_cta"] = bool(re.search(r"(request|get)\s+(a\s+)?(quote|bid|estimate)|rfq", low))
    a["has_careers"] = bool(re.search(r"career|jobs|employment", links))
    a["has_phone"] = bool(re.search(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b", soup.get_text(" ")))
    a["has_linkedin"] = "linkedin.com/company" in low
    a["mailto_only"] = "mailto:" in low and not a["has_form"]
    return a


def audit_all(companies: list[Company], workers: int = 16, log=print) -> list[Company]:
    todo = [c for c in companies if c.website]
    log(f"Auditing {len(todo)} websites...")

    def work(c: Company):
        c.audit = audit_url(c.website)
        return c

    with ThreadPoolExecutor(workers) as pool:
        for i, _ in enumerate(pool.map(work, todo), 1):
            if i % 25 == 0:
                log(f"  {i}/{len(todo)} audited")
    return companies
