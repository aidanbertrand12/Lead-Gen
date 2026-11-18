# Gulf Coast Oil & Gas Lead Gen

Finds Gulf Coast oil & gas companies, audits their websites for outdated tech and
missing lead capture, and ranks them as prospects for the $35k AI Growth Package
(see [PRICING.md](PRICING.md)).

## Pipeline
1. **Source companies**
   - **BOEM** (default, free): every active company qualified to operate on the Gulf
     outer continental shelf, filtered to TX/LA/MS/AL/FL. Trusts, funds, holding
     companies and majors are dropped (`--keep-holding-cos` keeps them).
   - **Google Places** (`--places`, needs `GOOGLE_PLACES_API_KEY`): oilfield *service*
     companies (fabrication, trucking, rentals, marine) across about 36 Gulf cities.
     **This is the best source for $35k buyers**, because service companies sell to operators and need leads.
   - **Your own CSV** (`--seed file.csv`, columns `name,city,state,website,phone`), e.g. exports
     from Texas RRC, Louisiana SONRIS, trade show lists, or purchased lists.
2. **Find websites**: guesses likely domains from the company name and accepts one only if the
   page names the company, uses oil & gas language, and isn't a parked/for-sale domain.
3. **Audit**: one request per homepage. Checks HTTPS/SSL, mobile viewport, Flash/frames/table layouts,
   copyright year, WordPress/jQuery/PHP versions, page speed, SEO basics, chat widget, forms,
   quote/RFQ calls-to-action, analytics (including dead Universal Analytics), CRM pixels.
4. **Score**: 0–100 opportunity score, plus the findings and the package line items to pitch.
   Subsidiaries that share one website are merged into one lead.
5. **Report**: `data/leads.csv` (CRM import), `data/leads.json`, `data/leads.html` (sortable and filterable).

## Usage
```bash
pip install -r requirements.txt
python -m leadgen run --limit 100                # quick test
python -m leadgen run                            # all BOEM Gulf companies (~30 min)
GOOGLE_PLACES_API_KEY=... python -m leadgen run --places --require-site
python -m leadgen run --no-boem --seed data/my_list.csv
python -m leadgen rescore                        # re-filter/re-score data/leads.json, no re-crawl
python -m leadgen audit-url https://somecompany.com   # audit a single site for a sales call
```

## Notes
- `site_confidence`: **high** = the page title names the company and the industry; **review** = check by hand (e.g. a bare "Home" title); guesses that are clearly another business are dropped. Spend 30 seconds checking any guessed site before outreach.
- Score 50+ means a hot lead. A score of 40 with "No website found" needs a manual check, because many BOEM
  entities are inactive or paper companies.
- Domain guessing misses companies whose domain doesn't match their name. Google Places fills that gap.
- Outreach: follow CAN-SPAM (physical address, working unsubscribe, honest subject lines) and
  warm up sending domains before running cold campaigns.
