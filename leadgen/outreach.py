"""Builds the outreach file for Grok (one row per company) and the Grok prompt.

The emails do NOT pitch price. They point out 1-2 real things we noticed on the
company's website, say Gulf Coast Systems has an offer, and ask for a short call.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .models import Company

COMPANY = "Gulf Coast Systems"

# Reason (from score.py) -> plain-English observation, in priority order.
OBSERVATIONS = [
    ("Website is down or erroring", "your website wasn't loading when we checked it"),
    ("Domain is parked", "your web address is currently showing a 'domain for sale' page"),
    ("Broken SSL", "the site's security certificate is broken, so browsers show visitors a warning"),
    ("Uses Flash", "parts of the site rely on Flash, which no modern browser can display"),
    ("Not mobile-friendly", "the site doesn't adjust to phones, which is where most people look up vendors now"),
    ("No HTTPS", "browsers label the site 'Not Secure' when people visit"),
    ("Uses HTML frames", "the site uses an older frame-based layout that Google has trouble reading"),
    ("Copyright footer is 3+ years old", "the footer still shows a copyright year of {year}"),
    ("Only dead Universal Analytics", "the site's Google Analytics stopped collecting data back in 2023"),
    ("No 'Request a Quote", "there isn't a clear way for a visitor to request a quote or a bid"),
    ("No contact/lead form", "there's no contact form on the homepage, so inquiries depend on someone picking up the phone"),
    ("No chat / AI assistant", "there's no way for a visitor to get answers or leave their details after hours"),
    ("Slow homepage", "the homepage takes more than four seconds to load"),
    ("Outdated jQuery", "the site runs on outdated code that has known security issues"),
    ("End-of-life PHP", "the server runs an outdated version of PHP that no longer gets security updates"),
    ("1990s-style table layout", "the site's design and code date back many years"),
    ("No analytics", "there's no visitor tracking set up, so there's no way to see who is checking you out"),
    ("Missing meta description", "the site isn't set up to show a proper description in Google results"),
]
_FREE_MAIL = {"gmail.com", "yahoo.com", "aol.com", "hotmail.com", "outlook.com", "att.net",
              "sbcglobal.net", "bellsouth.net", "cox.net", "comcast.net", "msn.com", "icloud.com"}
_EXEC = re.compile(r"president|ceo|chief executive|owner|founder|managing (partner|director|member)|"
                   r"sole proprietor|manager|member|partner|"
                   r"principal|general manager|coo|chief operating|business development|chairman", re.I)
_SKIP_TITLE = re.compile(r"human resources|\bhr\b|land\b|regulatory|geolog|geoscience|accounting|"
                         r"controller|reservoir|drilling|completions|it\b|safety|hse", re.I)


def observations(c: Company, limit: int = 2) -> list[str]:
    out = []
    for key, text in OBSERVATIONS:
        if any(key in r for r in c.reasons):
            out.append(text.format(year=c.audit.get("copyright_year") or "years ago"))
        if len(out) >= limit:
            break
    return out


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def pick_contact(c: Company) -> tuple[str, str, str, str]:
    """Returns (contact_name, contact_title, email, backup_email)."""
    ct = c.audit.get("contacts", {}) or {}
    site_hosts = {_host(c.website), _host(c.audit.get("final_url", ""))} - {""}
    emails = [e for e in ct.get("emails", [])
              if e.split("@")[-1] in site_hosts or e.split("@")[-1] in _FREE_MAIL
              or any(e.split("@")[-1].split(".")[0] in h for h in site_hosts)]
    people = []
    for p in list(ct.get("people", [])) + list(c.officers):
        name, _, title = p.partition(", ")
        if _EXEC.search(title) and not _SKIP_TITLE.search(title):
            people.append((name, title))
    name, title = people[0] if people else ("", "")
    # Prefer an email that belongs to the named person (first name, last name, or initial+last)
    chosen = ""
    if name and emails:
        parts = [p.lower() for p in re.findall(r"[A-Za-z]+", name) if len(p) > 1]
        first, last = parts[0], parts[-1]
        for e in emails:
            local = e.split("@")[0]
            if last in local or local in (first, first[0] + last, first + "." + last):
                chosen = e
                break
    if not chosen and emails:
        chosen = emails[0]
        # A personal mailbox that isn't the named contact: don't address it to the named person
        local = chosen.split("@")[0]
        generic = local in {"info", "contact", "sales", "office", "admin", "inquiries", "bd", "business", "mail"}
        if name and not generic:
            name, title = "", ""
    backup = next((e for e in emails if e != chosen), "")
    return name, title, chosen, backup


@dataclass
class OutreachRow:
    lead_id: str
    priority: str
    company: str
    contact_name: str
    contact_title: str
    email: str
    backup_email: str
    phone: str
    city: str
    state: str
    website: str
    site_verified: str
    observation_1: str
    observation_2: str
    all_findings: str
    status: str = ""
    date_sent: str = ""
    follow_up_due: str = ""
    notes: str = ""


def build_rows(companies: list[Company]) -> list[OutreachRow]:
    rows = []
    for c in companies:
        if not c.website:
            continue
        name, title, email, backup = pick_contact(c)
        obs = observations(c)
        conf = c.audit.get("site_confidence", "")
        prio = "A" if conf == "high" and c.score >= 40 else ("B" if conf == "high" else "C")
        rows.append(OutreachRow(
            lead_id="", priority=prio, company=_display_name(c.name), contact_name=name, contact_title=title,
            email=email, backup_email=backup, phone=c.phone, city=c.city, state=c.state, website=c.website,
            site_verified="yes" if conf == "high" else "CHECK",
            observation_1=obs[0] if obs else "", observation_2=obs[1] if len(obs) > 1 else "",
            all_findings="; ".join(c.reasons),
        ))
    rows.sort(key=lambda r: (r.priority, r.email == "", r.company))
    for i, r in enumerate(rows, 1):
        r.lead_id = f"GCS-{i:03d}"
    return rows


def _display_name(name: str) -> str:
    """'GLOBAL PRODUCTION SERVICES, L.L.C.' -> 'Global Production Services, L.L.C.'"""
    if name.isupper():
        name = " ".join(w if len(w) <= 3 and "." in w else w.capitalize() for w in name.split())
        name = re.sub(r"\b(Llc|L\.l\.c\.|Lp|Inc)\b", lambda m: m.group(0).upper().replace("INC", "Inc"), name)
    return name


def write_grok_csv(rows: list[OutreachRow], path: Path, emails_only: bool = True) -> int:
    fields = list(OutreachRow.__dataclass_fields__)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            if emails_only and not r.email:
                continue
            w.writerow(r.__dict__)
            n += 1
    return n


def grok_prompt(sender: dict) -> str:
    s = sender
    return f"""You are my outreach assistant for {COMPANY}, a Gulf Coast company that modernizes \
websites and sets up AI systems (24/7 website assistants, quote-request capture, and automated \
lead generation) for oil & gas and energy companies.

THE LEAD FILE
I've connected a Google Sheet called "GCS Leads" (in my Google Drive). Each row is one company. \
Columns: lead_id, priority, company, contact_name, contact_title, email, backup_email, phone, city, \
state, website, site_verified, observation_1, observation_2, all_findings, status, date_sent, \
follow_up_due, notes.

YOUR JOB EACH RUN
1. Pick the next {s['daily']} rows where: status is blank, email is not blank, and site_verified = "yes". \
Work in priority order (A, then B, then C), top to bottom.
2. Write ONE short, personal email per company (rules below) and send it from my Gmail to the \
address in the "email" column only. Never use backup_email unless I tell you to.
3. After sending, update that row: status = "sent", date_sent = today's date, follow_up_due = 4 \
business days from today.
4. Follow-ups: for rows where status = "sent", follow_up_due is today or earlier, and there's no \
reply from that address in my inbox, send ONE short follow-up in the same thread (rules below) and \
set status = "followed up". Never send more than one follow-up per company.
5. Before sending anything, check my inbox. If a company has replied, set status = "replied", do \
not send them anything else, and add a one-line summary of their reply in "notes".
6. When you're done, send me a short summary: how many first emails and follow-ups you sent, and \
a list of any replies with company name + what they said.

EMAIL RULES (FIRST EMAIL)
- Plain text, no images, no attachments, no bold, no emojis. 70-120 words.
- One recipient per email. Never CC or BCC anyone.
- Greeting: "Hi {{first name}}," using contact_name. If contact_name is blank but the email is \
clearly a first name (like royce@company.com), use that name. Otherwise use "Hi {{company}} team,".
- Sentence 1: say you were looking at their website ({{website}}) and mention observation_1 (and \
observation_2 if it's there) in a friendly, helpful tone, like a neighbor pointing something out, \
not criticizing. Use your own words; don't copy the observation text word for word.
- Sentence 2-3: say {COMPANY} works with Gulf Coast energy companies to modernize their websites \
and set up AI systems that answer inquiries around the clock and help bring in new work.
- Then: say we have an offer we'd like to walk them through, and ask for a quick 15-minute call \
this week or next. Include my booking link: {s['calendar']}
- DO NOT mention any price, cost, dollar amount, discount, or "free". Don't say "AI-powered \
revolution" or similar hype. Don't make promises about results.
- Sign off with my signature exactly:
{s['name']}
{s['title']}, {COMPANY}
{s['phone']}
- Then a blank line and this footer exactly:
{COMPANY} | {s['address']}
If you'd rather not hear from me, just reply "no thanks" and I won't email again.
- Subject line: short, lowercase-friendly, specific to them, no clickbait. Examples: \
"quick note about {{company}}'s website", "{{company}} website", "question for {{first name}}". \
Never use "RE:" or "FWD:" on a first email.

EMAIL RULES (FOLLOW-UP)
- Reply in the same thread, 30-50 words, plain text. Briefly bump the first note, repeat the \
15-minute call ask and booking link, same signature and footer. No new claims.

SAFETY RULES (ALWAYS)
- Maximum {s['daily']} first emails + {s['daily']} follow-ups per run. Never exceed this even if I \
ask in a hurry.
- If anyone replies "no thanks", "unsubscribe", "remove me", "stop", or anything similar: set \
status = "do not contact" and never email that company again.
- If an email bounces: set status = "bounced" and copy the bounce reason into notes.
- If someone replies with interest or a question: set status = "replied", DO NOT answer them \
yourself, and tell me right away. I handle all replies personally.
- Never invent facts about a company. Only use what's in their row.
- If you're unsure about anything, skip that row, put the reason in notes, and tell me.

TEST MODE
The first time you run, DO NOT SEND. Instead, save the first 5 emails as Gmail drafts and show \
them to me. Only start sending after I reply "approved"."""


def write_prompt(sender: dict, path: Path) -> str:
    text = grok_prompt(sender)
    path.write_text(text + "\n", encoding="utf-8")
    return text
