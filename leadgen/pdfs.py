"""Printable PDFs for Gulf Coast Systems: the setup guide and the lead book."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .models import Company
from .outreach import COMPANY, OutreachRow, build_rows, grok_prompt

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")

NAVY = colors.HexColor("#0B3C5D")
TEAL = colors.HexColor("#1B7F8C")
SAND = colors.HexColor("#F3EFE6")
LINE = colors.HexColor("#C9CED6")
MUTED = colors.HexColor("#5A6472")
HOT = colors.HexColor("#B5482A")

ST = {
    "title": ParagraphStyle("title", fontName="Sans-Bold", fontSize=26, leading=32, textColor=NAVY),
    "subtitle": ParagraphStyle("subtitle", fontName="Sans", fontSize=13, leading=18, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="Sans-Bold", fontSize=17, leading=22, textColor=NAVY,
                         spaceBefore=6, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Sans-Bold", fontSize=12.5, leading=16, textColor=TEAL,
                         spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Sans", fontSize=10, leading=14.5, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=8.5, leading=11.5, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=8.8, leading=11.5),
    "cellb": ParagraphStyle("cellb", fontName="Sans-Bold", fontSize=8.8, leading=11.5),
    "tiny": ParagraphStyle("tiny", fontName="Sans", fontSize=6.8, leading=8.4),
    "bullet": ParagraphStyle("bullet", fontName="Sans", bulletFontName="Sans", fontSize=10, leading=14.5, leftIndent=16,
                             bulletIndent=4, spaceAfter=2.5),
    "check": ParagraphStyle("check", fontName="Sans", bulletFontName="Sans", fontSize=10, leading=15, leftIndent=18,
                            bulletIndent=2, spaceAfter=2.5),
    "mono": ParagraphStyle("mono", fontName="Mono", fontSize=7.6, leading=9.8),
    "monobox": ParagraphStyle("monobox", fontName="Mono", fontSize=7.6, leading=9.8, backColor=SAND,
                              borderColor=NAVY, borderWidth=0.8, borderPadding=8, leftIndent=8, rightIndent=8,
                              spaceBefore=8),
    "card_title": ParagraphStyle("card_title", fontName="Sans-Bold", fontSize=11.5, leading=14, textColor=NAVY),
    "center": ParagraphStyle("center", fontName="Sans", fontSize=10, leading=14, alignment=TA_CENTER, textColor=MUTED),
}


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, ST[style])


def bullets(items: list[str], style: str = "bullet", mark: str = "•") -> list[Paragraph]:
    return [Paragraph(t, ST[style], bulletText=mark) for t in items]


def checks(items: list[str]) -> list[Paragraph]:
    return bullets(items, "check", "☐")


def table(rows: list[list], widths: list[float], header: bool = True, zebra: bool = True) -> Table:
    data = [[c if not isinstance(c, str) else P(escape(c) if "<" not in c else c,
                                                 "cellb" if header and i == 0 else "cell")
             for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), SAND))
    if zebra:
        for i in range(2 if header else 1, len(rows), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFAF8")))
    t.setStyle(TableStyle(style))
    return t


def callout(flowables: list, color=TEAL) -> Table:
    t = Table([[flowables]], colWidths=[7.0 * inch])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, color), ("BACKGROUND", (0, 0), (-1, -1), SAND),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def _doc(path: Path, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(str(path), pagesize=letter, title=title, author=COMPANY,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                             topMargin=0.8 * inch, bottomMargin=0.75 * inch)


def _page_deco(label: str):
    def deco(canvas, doc):
        canvas.saveState()
        w, h = letter
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 0.32 * inch, w, 0.32 * inch, stroke=0, fill=1)
        canvas.setFont("Sans-Bold", 8)
        canvas.setFillColor(colors.white)
        canvas.drawString(0.75 * inch, h - 0.21 * inch, COMPANY.upper())
        canvas.setFont("Sans", 8)
        canvas.drawRightString(w - 0.75 * inch, h - 0.21 * inch, label)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w - 0.75 * inch, 0.45 * inch, f"Page {doc.page}")
        canvas.drawString(0.75 * inch, 0.45 * inch, dt.date.today().strftime("%B %d, %Y"))
        canvas.restoreState()
    return deco


# --------------------------------------------------------------------------- setup guide

def build_setup_guide(path: Path, stats: dict, sender: dict) -> None:
    s = []
    s += [Spacer(1, 1.3 * inch), P(COMPANY, "subtitle"), P("Cold Outreach Setup Guide", "title"),
          Spacer(1, 6), P("How to set up your sending inbox, Grok and your daily routine so you can email "
                          "Gulf Coast energy companies and book intro calls.", "subtitle"),
          Spacer(1, 0.4 * inch)]
    s.append(callout([
        P("<b>The goal of every email is a 15-minute call. Not a sale.</b>"),
        P("We do not mention price, the $35k package, or anything that sounds like a pitch. "
          "We point out one or two real things we noticed on their website, say we have an offer, "
          "and ask for a short call. The offer and pricing happen on the call."),
    ]))
    s.append(Spacer(1, 0.3 * inch))
    s.append(table([
        ["What you have now", ""],
        ["Companies on the list", f"{stats['total']:,}"],
        ["With a website we checked", f"{stats['with_site']:,}"],
        ["With an email address", f"{stats['with_email']:,}"],
        ["Ready to email now (website confirmed + email)", f"{stats['ready']:,}"],
        ["With a named executive (CEO, President, owner...)", f"{stats['named']:,}"],
        ["Call list (phone, no email)", f"{stats['call_only']:,}"],
    ], [5.0 * inch, 2.0 * inch]))
    s.append(Spacer(1, 0.25 * inch))
    s.append(P("<b>Files that go with this guide</b>", "body"))
    s += bullets([
        "<b>GCS_Lead_Book.pdf</b>: every lead with contact info, website findings and talking points, "
        "plus the Grok prompt. Print it and use it as your call sheet.",
        "<b>grok_leads.csv</b>: the lead file you upload to Google Drive for Grok (one row per company "
        "that has an email).",
        "<b>grok_prompt.txt</b>: the same prompt as in the lead book, ready to copy and paste.",
    ])
    s.append(PageBreak())

    # Overview
    s.append(P("How the system works", "h1"))
    flow = Table([[P("<b>1. Lead list</b><br/>grok_leads.csv in Google Drive", "cell"), "→",
                   P("<b>2. Grok</b><br/>writes one personal email per company", "cell"), "→",
                   P("<b>3. Your Gmail</b><br/>sends 10-20 a day from your outreach inbox", "cell"), "→",
                   P("<b>4. You</b><br/>answer replies and book the call", "cell")]],
                 colWidths=[1.55 * inch, 0.22 * inch, 1.55 * inch, 0.22 * inch, 1.55 * inch, 0.22 * inch, 1.55 * inch])
    flow.setStyle(TableStyle([("BOX", (0, 0), (0, 0), 0.8, TEAL), ("BOX", (2, 0), (2, 0), 0.8, TEAL),
                              ("BOX", (4, 0), (4, 0), 0.8, TEAL), ("BOX", (6, 0), (6, 0), 0.8, NAVY),
                              ("BACKGROUND", (0, 0), (0, 0), SAND), ("BACKGROUND", (2, 0), (2, 0), SAND),
                              ("BACKGROUND", (4, 0), (4, 0), SAND), ("BACKGROUND", (6, 0), (6, 0), SAND),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                              ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    s += [flow, Spacer(1, 10)]
    s.append(P("Grok does the repetitive part: reading each row, writing a personal email, sending it, "
               "following up once, and keeping the sheet updated. <b>You do the part that makes money: "
               "replying to people and running the call.</b> Grok never answers replies for you."))
    s.append(P("Total setup time: about 2 hours of work, then <b>2-3 weeks of inbox warm-up</b> before the "
               "first cold email goes out. Do not skip the warm-up. A brand-new inbox that sends cold email "
               "gets flagged as spam, and then nothing you send arrives."))

    s.append(P("Shopping list", "h2"))
    s.append(table([
        ["Item", "What it's for", "Approx. cost"],
        ["Outreach domain (e.g. from Google Domains/Squarespace, Namecheap, Cloudflare)",
         "A separate web address just for cold email, so your main domain stays safe", "$10-20 / year"],
        ["Google Workspace (Business Starter), 1-2 inboxes", "Your professional Gmail, e.g. you@yourdomain.com",
         "about $8-9 per inbox / month"],
        ["X Subscription, Premium plan (includes Grok Bot + connectors)", "Grok writes and sends the emails",
         "$30 / month"],
        ["Email verifier (ZeroBounce, NeverBounce, or similar)", "Removes dead addresses before you send",
         "free tier / about $10 per 1,000"],
        ["Booking link (Google Calendar appointment schedule, or Calendly free)", "Lets people book the call themselves",
         "included / free"],
        ["<b>Total</b>", "", "<b>about $50-60 / month</b>"],
    ], [2.8 * inch, 2.9 * inch, 1.3 * inch]))
    s.append(P("Prices change. Confirm each one on the signup page before you buy.", "small"))
    s.append(PageBreak())

    # Step 1-3
    s.append(P("Step 1: Buy your outreach domain", "h1"))
    s.append(P("Keep your main business domain (the one on your website and business cards) for normal email. "
               "Buy a second, similar domain just for cold outreach. If that one ever gets flagged, your main "
               "domain and its inbox aren't affected."))
    s += bullets([
        "Pick something that clearly reads as your company, for example <b>gulfcoastsystems.co</b>, "
        "<b>getgulfcoastsystems.com</b>, <b>gulfcoastsystemsllc.com</b> or <b>gulfcoast-systems.com</b>. "
        "Check which ones are available.",
        "Use <b>.com</b> if you can, otherwise .co or .net. Avoid odd endings like .xyz or .info, which spam filters distrust.",
        "Set the new domain to <b>forward to your main website</b>, so anyone who types it in lands on your real site.",
    ])
    s += checks(["Outreach domain purchased", "Domain forwards to main website"])

    s.append(P("Step 2: Set up Google Workspace", "h1"))
    s += bullets([
        "Go to workspace.google.com and sign up with your outreach domain. Choose Business Starter.",
        "Create your inbox as a real person: <b>firstname@yourdomain.com</b> or <b>firstname.lastname@</b>. "
        "Never use info@ or sales@ for cold email.",
        "Optional: create a second inbox (for example a partner or a second spelling of your name). Two inboxes "
        "let you send twice as many emails safely.",
        "Add a profile photo (a real headshot) and your full name to each inbox.",
        f"Set your Gmail signature: <b>{escape(sender['name'])}</b> / {escape(sender['title'])}, {COMPANY} / "
        f"{escape(sender['phone'])}. Plain text, no images or logos.",
    ])
    s += checks(["Workspace account created", "Inbox created (real name)", "Profile photo + signature added"])

    s.append(P("Step 3: Authenticate your domain (SPF, DKIM, DMARC)", "h1"))
    s.append(P("These three DNS records prove to Gmail, Outlook and Yahoo that your emails are really from you. "
               "Without them a lot of your mail goes to spam. Add them where you bought the domain, under "
               "<b>DNS settings</b>."))
    s.append(table([
        ["Record", "Type", "Name / Host", "Value"],
        ["SPF", "TXT", "@", "v=spf1 include:_spf.google.com ~all"],
        ["DKIM", "TXT", "google._domainkey",
         "Generate it in Google Admin → Apps → Google Workspace → Gmail → Authenticate email. "
         "Paste the value Google gives you, then click <b>Start authentication</b>."],
        ["DMARC", "TXT", "_dmarc", "v=DMARC1; p=none; rua=mailto:you@yourdomain.com"],
    ], [0.7 * inch, 0.55 * inch, 1.35 * inch, 4.4 * inch]))
    s.append(P("DNS changes can take a few hours. To check: send an email to a personal Gmail, open it, click "
               "the ⋮ menu → <b>Show original</b>. SPF, DKIM and DMARC should all say <b>PASS</b>.", "small"))
    s += checks(["SPF added", "DKIM generated + authentication started", "DMARC added",
                 "Test email shows PASS / PASS / PASS"])
    s.append(PageBreak())

    # Step 4 warm-up
    s.append(P("Step 4: Warm up the inbox (2-3 weeks)", "h1"))
    s.append(P("Email providers trust inboxes that have a history of normal, two-way conversations. Spend the "
               "first weeks using the inbox like a real person. You can also turn on an automatic warm-up "
               "service (for example the warm-up feature in Instantly, Smartlead, Lemwarm or Warmup Inbox) to "
               "speed this up, but still do the manual part."))
    s.append(table([
        ["Week", "What to do each weekday", "Cold emails"],
        ["Week 1", "Send 5-10 real emails to friends, family, colleagues and clients. Ask them to reply. "
                   "Sign up for 3-4 industry newsletters (Hart Energy, Offshore Magazine, Rigzone, local "
                   "chamber of commerce) and open them.", "0"],
        ["Week 2", "Send 10-15 real emails a day. Keep conversations going back and forth. If anything lands "
                   "in someone's spam folder, ask them to mark it 'Not spam'.", "0"],
        ["Week 3", "Keep up normal emails. Start Grok in TEST MODE (drafts only, see Step 7).", "0-5 (drafts)"],
        ["Week 4", "Start sending: 10 cold emails per day per inbox.", "10 / day"],
        ["Week 5+", "If bounces are under 3% and no spam complaints: go up to 20 per day per inbox. "
                    "Never go above 30.", "20 / day"],
    ], [0.75 * inch, 5.1 * inch, 1.15 * inch]))
    s += checks(["Week 1 done", "Week 2 done", "Week 3 done"])

    s.append(P("Step 5: Create your booking link", "h1"))
    s += bullets([
        "In Google Calendar: <b>Create → Appointment schedule</b>. Name it <b>15-minute intro call</b>, set "
        "15 minutes, and pick the times you're free (for example Tue-Thu, 9-11am and 1-4pm Central).",
        "Add a Google Meet link, or ask for their phone number in the booking form.",
        "Copy the booking page link. This is your <b>[Your Booking Link]</b> in the Grok prompt.",
        "Calendly (free plan) works just as well if you prefer it.",
    ])
    s += checks(["Booking link created", "Test-booked it yourself to make sure it works"])

    s.append(P("Step 6: Clean the email list", "h1"))
    s += bullets([
        "Open <b>grok_leads.csv</b>. Rows marked <b>site_verified = CHECK</b> were matched to a website by "
        "guessing. Spend about 30 seconds opening each website. If it's clearly the right company, change "
        "CHECK to <b>yes</b>. If not, delete the row.",
        "Upload the email column to an email verifier (ZeroBounce or NeverBounce). Delete rows it marks "
        "<b>invalid</b>. Keep 'catch-all' only if you're short on leads.",
        "Delete any company you already know, or don't want to contact.",
    ])
    s += checks(["CHECK rows reviewed", "Emails verified, invalid ones removed"])
    s.append(PageBreak())

    # Step 7 Grok
    s.append(P("Step 7: Set up Grok", "h1"))
    s.append(P("1. Subscribe", "h2"))
    s += bullets(["Get the <b>Premium</b> plan of The X Subscription ($30/month). This includes Grok Bot, "
                  "automations and connectors. You don't need Super or Ultra for this volume."])
    s.append(P("2. Connect your accounts", "h2"))
    s += bullets([
        "In Grok, open <b>Settings → Connectors</b>. Connect <b>Gmail</b> using your new <b>outreach inbox</b>, "
        "not your personal or main business email. Turn on the <b>send</b> permission.",
        "Connect <b>Google Drive</b> (same Google account).",
        "Do <b>not</b> use Grok Bot's own @mail.grokbot.com address for this. Emails should come from "
        f"{COMPANY}, not from a bot address.",
    ])
    s.append(P("3. Upload the lead file", "h2"))
    s += bullets([
        "Upload <b>grok_leads.csv</b> to Google Drive, then open it with Google Sheets "
        "(File → Save as Google Sheets). Name the sheet <b>GCS Leads</b>.",
        "Leave the status, date_sent, follow_up_due and notes columns empty. Grok fills them in.",
    ])
    s.append(P("4. Fill in your details and paste the prompt", "h2"))
    s += bullets([
        "Open <b>grok_prompt.txt</b> (also printed in the lead book). Replace every <b>[bracketed]</b> item: "
        "your name, title, phone, business mailing address and booking link.",
        "The mailing address is required by law (CAN-SPAM). A PO box or registered business address is fine.",
        "Paste the prompt into Grok and add: <i>\"Run this now in TEST MODE.\"</i>",
    ])
    s.append(P("5. Test mode (do not skip)", "h2"))
    s += bullets([
        "Grok saves 5 emails as Gmail drafts instead of sending. Read every one. Check the names, that the "
        "website observations are accurate (open their site), that there's no price mentioned, and that the "
        "signature and footer are right.",
        "If something's off, tell Grok what to change (\"shorter\", \"less formal\", \"don't mention "
        "analytics\") and run test mode again.",
        "When they're good, reply <b>approved</b>.",
    ])
    s.append(P("6. Turn on the automation", "h2"))
    s += bullets([
        "Tell Grok: <i>\"Create an automation that runs this every weekday at 8:30 AM Central.\"</i>",
        "Start with <b>10 per day</b> (the prompt's limit). After a clean first week, edit the prompt's daily "
        "number to 20.",
        "Tuesday to Thursday mornings get the best replies. Monday and Friday are fine but slower.",
    ])
    s += checks(["Premium plan active", "Gmail (send) + Drive connected", "GCS Leads sheet uploaded",
                 "Prompt filled in", "Test drafts reviewed + approved", "Weekday automation on"])
    s.append(PageBreak())

    # Step 8 daily routine
    s.append(P("Step 8: Your daily routine (15-30 minutes)", "h1"))
    s += checks([
        "Read Grok's daily summary (how many sent, any replies).",
        "Open your outreach inbox. <b>Answer every interested reply within 1 hour</b> if you can. Speed wins meetings.",
        "Check the GCS Leads sheet: anything marked bounced, do not contact, or with a note from Grok.",
        "Write down calls booked and outcomes in the lead book (each lead has checkboxes).",
        "Once a week: check bounce rate and replies (see the scorecard below).",
    ])
    s.append(P("How to answer replies", "h2"))
    s.append(table([
        ["They say...", "You reply..."],
        ["\"Sure, let's talk\" / asks a question",
         "Thank them, answer in 1-2 lines, and offer two specific times plus the booking link. "
         "\"Does Tuesday at 10 or Wednesday at 2 work? Or grab any time here: [link]\""],
        ["\"What's the offer?\" / \"Send me info\"",
         "Keep it short and steer to the call: \"Happy to. It depends on how you get new work today, so it's "
         "much easier to show you in 15 minutes. I'll walk through what we found on your site. [link]\" "
         "Don't send pricing by email."],
        ["\"Not right now\"",
         "\"Totally understand. Mind if I check back in a few months?\" Note the date in the sheet."],
        ["\"I'm not the right person\"",
         "\"Thanks! Who would be the best person to talk to about your website and marketing?\""],
        ["\"No thanks\" / \"remove me\" / \"stop\"",
         "Don't reply. Grok marks them do not contact. Make sure they are never emailed again."],
        ["Angry or spam complaint", "Apologize once, remove them, and never contact them again."],
    ], [2.0 * inch, 5.0 * inch]))
    s.append(P("Weekly scorecard: what good looks like", "h2"))
    s.append(table([
        ["Metric", "Healthy", "Stop and fix if..."],
        ["Bounce rate", "under 2%", "over 3%: verify your list again"],
        ["Spam complaints", "0", "any: pause, soften the email, slow down"],
        ["Reply rate", "3-8%", "under 1% after 100 emails: rewrite the email"],
        ["Calls booked", "1-3 per 100 emails", "0 after 150 emails: change the call ask / observations"],
    ], [1.6 * inch, 1.8 * inch, 3.6 * inch]))
    s.append(PageBreak())

    # Step 9 call
    s.append(P("Step 9: The 15-minute intro call", "h1"))
    s.append(P("The call is where the offer is introduced. Before the call, open their lead card and their "
               "website. Have the two or three findings ready to show."))
    s.append(table([
        ["Minutes", "What happens"],
        ["0-1", "Thank them. Set the agenda: \"I'll ask a few questions about how you win work, show you what we "
                "noticed on your site, and if it makes sense, walk you through our offer.\""],
        ["1-6", "Ask, then listen: How do new customers find you today? Who's your ideal customer (operators, "
                "EPCs, midstream)? What happens when someone visits your website at 9pm? Who follows up "
                "on inquiries? What would one new contract be worth to you?"],
        ["6-9", "Share your screen. Show 2-3 findings from their site (phone view, 'Not Secure' warning, old "
                "copyright, no quote form). Keep it friendly. Everyone's website gets old."],
        ["9-13", "The offer: a modern website, a 24/7 AI assistant that captures quote requests, and an AI "
                 "system that finds and contacts new buyers for them. Describe outcomes, not tech."],
        ["13-15", "Next step: book a <b>proposal meeting</b> (30-45 min) where you present the full plan "
                  "and pricing (see PRICING.md). Get it on the calendar before you hang up."],
    ], [0.8 * inch, 6.2 * inch]))
    s.append(P("Rules and compliance", "h1"))
    s += bullets([
        "<b>CAN-SPAM (US law):</b> honest From name and subject line, your physical mailing address in every "
        "email, a clear way to opt out, and honor opt-outs right away (within 10 business days at most). "
        "The Grok prompt handles all of this. Don't remove the footer.",
        "<b>One recipient per email.</b> No CC/BCC blasts, no attachments, no tracking pixels.",
        "<b>Volume limits:</b> Google Workspace allows about 2,000 emails/day, but that's not a safe cold-email "
        "number. Stay at 10-20 (max 30) cold emails per inbox per day.",
        "<b>Business contacts only.</b> These are public business addresses from each company's own "
        "website, emailed about their business. Don't add personal addresses you find elsewhere.",
        "<b>Never</b> send from your main business domain, buy email lists, or email anyone who opted out.",
    ])
    s.append(P("Troubleshooting", "h2"))
    s.append(table([
        ["Problem", "Fix"],
        ["Grok says it can't send email", "Reconnect Gmail in Settings → Connectors and make sure send permission is on."],
        ["Grok can't find the sheet", "Make sure it's a Google Sheet (not just a CSV) named GCS Leads, in the same "
                                      "Google account that's connected."],
        ["Emails landing in spam", "Check SPF/DKIM/DMARC pass, slow to 10/day, keep warm-up running, remove links "
                                   "except the booking link."],
        ["Grok sends to the wrong rows", "Tell it to stop. Check the status column, then re-run test mode."],
        ["Lots of bounces", "Pause, run the list through the verifier again, delete invalid rows."],
    ], [2.2 * inch, 4.8 * inch]))

    doc = _doc(path, f"{COMPANY} - Outreach Setup Guide")
    doc.build(s, onFirstPage=_page_deco("Outreach Setup Guide"), onLaterPages=_page_deco("Outreach Setup Guide"))


# --------------------------------------------------------------------------- lead book

def _card(row: OutreachRow, c: Company) -> KeepTogether:
    ct = c.audit.get("contacts", {}) or {}
    head = Table([[P(f"{row.lead_id} &nbsp; {escape(row.company)}", "card_title"),
                   P(f"<b>Priority {row.priority}</b> · Score {c.score}", "cell")]],
                 colWidths=[5.4 * inch, 1.6 * inch])
    head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SAND), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LINEBELOW", (0, 0), (-1, -1), 1.2, HOT if row.priority == "A" else TEAL),
                              ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 4),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    loc = ", ".join(x for x in [c.address, c.city, f"{c.state} {c.zip}".strip()] if x)
    contact = f"{escape(row.contact_name)}, {escape(row.contact_title)}" if row.contact_name else "(no named contact found)"
    others = [p for p in ct.get("people", []) if not p.startswith(row.contact_name or "\x00")]
    lines = [
        ("Address", escape(loc)),
        ("Website", escape(c.website) + ("" if row.site_verified == "yes" else
                                          " &nbsp;<font color='#B5482A'><b>CHECK: verify this is their site</b></font>")),
        ("Contact", contact),
        ("Email", f"<b>{escape(row.email)}</b>" if row.email else "(none found, call or use the website contact form)"),
    ]
    extra_emails = [e for e in ct.get("emails", []) if e != row.email]
    if extra_emails:
        lines.append(("Other emails", escape(", ".join(extra_emails[:4]))))
    phones = ct.get("phones", []) or ([c.phone] if c.phone else [])
    lines.append(("Phone", escape(", ".join(phones[:3])) if phones else "-"))
    if others:
        lines.append(("Leadership", escape("; ".join(others[:4]))))
    li = ct.get("linkedin", "")
    if li:
        lines.append(("LinkedIn", escape(li)))
    rel = c.audit.get("related_entities") or []
    if rel:
        lines.append(("Related entities", escape("; ".join(rel[:6]))))
    a = c.audit
    tech = []
    if a.get("copyright_year"):
        tech.append(f"© {a['copyright_year']}")
    if a.get("wordpress"):
        tech.append("WordPress" + (f" {a['wordpress_version']}" if a.get("wordpress_version") else ""))
    if a.get("builder"):
        tech.append(a["builder"])
    if a.get("jquery_version"):
        tech.append(f"jQuery {a['jquery_version']}")
    if a.get("load_seconds"):
        tech.append(f"loads in {a['load_seconds']}s")
    tech.append("HTTPS" if a.get("https") else "no HTTPS")
    tech.append("mobile-ready" if a.get("has_viewport") else "not mobile-ready")
    lines.append(("Site snapshot", escape(" · ".join(tech))))
    lines.append(("Findings", escape("; ".join(c.reasons)) or "-"))
    talk = [o for o in (row.observation_1, row.observation_2) if o]
    if talk:
        lines.append(("Say on email/call", "<br/>".join("• " + escape(t[0].upper() + t[1:]) + "." for t in talk)))
    lines.append(("Tracking", "☐ Emailed ____/____ &nbsp;&nbsp; ☐ Follow-up ____/____ &nbsp;&nbsp; ☐ Replied "
                              "&nbsp;&nbsp; ☐ Call booked ____/____ &nbsp;&nbsp; ☐ Proposal &nbsp;&nbsp; ☐ Won"))
    body = Table([[P(k, "cellb"), P(v, "cell")] for k, v in lines], colWidths=[1.25 * inch, 5.75 * inch])
    body.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
                              ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                              ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TEXTCOLOR", (0, 0), (0, -1), MUTED)]))
    return KeepTogether([head, body, Spacer(1, 12)])


def build_lead_book(path: Path, companies: list[Company], sender: dict) -> dict:
    rows = build_rows(companies)
    by_site = {c.website: c for c in companies if c.website}
    ready = [r for r in rows if r.email and r.site_verified == "yes"]
    check = [r for r in rows if r.email and r.site_verified != "yes"]
    call = [r for r in rows if not r.email and (by_site[r.website].audit.get("contacts", {}) or {}).get("phones")]
    rest = [r for r in rows if not r.email and r not in call]
    no_site = sorted([c for c in companies if not c.website], key=lambda c: (c.state, c.city, c.name))
    stats = {"total": len(companies), "with_site": len(rows), "with_email": len(ready) + len(check),
             "ready": len(ready), "named": sum(1 for r in rows if r.email and r.contact_name),
             "call_only": len(call), "check": len(check), "no_contact": len(rest), "no_site": len(no_site)}

    s = [Spacer(1, 1.3 * inch), P(COMPANY, "subtitle"), P("Gulf Coast Energy Lead Book", "title"),
         Spacer(1, 6), P(f"{stats['total']:,} oil &amp; gas companies across Texas, Louisiana, Mississippi, "
                         f"Alabama and Florida, with website audits, contact details and outreach talking points.",
                         "subtitle"), Spacer(1, 0.35 * inch)]
    s.append(table([
        ["Section", "What's in it", "Leads"],
        ["A. Ready to email", "Website confirmed and email found. Start here, in order.", f"{len(ready)}"],
        ["B. Verify, then email", "Email found, but the website was matched by guessing. Check the site first.", f"{len(check)}"],
        ["C. Call list", "No email found, but a phone number is on their website.", f"{len(call)}"],
        ["D. Website, no contact info", "Use their website's contact form, or look them up on LinkedIn.", f"{len(rest)}"],
        ["Appendix", "Companies with no website found. Many may be inactive. Optional printing.", f"{len(no_site):,}"],
    ], [1.9 * inch, 4.3 * inch, 0.8 * inch]))
    s.append(Spacer(1, 0.25 * inch))
    s.append(callout([
        P("<b>How to read a lead card</b>"),
        *bullets([
            "<b>Priority A</b>: confirmed website, most outdated (score 40+). <b>B</b>: confirmed website. "
            "<b>C</b>: website needs checking.",
            "<b>Score</b> (0-100): how much their website and lead capture need work. Higher means a bigger opportunity.",
            "<b>Say on email/call</b>: the friendly observations Grok uses in the email. Use the same ones on the call.",
            "<b>Tracking</b>: tick the boxes as you go so the printed book stays your source of truth.",
        ]),
        P("Contact details were collected from each company's own public website and may be out of date. "
          "Always confirm before relying on them.", "small"),
    ]))
    s.append(PageBreak())

    s.append(P("The Grok prompt", "h1"))
    s.append(P("Upload <b>grok_leads.csv</b> to Google Drive as a Google Sheet named <b>GCS Leads</b>, connect "
               "Gmail (send on) and Drive in Grok, replace the <b>[bracketed]</b> items with your details, and paste "
               "this in. The same text is in <b>grok_prompt.txt</b>. The email never mentions price. "
               "It asks for a 15-minute call."))
    s.append(Preformatted(grok_prompt(sender), ST["monobox"], maxLineLength=100))
    s.append(Spacer(1, 8))
    s.append(P("Example of the kind of email this produces", "h2"))
    ex = ready[0] if ready else None
    if ex:
        first = ex.contact_name.split()[0] if ex.contact_name else f"{ex.company} team"
        obs = " and ".join(o for o in (ex.observation_1, ex.observation_2) if o)
        sample = (f"Subject: quick note about {ex.company}'s website\n\n"
                  f"Hi {first},\n\n"
                  f"I was looking at {ex.website.split('//')[-1].rstrip('/')} and noticed {obs}. "
                  f"Easy things to miss when you're busy running operations.\n\n"
                  f"{COMPANY} works with Gulf Coast energy companies to modernize their websites and set up AI "
                  f"systems that answer inquiries around the clock and help bring in new work.\n\n"
                  f"We have an offer I'd like to walk you through. Would you be open to a quick 15-minute call "
                  f"this week or next? You can grab a time here: {sender['calendar']}\n\n"
                  f"{sender['name']}\n{sender['title']}, {COMPANY}\n{sender['phone']}\n\n"
                  f"{COMPANY} | {sender['address']}\n"
                  f"If you'd rather not hear from me, just reply \"no thanks\" and I won't email again.")
        s.append(Preformatted(sample, ST["monobox"], maxLineLength=100))
    s.append(PageBreak())

    for title, intro, group in [
        ("A. Ready to email", "Confirmed website and email address. Grok works through these first.", ready),
        ("B. Verify, then email", "These websites were matched by guessing the domain. Open each one. If it's "
                                  "the right company, change site_verified from CHECK to yes in the sheet. "
                                  "If not, delete the row.", check),
        ("C. Call list", "No email on their website, but there's a phone number. Call, mention what you noticed "
                         "on their site, and ask for the right person and their email.", call),
        ("D. Website, no contact info", "Use the contact form on their website, or find the owner or "
                                        "president on LinkedIn.", rest),
    ]:
        if not group:
            continue
        s.append(P(f"{title} ({len(group)})", "h1"))
        s.append(P(intro))
        for r in group:
            s.append(_card(r, by_site[r.website]))
        s.append(PageBreak())

    s.append(P(f"Appendix: Companies with no website found ({len(no_site):,})", "h1"))
    s.append(P("These companies are active on the federal offshore register (BOEM), but no website was found "
               "for them. Many are small, inactive, or exist only on paper. Some may be worth a call or a quick "
               "Google search, especially the ones in Gulf Coast towns like Lafayette, Houma or New Iberia. "
               "This section is long. Print it only if you need it.", "small"))
    rows_tbl = [["Company", "Address", "City", "St", "ZIP"]]
    rows_tbl += [[P(escape(c.name), "tiny"), P(escape(c.address), "tiny"), P(escape(c.city), "tiny"),
                  P(c.state, "tiny"), P(c.zip, "tiny")] for c in no_site]
    t = Table(rows_tbl, colWidths=[2.55 * inch, 2.3 * inch, 1.2 * inch, 0.35 * inch, 0.6 * inch], repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Sans-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                           ("BACKGROUND", (0, 0), (-1, 0), SAND), ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), 1.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    s.append(t)

    doc = _doc(path, f"{COMPANY} - Gulf Coast Energy Lead Book")
    doc.build(s, onFirstPage=_page_deco("Lead Book"), onLaterPages=_page_deco("Lead Book"))
    return stats
