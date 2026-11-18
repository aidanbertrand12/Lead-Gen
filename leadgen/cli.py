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

    u = sub.add_parser("audit-url", help="audit a single website")
    u.add_argument("url")
    u.set_defaults(fn=cmd_audit_url)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
