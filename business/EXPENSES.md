# Gulf Coast Growth Systems — business expenses

The log lives in [`expenses.csv`](expenses.csv) (opens in Excel / Google Sheets).
Every time you buy something for the business, add a row, or tell Claude and it will add it.

## Rules that make tax time easy
- **Save every receipt** (PDF or screenshot) in one folder, e.g. Google Drive → `Business/Receipts/2026`.
  Name files `2026-11-20_xAI_Grok.pdf`. Mark `receipt_saved = yes` in the log.
- **Pay with one card used only for the business** if you can. It makes the log easy to check against statements.
- **Record the real amount from the receipt** (with tax), not the advertised price. Rows marked
  `planned` are estimates; change them to `active` with the real amount and date when you pay.
- **Cancelled something?** Keep the row, set `status = cancelled`, and add the end date in notes.
- **Monthly subscriptions:** log the first charge; at year-end, total the months actually paid.

## Categories used (common small-business expense categories)
| Category | Examples |
|---|---|
| Software & subscriptions | Grok, Google Workspace, CRM, Calendly |
| Advertising & marketing | Domains for outreach, email verification, lead data, ads |
| Office & supplies | Printer paper/ink for the lead book, equipment |
| Contract labor | Freelancers you pay |

This is a record-keeping aid, not tax advice. Have a tax preparer or CPA confirm how to file and
what's deductible for your situation (business structure, home office, mileage, etc.).
