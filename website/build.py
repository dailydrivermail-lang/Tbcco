"""Build the Wolfey marketing site (static, five pages) into website/dist/ or --out.

    python website/build.py [--out DIR] [--noindex]

Pages share one header and footer. The two videos in marketing/video/ are the centrepiece.
All links are relative, so the site works at any path (a domain root or a GitHub Pages subfolder).
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VIDEO = ROOT / "marketing" / "video"
EMAIL = "hello@wolfey.com.au"   # placeholder until the mailbox exists

# Short hash of the stylesheet and script. It goes on their URLs, so a browser never pairs new pages with an old cached copy.
import hashlib
VERSION = hashlib.sha256((HERE / "site.css").read_bytes() + (HERE / "site.js").read_bytes()).hexdigest()[:10]

MARK_PATH = "M3.5 3.2 9 7.6 12 6l3 1.6 5.5-4.4v10C20.5 18.6 16.6 21.4 12 22.6 7.4 21.4 3.5 18.6 3.5 13.2z"
MARK = f'<span class="logo-mark"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="{MARK_PATH}"/></svg></span>'
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='" + MARK_PATH.replace(" ", "%20")
           + "' fill='%230b5cff' stroke='%230b5cff' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E")
NAV = [("compliance.html", "Compliance"), ("tenders.html", "Tenders"), ("pricing.html", "Pricing"), ("contact.html", "Contact")]


TICKS = [("index.html", "No new software. No logins. We just get on with it."),
         ("compliance.html", "Your own address: yourbusiness@wolfey.com.au. Forward or CC us on any compliance problem and we sort it out"),
         ("index.html", "Keep ServiceM8, simPRO, AroFlo, Tradify or Fergus. We work alongside what you already use"),
         ("tenders.html", "New: tender responses, written for you on a no-win, no-fee basis"),
         ("contact.html", "Canberra based"),
         ("compliance.html", "One email address, one WhatsApp number, one call a week"),
         ("compliance.html", "Every document reviewed by a person before it reaches you"),
         ("tenders.html", "We find tender opportunities online and through relationship channels"),
         ]
TICKER = "".join(f'<a href="{h}">{t}</a><span aria-hidden="true">•</span>' for h, t in TICKS)
# the second copy makes the loop seamless; it is hidden from screen readers and keyboard focus
TICKER_COPY = '<span class="ticker-copy" aria-hidden="true">' + "".join(
    f'<a href="{h}" tabindex="-1">{t}</a><span>•</span>' for h, t in TICKS) + "</span>"


def page(slug: str, title: str, desc: str, body: str, noindex: bool) -> str:
    links = "".join(f'<a href="{h}"{" class=\"on\"" if h == slug else ""}>{t}</a>' for h, t in NAV)
    robots = '<meta name="robots" content="noindex, nofollow">\n' if noindex else ""
    return f"""<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
{robots}<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="assets/compliance-poster.jpg">
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="site.css?v={VERSION}">
</head>
<body>
<div class="ticker" aria-label="Announcements"><div class="ticker-track">{TICKER}{TICKER_COPY}</div></div>
<header class="nav"><div class="wrap">
  <a class="logo" href="index.html" aria-label="Wolfey home">{MARK}wolfey</a>
  <nav class="nav-links" aria-label="Main">{links}</nav>
  <a class="btn btn-primary btn-sm" href="contact.html">Book a call</a>
  <button class="menu-btn" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
</div></header>
<main>
{body}
</main>
<footer><div class="wrap">
  <div class="foot-top">
    <a class="logo" href="index.html">{MARK}wolfey</a>
    <div class="foot-links">{"".join(f'<a href="{h}">{t}</a>' for h, t in NAV)}</div>
  </div>
  <p>Wolfey keeps compliance current and writes tender responses for mid-sized Australian construction businesses. It is a compliance administration and tender support service. We are not a law firm and do not give legal advice. Every document is reviewed by a person before it reaches you. No tender outcome is guaranteed.</p>
</div></footer>
<script src="site.js?v={VERSION}"></script>
</body>
</html>
"""


def video(src: str, poster: str, label: str, player: bool = False) -> str:
    attr = "data-player" if player else ""
    return (f'<div class="frame"><video {attr} data-auto src="assets/{src}" poster="assets/{poster}" controls muted loop playsinline '
            f'preload="metadata" aria-label="{label}"></video></div>')


CTA = """<div class="wrap"><div class="cta">
  <div><h2>Get back to the tools.</h2><p>A 20-minute call. We'll tell you plainly whether we can help.</p></div>
  <a class="btn btn-light" href="contact.html">Book a call</a>
</div></div>"""

HUMAN = """<section class="band"><div class="wrap">
  <h2>Automated, so it's affordable. <em>Checked by a person, so you can rely on it.</em></h2>
  <p class="sub">Compliance people, backed by technology. Not the other way round.</p>
  <div class="grid-2">
    <div class="card"><span class="tag">The legwork</span><h3>AI and automation</h3>
      <ul><li>Reads every document you send</li><li>Tracks every expiry date and chases renewals</li><li>Drafts your SWMS, toolbox memos and tender responses</li></ul></div>
    <div class="card hl"><span class="tag">The sign-off</span><h3>A human in the loop</h3>
      <p>A legally trained professional, experienced in construction compliance and regulation, reviews every document before it reaches you.</p></div>
  </div>
</div></section>"""

def names(*items):
    return '<div class="names">' + "".join(f"<span>{i}</span>" for i in items) + "</div>"


SOFTWARE = f"""<section class="block"><div class="wrap">
  <h2>Keep the software <em>you already use.</em></h2>
  <p class="sub">Most trade businesses already run a job app, an accounting package and a builder's portal or two. We don't replace any of them, and there's nothing to connect or install. We work alongside what you have.</p>
  <div class="grid-3">
    <div class="card"><span class="tag">Job management</span><h3>Your job app stays the source of truth</h3>
      {names("ServiceM8", "simPRO", "AroFlo", "Tradify", "Fergus")}
      <p><b>How we work with it:</b> forward or CC us the job or quote email it already sends, or send an export. We pick up the site, scope and dates from that, so nobody types a job in twice.</p></div>
    <div class="card"><span class="tag">Builder portals</span><h3>We prepare what they ask for</h3>
      {names("Cm3", "Avetta", "Rapid Global", "HammerTech", "Procore")}
      <p><b>How we work with it:</b> forward us the request. We put together the insurances, licences, SWMS and policies it needs, current and in the format asked for, ready to upload.</p></div>
    <div class="card"><span class="tag">Accounts and site apps</span><h3>Nothing changes</h3>
      {names("Xero", "MYOB", "SafetyCulture")}
      <p><b>How we work with it:</b> you keep using them as you do now. If records we need already live there, send us a copy and we work from it.</p></div>
  </div>
  <p class="terms">We are independent of these products. Names are used only to describe how we work alongside them, and belong to their owners. No integration, partnership or endorsement is implied.</p>
</div></section>"""

HOME = f"""<section class="hero"><div class="wrap">
  <p class="eyebrow">A managed back office, based in Canberra</p>
  <h1>No new software. <em>We just get on with it.</em></h1>
  <p class="lede"><strong>We keep compliance current and write tender responses for mid-sized Australian construction businesses.</strong> You don't log in to anything. Forward or CC us on a problem, send a photo, take one call a week.</p>
  <div class="cta-row"><a class="btn btn-primary" href="contact.html">Book a call</a><a class="btn btn-outline" href="pricing.html">How pricing works</a></div>
  <ul class="nos" aria-label="What you don't have to do">
    <li>No software to learn</li><li>No logins</li><li>No apps for your crew</li><li>No chasing people</li>
  </ul>
</div></section>

<section class="stage"><div class="wrap">
  <div class="tabs" role="tablist" aria-label="Choose a video">
    <button role="tab" aria-selected="true" data-video="assets/wolfey-compliance.mp4" data-poster="assets/compliance-poster.jpg" data-text="Licences, insurances, SWMS and toolbox talks, as one managed service." data-href="compliance.html" data-link="More on compliance">Compliance</button>
    <button role="tab" aria-selected="false" data-video="assets/wolfey-tenders.mp4" data-poster="assets/tenders-poster.jpg" data-text="We find the opportunities, write the response and lodge it. You pay only when you win." data-href="tenders.html" data-link="More on tenders">Tender responses</button>
  </div>
  {video("wolfey-compliance.mp4", "compliance-poster.jpg", "Wolfey explainer video", player=True)}
  <div class="stage-foot"><span data-caption>Licences, insurances, SWMS and toolbox talks, as one managed service.</span><a data-more href="compliance.html">More on compliance →</a></div>
</div></section>

<section class="block"><div class="wrap">
  <h2>You already have <em>everything you need.</em></h2>
  <p class="sub">Other providers hand you a platform and leave you to run it. We do the work. The technology is ours to operate, not yours to learn.</p>
  <div class="addr">
    <div><span class="tag">Your own address</span>
      <p class="addr-line"><b>yourbusiness</b>@wolfey.com.au</p></div>
    <p>We set up an address for your business. Owners and operators forward or CC it on any compliance problem: a builder's request, an expiring licence, a subbie's certificate, a job that might need a SWMS. We take it from there.</p>
  </div>
  <div class="grid-3" style="margin-top:24px">
    <div class="card plain"><span class="step-n">One</span><h3>Email address of your own</h3><p>Forward or CC it on anything to do with compliance, and tenders you've spotted.</p></div>
    <div class="card plain"><span class="step-n">One</span><h3>WhatsApp number</h3><p>Send a photo of a licence, or a line about Monday's job.</p></div>
    <div class="card plain"><span class="step-n">One</span><h3>Call a week</h3><p>Ten minutes on Friday. We tell you what needs doing, then we do it.</p></div>
  </div>
</div></section>

{SOFTWARE}

<section class="block"><div class="wrap">
  <h2>Two things we take <em>off your plate.</em></h2>
  <p class="sub">Each stands on its own. Together, your compliance file does half the work of every tender.</p>
  <div class="grid-2">
    <a class="card" href="compliance.html"><span class="tag">Pillar one</span><h3>Compliance, as a managed service</h3>
      <p>No software to learn and no logins. One email address, one WhatsApp number and one call a week.</p>
      <ul><li>Licences, tickets and insurances tracked and chased</li><li>A site-specific SWMS when a job needs one</li><li>Toolbox talk memos your crew sign on their phones</li></ul>
      <span class="more">See how compliance works →</span></a>
    <a class="card" href="tenders.html"><span class="tag">Pillar two</span><h3>Tender responses, no win, no fee</h3>
      <p>The bigger jobs go to tender. We find them, write the response and lodge it on time.</p>
      <ul><li>Opportunities found online and through relationships</li><li>Responses written in the buyer's format</li><li>A fee only on the bids you win</li></ul>
      <span class="more">See how tenders work →</span></a>
  </div>
</div></section>

{HUMAN}

<section class="block"><div class="wrap">
  <h2>How it works.</h2>
  <div class="grid-3">
    <div class="card plain"><span class="step-n">One</span><h3>Send us what you have</h3><p>Photos of licences and certificates, a job described in your own words, a tender you've spotted.</p></div>
    <div class="card plain"><span class="step-n">Two</span><h3>We do the work</h3><p>Our systems read, check and draft. A legally trained professional reviews the result.</p></div>
    <div class="card plain"><span class="step-n">Three</span><h3>You approve it</h3><p>You get a finished document and a short list of anything that needs you. Nothing goes out without your say.</p></div>
  </div>
</div></section>
{CTA}"""

COMPLIANCE = f"""<section class="hero"><div class="wrap">
  <p class="eyebrow"><b>Compliance</b> · a managed service</p>
  <h1>You run a construction business. <em>Not a compliance department.</em></h1>
  <p class="lede">Send us a photo, tell us the job, take one call on Friday. We keep the licensing and safety paperwork current and audit-ready.</p>
  <div class="cta-row"><a class="btn btn-primary" href="contact.html">Book a call</a><a class="btn btn-outline" href="pricing.html">How pricing works</a></div>
</div></section>
<section class="stage"><div class="wrap">
  {video("wolfey-compliance.mp4", "compliance-poster.jpg", "Wolfey compliance explainer video")}
</div></section>
<section class="block"><div class="wrap">
  <h2>What we look after.</h2>
  <div class="grid-2">
    <div class="card"><span class="tag">Always current</span><h3>Licences, tickets and insurances</h3><p>For your crew and your subcontractors. We record each one, track the expiry and chase the renewal before it lapses.</p></div>
    <div class="card"><span class="tag">Per job</span><h3>SWMS, only when you need one</h3><p>Tell us the job in your own words. We work out whether it needs a SWMS, ask only what matters, and send back a site-specific one that a person has checked.</p></div>
    <div class="card"><span class="tag">On site</span><h3>Toolbox talk memos</h3><p>A short, plain-English memo for each job on what to watch for. It goes to every worker's phone and they tap to sign. You keep the record.</p></div>
    <div class="card"><span class="tag">Every week</span><h3>One call on Friday</h3><p>Ten minutes. What's expired, what's due, what we need from you, and next week's jobs taken off your hands.</p></div>
  </div>
</div></section>
{HUMAN}
{SOFTWARE}
<section class="block"><div class="wrap">
  <h2>No new software. <em>No logins.</em></h2>
  <p class="sub">The technology is ours to run. You deal with people, through the channels you already use.</p>
  <div class="addr">
    <div><span class="tag">Your own address</span>
      <p class="addr-line"><b>yourbusiness</b>@wolfey.com.au</p></div>
    <p>We set up an address for your business. Owners and operators forward or CC it on any compliance problem: a builder's request, an expiring licence, a subbie's certificate, a job that might need a SWMS. We take it from there.</p>
  </div>
  <div class="grid-3" style="margin-top:24px">
    <div class="card plain"><span class="step-n">One</span><h3>Email address of your own</h3><p>Forward or CC it on any compliance problem and we sort it out.</p></div>
    <div class="card plain"><span class="step-n">One</span><h3>WhatsApp number</h3><p>For photos, quick questions and "job on Monday".</p></div>
    <div class="card plain"><span class="step-n">One</span><h3>Call a week</h3><p>So you always know where you stand.</p></div>
  </div>
</div></section>
{CTA}"""

TENDERS = f"""<section class="hero"><div class="wrap">
  <p class="eyebrow"><b>Tender responses</b> · no win, no fee</p>
  <h1>The bigger jobs go to tender. <em>We'll write yours.</em></h1>
  <p class="lede">We find the opportunities, write the response and lodge it on time. You pay a percentage of the bids you win, and nothing on the ones you don't.</p>
  <div class="cta-row"><a class="btn btn-primary" href="contact.html">Book a call</a><a class="btn btn-outline" href="pricing.html">How pricing works</a></div>
</div></section>
<section class="stage"><div class="wrap">
  {video("wolfey-tenders.mp4", "tenders-poster.jpg", "Wolfey tender responses explainer video")}
</div></section>
<section class="block"><div class="wrap">
  <h2>From spotting it <em>to lodging it.</em></h2>
  <div class="grid-2">
    <div class="card"><span class="tag">Find</span><h3>We find the work</h3><p>We watch the online tender portals and work our relationship channels with builders and agencies, then bring you the opportunities that fit your trade and region. You choose which to chase.</p></div>
    <div class="card"><span class="tag">Write</span><h3>We write the response</h3><p>Schedules, methodology, capability statements and referees, drafted in the buyer's format. You set the price. We do the rest.</p></div>
    <div class="card"><span class="tag">Reuse</span><h3>Your compliance file does half of it</h3><p>Licences, insurances and safety evidence come straight from the file we already keep for you, current and complete.</p></div>
    <div class="card"><span class="tag">Lodge</span><h3>You approve, we lodge</h3><p>A person reviews every response before you see it. Nothing is lodged without your sign-off, and it goes in complete and on time.</p></div>
  </div>
</div></section>
<section class="band"><div class="wrap">
  <h2>No win, <em>no fee.</em></h2>
  <p class="sub">We back our work. That only makes sense if we chase the right opportunities together over time, so tender support runs on a six-month agreement.</p>
  <div class="grid-2">
    <div class="card hl"><span class="tag">You win the bid</span><h3>A percentage of the contract you've won</h3><p>Agreed up front, before we write a word.</p></div>
    <div class="card"><span class="tag">You don't</span><h3>Nothing for the response we wrote</h3><p>The risk on each bid is ours.</p></div>
  </div>
</div></section>
{CTA}"""

PRICING = f"""<section class="hero"><div class="wrap">
  <p class="eyebrow"><b>Pricing</b></p>
  <h1>Priced to give you <em>time back and peace of mind.</em></h1>
  <p class="lede">Two simple arrangements. Both are designed to do more than save you time: confidence that your compliance is in order, and a better win rate on the bigger work that goes to tender.</p>
</div></section>
<section class="block"><div class="wrap">
  <div class="grid-2" style="margin-top:0">
    <div class="card"><span class="tag">Compliance</span>
      <p class="price">Subscription<small>A support arrangement, billed monthly</small></p>
      <p>Ongoing support for a fixed monthly fee, set by the size of your business and what you need.</p>
      <ul><li>Licence, ticket and insurance register, kept current</li><li>Expiry tracking and chasing</li><li>SWMS and toolbox talk memos as jobs need them</li><li>A call every Friday</li></ul>
      <a class="more" href="contact.html">Ask for a quote →</a></div>
    <div class="card"><span class="tag">Tender responses</span>
      <p class="price">No win, no fee<small>A percentage of the bids you win</small></p>
      <p>You pay only when a bid we wrote is successful. Requires signing up for six months of bid support.</p>
      <ul><li>Opportunities found online and through relationship channels</li><li>Responses written, reviewed and lodged</li><li>Nothing to pay on unsuccessful bids</li><li>Six-month bid support agreement</li></ul>
      <a class="more" href="contact.html">Talk to us about tenders →</a></div>
  </div>
  <p class="terms">Fees and percentages are agreed in writing before work starts. No tender outcome is guaranteed. The six-month bid support agreement sets out which opportunities are covered and how a successful bid is defined.</p>
</div></section>
<section class="block"><div class="wrap">
  <h2>Common questions.</h2>
  <div style="margin-top:40px">
    <details><summary>Do I need both services?</summary><p>No. Each stands on its own. They work best together, because the compliance file we keep for you supplies the licences, insurances and safety evidence every tender asks for.</p></details>
    <details><summary>Why six months for tender support?</summary><p>Winning tendered work takes more than one bid. Six months lets us learn your business, build a pipeline of the right opportunities and improve each response on the last.</p></details>
    <details><summary>Do you guarantee we'll win?</summary><p>No, and nobody honestly can. What we do is make sure you bid on the right opportunities with complete, well-written responses lodged on time. If a bid doesn't win, you don't pay for it.</p></details>
    <details><summary>Who actually reviews our documents?</summary><p>A legally trained professional with construction compliance experience reviews every document before it reaches you. Our systems do the reading, tracking and drafting, which is what keeps the service affordable.</p></details>
    <details><summary>Is this legal advice?</summary><p>No. Wolfey is a compliance administration and tender support service. Where something needs legal advice, we'll tell you.</p></details>
  </div>
</div></section>
{CTA}"""

CONTACT = f"""<section class="hero"><div class="wrap">
  <p class="eyebrow"><b>Contact</b></p>
  <h1>Book a call. <em>Twenty minutes.</em></h1>
  <p class="lede">Tell us your trade, your crew size and what's taking up your time. We'll tell you plainly whether we can help and what it would cost.</p>
  <p class="contact-line" style="margin-top:36px"><a href="mailto:{EMAIL}">{EMAIL}</a></p>
  <p class="note">Email us with a good time to call and a phone number.</p>
</div></section>
<section class="block"><div class="wrap">
  <h2>Canberra based. <em>Qualified people.</em></h2>
  <p class="sub">We're a Canberra business working with trade and construction companies across the ACT and surrounding NSW.</p>
  <div class="grid-2">
    <div class="card"><span class="tag">Legal</span><h3>A legally trained professional, admitted in the ACT</h3><p>Every document is reviewed by someone with legal training and hands-on experience in construction compliance.</p></div>
    <div class="card"><span class="tag">Finance</span><h3>A Chartered Accountant on staff</h3><p>Commercial and financial experience behind your tender pricing schedules and the business side of compliance.</p></div>
  </div>
</div></section>
<section class="block"><div class="wrap">
  <h2>What happens next.</h2>
  <div class="grid-3">
    <div class="card plain"><span class="step-n">One</span><h3>A short call</h3><p>We ask about your work, your crew and where the paperwork hurts.</p></div>
    <div class="card plain"><span class="step-n">Two</span><h3>A plain proposal</h3><p>What we'd take on, what we'd need from you, and the fee.</p></div>
    <div class="card plain"><span class="step-n">Three</span><h3>We get started</h3><p>Send us your staff list and documents. We do the rest.</p></div>
  </div>
</div></section>"""

PAGES = {
    "index.html": ("Wolfey | No new software. We just get on with it.",
                   "We keep compliance current and write tender responses for mid-sized Australian construction businesses. No new software and no logins.", HOME),
    "compliance.html": ("Compliance as a managed service | Wolfey",
                        "Licences, insurances, SWMS and toolbox talks handled for trade businesses. One email, one WhatsApp number, one call a week.", COMPLIANCE),
    "tenders.html": ("Tender responses, no win no fee | Wolfey",
                     "We find tender opportunities, write the response and lodge it. You pay a percentage of the bids you win.", TENDERS),
    "pricing.html": ("Pricing | Wolfey", "Compliance is a subscription support arrangement. Tender responses are a percentage of winning bids on a six-month bid support agreement.", PRICING),
    "contact.html": ("Contact | Wolfey", "Book a 20-minute call with Wolfey.", CONTACT),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "dist")
    ap.add_argument("--noindex", action="store_true", help="mark pages noindex (for a preview site)")
    a = ap.parse_args()
    out = a.out.resolve()
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "fonts").mkdir(exist_ok=True)
    for slug, (title, desc, body) in PAGES.items():
        (out / slug).write_text(page(slug, title, desc, body, a.noindex), encoding="utf-8")
    for f in ("site.css", "site.js"):
        shutil.copy(HERE / f, out / f)
    shutil.copy(VIDEO / "inter-latin-wght-normal.woff2", out / "fonts" / "inter-latin-wght-normal.woff2")
    for f in ("wolfey-compliance.mp4", "wolfey-tenders.mp4", "compliance-poster.jpg", "tenders-poster.jpg"):
        shutil.copy(VIDEO / f, out / "assets" / f)
    print(f"Site written to {out} ({len(PAGES)} pages)")


if __name__ == "__main__":
    main()
