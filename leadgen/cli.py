"""Command-line entry point.

  python -m leadgen run                       # BOEM -> discover sites -> audit -> score -> report
  python -m leadgen run --places              # also pull oilfield service cos. from Google Places
  python -m leadgen run --seed my_list.csv    # add your own list (name,city,state,website,phone)
  python -m leadgen run --limit 100           # quick test on the first 100 companies
  python -m leadgen audit-url https://example.com
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import audit, discover, report, score
from .models import load_seed_csv, merge, save_json
from .sources import boem, places

DATA = Path("data")


def cmd_run(args) -> None:
    lists = []
    states = set(s.strip().upper() for s in args.states.split(","))
    if not args.no_boem:
        print("Fetching BOEM Gulf company list...")
        b = boem.fetch(DATA / "raw", states, skip_paper_entities=not args.keep_holding_cos)
        print(f"  {len(b)} active BOEM companies in {sorted(states)}")
        lists.append(b)
    if args.places:
        print("Searching Google Places for oilfield service companies...")
        p = places.fetch(max_pages=args.places_pages)
        p = [c for c in p if c.state in states]
        print(f"  {len(p)} Places results")
        lists.append(p)
    for seed in args.seed or []:
        s = load_seed_csv(Path(seed))
        print(f"  {len(s)} companies from {seed}")
        lists.append(s)

    companies = merge(*lists)
    if args.limit:
        companies = companies[: args.limit]
    print(f"{len(companies)} unique companies.")

    if not args.skip_discover:
        discover.discover(companies, workers=args.workers)
    audit.audit_all(companies, workers=args.workers)
    ranked = score.score_all(companies)
    if args.require_site:
        ranked = [c for c in ranked if c.website]

    save_json(ranked, DATA / "leads.json")
    report.write_csv(ranked, DATA / "leads.csv")
    report.write_html(ranked, DATA / "leads.html")
    print(f"\nWrote {len(ranked)} leads to data/leads.csv, data/leads.json, data/leads.html")
    for c in ranked[:15]:
        print(f"  {c.score:>3}  {c.name[:45]:<45} {c.website[:40]}")


def cmd_rescore(args) -> None:
    """Re-apply filters + scoring to data/leads.json without re-crawling."""
    from .models import load_json
    from .sources.boem import _MAJORS, _PAPER_ENTITY
    companies = [c for c in load_json(DATA / "leads.json")
                 if not (c.source == "boem" and (_MAJORS.search(c.name) or _PAPER_ENTITY.search(c.name)))]
    for c in companies:  # undo previous grouping so it can be redone
        c.audit.pop("related_entities", None)
    ranked = score.score_all(companies)
    save_json(ranked, DATA / "leads.json")
    report.write_csv(ranked, DATA / "leads.csv")
    report.write_html(ranked, DATA / "leads.html")
    print(f"Rescored {len(ranked)} leads.")


def cmd_contacts(args) -> None:
    """Add emails / phones / leadership names to data/leads.json from each lead's own website."""
    from . import contacts
    from .models import load_json
    companies = load_json(DATA / "leads.json")
    contacts.scrape_all(companies, workers=args.workers)
    save_json(companies, DATA / "leads.json")
    report.write_csv(companies, DATA / "leads.csv")
    report.write_html(companies, DATA / "leads.html")


def cmd_outreach(args) -> None:
    """Build grok_leads.csv, grok_prompt.txt, the setup guide PDF and the lead book PDF."""
    from . import outreach, pdfs
    from .models import load_json
    sender = {"name": args.name, "title": args.title, "phone": args.phone, "address": args.address,
              "calendar": args.calendar, "daily": args.daily}
    companies = load_json(DATA / "leads.json")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = outreach.build_rows(companies)
    n = outreach.write_grok_csv(rows, out / "grok_leads.csv")
    outreach.write_prompt(sender, out / "grok_prompt.txt")
    stats = pdfs.build_lead_book(out / "GCS_Lead_Book.pdf", companies, sender)
    pdfs.build_setup_guide(out / "GCS_Setup_Guide.pdf", stats, sender)
    print(f"Wrote {out}/grok_leads.csv ({n} companies with email), grok_prompt.txt, "
          f"GCS_Lead_Book.pdf, GCS_Setup_Guide.pdf")
    print(stats)


def cmd_audit_url(args) -> None:
    from .models import Company
    c = Company(name=args.url, website=args.url)
    c.audit = audit.audit_url(args.url)
    score.score(c)
    print(json.dumps({"score": c.score, "reasons": c.reasons, "pitch": c.pitch, "audit": c.audit}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(prog="leadgen")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="full pipeline")
    r.add_argument("--states", default="TX,LA,MS,AL,FL")
    r.add_argument("--no-boem", action="store_true")
    r.add_argument("--keep-holding-cos", action="store_true", help="don't drop trusts/holding cos/funds")
    r.add_argument("--places", action="store_true", help="use Google Places (needs GOOGLE_PLACES_API_KEY)")
    r.add_argument("--places-pages", type=int, default=1)
    r.add_argument("--seed", action="append", help="extra CSV(s): name,city,state,website,phone")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--workers", type=int, default=16)
    r.add_argument("--skip-discover", action="store_true")
    r.add_argument("--require-site", action="store_true", help="only output companies with a website")
    r.set_defaults(fn=cmd_run)

    rs = sub.add_parser("rescore", help="re-filter and re-score data/leads.json without re-crawling")
    rs.set_defaults(fn=cmd_rescore)

    ct = sub.add_parser("contacts", help="scrape public emails/phones/leaders from lead websites")
    ct.add_argument("--workers", type=int, default=24)
    ct.set_defaults(fn=cmd_contacts)

    o = sub.add_parser("outreach", help="build Grok lead file, prompt and printable PDFs")
    o.add_argument("--name", default="[Your Name]")
    o.add_argument("--title", default="[Your Title]")
    o.add_argument("--phone", default="[Your Phone]")
    o.add_argument("--address", default="[Your Business Mailing Address]")
    o.add_argument("--calendar", default="[Your Booking Link]")
    o.add_argument("--daily", type=int, default=10, help="max first emails per Grok run")
    o.add_argument("--out", default="outreach")
    o.set_defaults(fn=cmd_outreach)

    u = sub.add_parser("audit-url", help="audit a single website")
    u.add_argument("url")
    u.set_defaults(fn=cmd_audit_url)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
