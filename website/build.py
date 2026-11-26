"""Build the Wolf marketing site (static, five pages) into website/dist/ or --out.

    python website/build.py [--out DIR] [--noindex]

Pages share one header and footer. The two videos in marketing/video/ are the centrepiece.
All links are relative, so the site works at any path (a domain root or a GitHub Pages subfolder).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VIDEO = ROOT / "marketing" / "video"
EMAIL = "hello@wolf.com.au"   # placeholder until the mailbox exists
YEAR = datetime.date.today().year
MEDIA = ("wolf-compliance.mp4", "wolf-tenders.mp4", "compliance-poster.jpg", "tenders-poster.jpg")


def _mv(name: str) -> str:
    """Short content hash of a media file, so browsers fetch a re-rendered video instead of a cached one."""
    return hashlib.sha256((VIDEO / name).read_bytes()).hexdigest()[:8]


# Short hash of the stylesheet and script. It goes on their URLs, so a browser never pairs new pages with an old cached copy.
VERSION = hashlib.sha256((HERE / "site.css").read_bytes() + (HERE / "site.js").read_bytes()).hexdigest()[:10]

# The Wolf mark: a blue shield with wolf ears.
MARK_PATH = "M3.5 3.2 9 7.6 12 6l3 1.6 5.5-4.4v10C20.5 18.6 16.6 21.4 12 22.6 7.4 21.4 3.5 18.6 3.5 13.2z"
MARK_INNER = f'<path d="{MARK_PATH}" fill="#0b5cff" stroke="#0b5cff" stroke-width="1.6" stroke-linejoin="round"/>'
MARK = f'<span class="logo-mark"><svg viewBox="0 0 24 24" aria-hidden="true">{MARK_INNER}</svg></span>'
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='" + MARK_PATH
           + "' fill='%230b5cff' stroke='%230b5cff' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E")
NAV = [("compliance.html", "Compliance"), ("tenders.html", "Tenders"), ("pricing.html", "Pricing"), ("contact.html", "Contact")]

# Line icons, 24 x 24, drawn as strokes (see .i in site.css).
ICONS = {
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "filecheck": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="m9 15 2 2 4-4"/>',
    "filetext": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
    "clipboard": '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="m9 14 2 2 4-4"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "pen": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "usercheck": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "award": '<circle cx="12" cy="8" r="6"/><path d="M8.2 13.2 7 22l5-3 5 3-1.2-8.8"/>',
    "briefcase": '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    "chart": '<path d="M12 20V10M18 20V4M6 20v-4"/>',
    "scale": '<path d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z"/>',
    "hardhat": '<path d="M2 18a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1z"/><path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"/><path d="M4 15v-3a6 6 0 0 1 6-6M14 6a6 6 0 0 1 6 6v3"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94z"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/>',
    "volumex": '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m23 9-6 6M17 9l6 6"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
}


def icon(name: str) -> str:
    return f'<svg class="i" viewBox="0 0 24 24" aria-hidden="true">{ICONS[name]}</svg>'


ARROW = icon("arrow")

TICKS = [("index.html", "No new software. No logins. We just get on with it."),
         ("compliance.html", "Your own address: yourbusiness@wolf.com.au. Forward or CC us on any compliance problem and we sort it out"),
         ("index.html", "Keep ServiceM8, simPRO, AroFlo, Tradify or Fergus. We work alongside what you already use"),
         ("tenders.html", "New: tender responses, written for you on a no-win, no-fee basis"),
         ("contact.html", "Canberra based"),
         ("compliance.html", "We check in weekly to help, not hinder"),
         ("compliance.html", "One email address, one WhatsApp number, one check-in phone call a week"),
         ("compliance.html", "Every document reviewed by a person before it reaches you"),
         ("tenders.html", "We find tender opportunities online and through relationship channels"),
         ]
TICKER = "".join(f'<a href="{h}">{t}</a><span aria-hidden="true">•</span>' for h, t in TICKS)
# the second copy makes the loop seamless; it is hidden from screen readers and keyboard focus
TICKER_COPY = '<span class="ticker-copy" aria-hidden="true">' + "".join(
    f'<a href="{h}" tabindex="-1">{t}</a><span>•</span>' for h, t in TICKS) + "</span>"


def page(slug: str, title: str, desc: str, body: str, noindex: bool) -> str:
    links = "".join(f'<a href="{h}"{" class=\"on\" aria-current=\"page\"" if h == slug else ""}>{t}</a>' for h, t in NAV)
    robots = '<meta name="robots" content="noindex, nofollow">\n' if noindex else ""
    return f"""<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
{robots}<meta name="theme-color" content="#0b5cff">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="assets/compliance-poster.jpg">
<link rel="icon" href="{FAVICON}">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="preload" href="fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="site.css?v={VERSION}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="ticker" aria-label="Announcements"><div class="ticker-track">{TICKER}{TICKER_COPY}</div></div>
<header class="nav"><div class="wrap">
  <a class="logo" href="index.html" aria-label="Wolf home">{MARK}Wolf</a>
  <nav class="nav-links" aria-label="Main">{links}</nav>
  <a class="btn btn-primary btn-sm" href="contact.html">Book a call{ARROW}</a>
  <button class="menu-btn" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="l1" d="M4 7h16"/><path class="l2" d="M4 12h16"/><path class="l3" d="M4 17h16"/></svg></button>
</div></header>
<main id="main">
{body}
</main>
<footer><div class="wrap">
  <div class="foot-grid">
    <div class="foot-brand"><a class="logo" href="index.html">{MARK}Wolf</a>
      <p>Compliance kept current and tender responses written for mid-sized Australian construction businesses.</p></div>
    <div class="foot-col"><h4>Services</h4><a href="compliance.html">Compliance</a><a href="tenders.html">Tender responses</a></div>
    <div class="foot-col"><h4>Company</h4><a href="pricing.html">Pricing</a><a href="pricing.html#questions">Common questions</a><a href="contact.html">Contact</a></div>
    <div class="foot-col"><h4>Get in touch</h4><a href="mailto:{EMAIL}">{EMAIL}</a><span>Canberra, ACT</span></div>
  </div>
  <div class="foot-base"><p>© {YEAR} Wolf</p>
    <p>Wolf is a compliance administration and tender support service. We are not a law firm and do not give legal advice. Every document is reviewed by a person before it reaches you. No tender outcome is guaranteed.</p></div>
</div></footer>
<script src="site.js?v={VERSION}"></script>
</body>
</html>
"""


# ---- shared pieces ----------------------------------------------------------------------------------------------

def video(src: str, poster: str, label: str, player: bool = False) -> str:
    attr = " data-player" if player else ""
    return (f'<div class="frame-wrap"><div class="frame"><video{attr} data-auto src="assets/{src}" poster="assets/{poster}" controls muted loop '
            f'playsinline preload="metadata" aria-label="{label}"></video></div></div>')


def names(*items: str) -> str:
    """Chips. An item that starts with * is drawn in blue."""
    return '<div class="names">' + "".join(
        f'<span class="key">{i[1:]}</span>' if i.startswith("*") else f"<span>{i}</span>" for i in items) + "</div>"


def top(ic: str, tag: str) -> str:
    return f'<div class="card-top"><span class="card-ic">{icon(ic)}</span><span class="tag">{tag}</span></div>'


def steps(*items: tuple[str, str]) -> str:
    return '<div class="steps">' + "".join(
        f'<div class="step"><span class="step-dot" aria-hidden="true">{n}</span><div><h3>{t}</h3><p>{p}</p></div></div>'
        for n, (t, p) in enumerate(items, 1)) + "</div>"


def ones(mail: str, chat: str, call: str) -> str:
    items = [("Email address of your own", mail), ("WhatsApp number", chat), ("Check-in phone call a week", call)]
    return '<div class="ones">' + "".join(
        f'<div class="one"><span class="one-n" aria-hidden="true">1</span><div><h3><span class="sr">One </span>{t}</h3><p>{p}</p></div></div>'
        for t, p in items) + "</div>"


SUBJECTS = ["Fwd: SWMS needed by Friday", "Fwd: Cm3 prequalification is due", "Fwd: Insurance certificate request",
            "Fwd: New starter on Monday", "Fwd: Tender closes in two weeks"]
ADDR = f"""<div class="addr">
    <div class="addr-mail">
      <div class="addr-bar">{icon("mail")}<span>New message</span><span class="pill">Forward or CC</span></div>
      <div class="addr-row"><span>To</span><p class="addr-line"><b>yourbusiness</b>@wolf.com.au</p></div>
      <div class="addr-row"><span>Subject</span><p class="addr-subj"><span data-type="{escape(json.dumps(SUBJECTS), quote=True)}">{SUBJECTS[0]}</span><i class="caret" aria-hidden="true"></i></p></div>
    </div>
    <div class="addr-copy"><span class="tag">Your own address</span>
      <h3>Forward it. We take it from there.</h3>
      <p>We set up an address for your business. Owners and operators forward or CC it on any compliance problem: a builder's request, an expiring licence, a subbie's certificate, a job that might need a SWMS.</p></div>
  </div>"""

CTA = f"""<div class="wrap"><div class="cta">
  <div><h2>Get back to the tools.</h2><p>A 20-minute call. We'll tell you plainly whether we can help.</p></div>
  <a class="btn btn-light" href="contact.html">Book a call{ARROW}</a>
</div></div>"""

HUMAN = f"""<section class="band"><div class="wrap">
  <p class="kicker">A person in the loop</p>
  <h2>Automated, so it's affordable. <em>Checked by a person, so you can rely on it.</em></h2>
  <p class="sub">Compliance people, backed by technology. Not the other way round.</p>
  <div class="flow">
    <div class="card">{top("cpu", "The legwork")}<h3>AI and automation</h3>
      <ul><li>Reads every document you send</li><li>Tracks every expiry date and chases renewals</li><li>Drafts your SWMS, toolbox memos and tender responses</li></ul></div>
    <div class="flow-link" aria-hidden="true"><span>{ARROW}</span></div>
    <div class="card hl">{top("usercheck", "The sign-off")}<h3>A human in the loop</h3>
      <p>A legally trained professional, experienced in construction compliance and regulation, reviews every document before it reaches you.</p></div>
  </div>
</div></section>"""

SOFTWARE = f"""<section class="block"><div class="wrap">
  <p class="kicker">Works with what you have</p>
  <h2>Keep the software <em>you already use.</em></h2>
  <p class="sub">Most trade businesses already run a job app, an accounting package and a builder's portal or two. We don't replace any of them, and there's nothing to connect or install. We work alongside what you have.</p>
  <div class="grid-3 rows-4">
    <div class="card">{top("wrench", "Job management")}<h3>Your job app stays the source of truth</h3>
      {names("ServiceM8", "simPRO", "AroFlo", "Tradify", "Fergus")}
      <p><b>How we work with it:</b> forward or CC us the job or quote email it already sends, or send an export. We pick up the site, scope and dates from that, so nobody types a job in twice.</p></div>
    <div class="card">{top("building", "Builder portals")}<h3>We prepare what they ask for</h3>
      {names("Cm3", "Avetta", "Rapid Global", "HammerTech", "Procore")}
      <p><b>How we work with it:</b> forward us the request. We put together the insurances, licences, SWMS and policies it needs, current and in the format asked for, ready to upload.</p></div>
    <div class="card">{top("chart", "Accounts and site apps")}<h3>Nothing changes</h3>
      {names("Xero", "MYOB", "SafetyCulture")}
      <p><b>How we work with it:</b> you keep using them as you do now. If records we need already live there, send us a copy and we work from it.</p></div>
  </div>
  <p class="terms">We are independent of these products. Names are used only to describe how we work alongside them, and belong to their owners. No integration, partnership or endorsement is implied.</p>
</div></section>"""

PAPERWORK = f"""<section class="block alt"><div class="wrap">
  <p class="kicker">What we handle</p>
  <h2>The paperwork <em>you'll recognise.</em></h2>
  <p class="sub">Builders, principals and tender panels keep asking for the same documents under slightly different names. These are the ones we prepare, track and keep current.</p>
  <div class="grid-2">
    <div class="card">{top("shield", "Compliance, on site and on file")}<h3>What builders and regulators ask you for</h3>
      {names("*Safe Work Method Statements (SWMS)", "White Cards", "Site inductions", "Trade licences", "High risk work licences", "Certificates of currency", "Workers compensation", "Public liability", "Subcontractor statements", "Prequalification (Cm3, Avetta, Rapid Global)", "Toolbox talk records", "Plant and equipment registers", "Test and tag records", "Safety Data Sheets (SDS)", "Hazardous chemicals register", "Asbestos and silica awareness training", "First aid certificates", "Incident and hazard reports", "Emergency plans")}
      <p class="fine">A SWMS is only needed for high risk construction work. We check each job first, and only write one when the job calls for it.</p></div>
    <div class="card">{top("filetext", "Tenders, the returnable schedules")}<h3>What goes in with the bid</h3>
      {names("*Tender form and returnable schedules", "Capability statement", "Construction methodology", "Construction program", "Key personnel and CVs", "Relevant experience and referees", "Risk management plan", "Risk register", "WHS management plan", "Quality management plan", "Inspection and Test Plans (ITPs)", "Construction Environmental Management Plan (CEMP)", "Traffic management plan", "Insurance certificates of currency", "Financial capacity statement", "Statement of departures", "Conflict of interest declaration", "Statutory declarations", "Modern slavery questionnaire", "Indigenous participation plan", "Local industry participation plan", "Secure Local Jobs Code certificate (ACT)", "Government prequalification")}
      <p class="fine">Pricing stays yours. We format the schedules around your numbers.</p></div>
  </div>
  <p class="fine" style="margin-top:20px">What applies to you depends on the work, the state or territory and the contract. We tell you which ones you need, and which you don't. This is an administration service, not legal advice.</p>
</div></section>"""

# ---- hero illustrations (decorative, hidden from screen readers; the same facts are in the copy) -----------------

MOCK_MAIL = f"""<div class="mock">
      <div class="mock-head"><span class="mock-ic">{icon("mail")}</span><div>Forwarded email<small>From you, whenever it lands</small></div><span class="pill live">On it</span></div>
      <div class="mock-row"><span>To</span><span><b>yourbusiness</b>@wolf.com.au</span></div>
      <div class="mock-row"><span>Subject</span><span>Fwd: Builder needs our SWMS and insurances by Friday</span></div>
    </div>"""
MOCK_CHAT = f"""<div class="mock">
      <div class="mock-head"><span class="mock-ic g">{icon("message")}</span><div>WhatsApp<small>A photo is enough</small></div></div>
      <div class="chat"><span class="bub me">{icon("image")}Sam's new gas licence</span><span class="bub us">Got it. Recorded, expires 19 Dec 2027.</span></div>
    </div>"""
MOCK_CALL = f"""<div class="mock">
      <div class="mock-head"><span class="mock-ic">{icon("phone")}</span><div>Friday check-in<small>Ten minutes, once a week</small></div></div>
      <div class="mock-list"><div><i class="dot r"></i>1 expired: first aid, Sam</div><div><i class="dot"></i>2 due in the next 30 days</div><div><i class="dot g"></i>3 jobs next week, 2 need a SWMS</div></div>
    </div>"""
MOCK_SWMS = f"""<div class="mock">
      <div class="mock-head"><span class="mock-ic">{icon("filecheck")}</span><div>SWMS, bathroom renovation<small>Checked by a person</small></div><span class="pill g">Ready</span></div>
    </div>"""
MOCK_OPPS = f"""<div class="mock">
      <div class="mock-head"><span class="mock-ic">{icon("search")}</span><div>Opportunities this week<small>Matched to your trade and region</small></div></div>
      <div class="mock-list">
        <div><div>Stormwater renewal program<small>Local council, closes 12 Dec</small></div><span class="pill g">Strong fit</span></div>
        <div><div>Hydraulics package, school upgrade<small>Head contractor, closes 9 Dec</small></div><span class="pill">Good fit</span></div>
      </div>
    </div>"""
_T = f'<span class="tickc">{icon("check")}</span>'
MOCK_BID = f"""<div class="mock">
      <div class="mock-head"><span class="mock-ic">{icon("filetext")}</span><div>Tender response<small>Stormwater renewal program</small></div></div>
      <div class="mock-list">
        <div>{_T}Licences and insurances<span class="pill g">From your file</span></div>
        <div>{_T}Methodology and program<span class="pill">Drafted</span></div>
        <div>{_T}Capability and referees<span class="pill">Drafted</span></div>
        <div><span class="tickc b">$</span>Pricing schedule<span class="pill n">Yours</span></div>
      </div>
    </div>"""


def art(*mocks: str) -> str:
    return '<div class="channels" aria-hidden="true">\n    ' + "\n    ".join(mocks) + "\n  </div>"


# ---- pages ------------------------------------------------------------------------------------------------------

HOME = f"""<section class="hero"><div class="wrap hero-cols">
  <div class="hero-copy">
    <p class="eyebrow eyebrow-lead"><span class="for">{icon("hardhat")}For construction businesses</span> Compliance and tender responses, done for you from Canberra</p>
    <h1>No new software. <em>We just get on with it.</em></h1>
    <p class="lede"><strong>We keep compliance current and write tender responses for mid-sized Australian construction businesses.</strong> You don't log in to anything. Forward or CC us on a problem, send a photo, take one check-in phone call a week.</p>
    <div class="cta-row"><a class="btn btn-primary" href="contact.html">Book a call{ARROW}</a><a class="btn btn-outline" href="pricing.html">How pricing works</a></div>
    <ul class="nos" aria-label="What you don't have to do">
      <li>No software to learn</li><li>No logins</li><li>No apps for your crew</li><li>No chasing people</li>
    </ul>
  </div>
  {art(MOCK_MAIL, MOCK_CHAT, MOCK_CALL)}
</div></section>

<section class="stage"><div class="wrap">
  <div class="stage-head">
    <div class="seg" role="tablist" aria-label="Choose a video">
      <button role="tab" aria-selected="true" data-video="assets/wolf-compliance.mp4" data-poster="assets/compliance-poster.jpg" data-text="Licences, insurances, SWMS and toolbox talks, as one managed service." data-href="compliance.html" data-link="More on compliance">Compliance <small>1:21</small></button>
      <button role="tab" aria-selected="false" tabindex="-1" data-video="assets/wolf-tenders.mp4" data-poster="assets/tenders-poster.jpg" data-text="We find the opportunities, write the response and lodge it. You pay only when you win." data-href="tenders.html" data-link="More on tenders">Tender responses <small>1:12</small></button>
    </div>
    <span class="stage-hint">{icon("volumex")}Plays without sound</span>
  </div>
  {video("wolf-compliance.mp4", "compliance-poster.jpg", "Wolf explainer video", player=True)}
  <div class="stage-foot"><span data-caption>Licences, insurances, SWMS and toolbox talks, as one managed service.</span><a class="link" data-more href="compliance.html"><span data-more-text>More on compliance</span>{ARROW}</a></div>
  <div class="trust">
    <div>{icon("pin")}<p><b>Canberra based</b><span>Working across the ACT and NSW</span></p></div>
    <div>{icon("usercheck")}<p><b>A person checks everything</b><span>Before it reaches you</span></p></div>
    <div>{icon("phone")}<p><b>One check-in call a week</b><span>Ten minutes on Friday</span></p></div>
    <div>{icon("award")}<p><b>No win, no fee</b><span>On tender responses</span></p></div>
  </div>
</div></section>

<section class="block"><div class="wrap">
  <p class="kicker">How you reach us</p>
  <h2>You already have <em>everything you need.</em></h2>
  <p class="sub">Other providers hand you a platform and leave you to run it. We do the work. The technology is ours to operate, not yours to learn.</p>
  {ADDR}
  {ones("Forward or CC it on anything to do with compliance, and tenders you've spotted.",
        "Send a photo of a licence, or a line about Monday's job.",
        "We check in weekly to help, not hinder. Ten minutes on Friday: what needs doing, then we do it.")}
</div></section>

{PAPERWORK}

{SOFTWARE}

<section class="block"><div class="wrap">
  <p class="kicker">The two pillars</p>
  <h2>Two things we take <em>off your plate.</em></h2>
  <p class="sub">Each stands on its own. Together, your compliance file does half the work of every tender.</p>
  <div class="grid-2">
    <a class="card" href="compliance.html">{top("shield", "Pillar one")}<h3>Compliance, as a managed service</h3>
      <p>No software to learn and no logins. One email address, one WhatsApp number and one check-in phone call a week.</p>
      <ul><li>Licences, tickets and insurances tracked and chased</li><li>A site-specific SWMS when a job needs one</li><li>Toolbox talk memos your crew sign on their phones</li></ul>
      <span class="link">See how compliance works{ARROW}</span></a>
    <a class="card" href="tenders.html">{top("award", "Pillar two")}<h3>Tender responses, no win, no fee</h3>
      <p>The bigger jobs go to tender. We find them, write the response and lodge it on time.</p>
      <ul><li>Opportunities found online and through relationships</li><li>Responses written in the buyer's format</li><li>A fee only on the bids you win</li></ul>
      <span class="link">See how tenders work{ARROW}</span></a>
  </div>
</div></section>

{HUMAN}

<section class="block"><div class="wrap">
  <p class="kicker">The process</p>
  <h2>How it works.</h2>
  {steps(("Send us what you have", "Photos of licences and certificates, a job described in your own words, a tender you've spotted."),
         ("We do the work", "Our systems read, check and draft. A legally trained professional reviews the result."),
         ("You approve it", "You get a finished document and a short list of anything that needs you. Nothing goes out without your say."))}
</div></section>
{CTA}"""

COMPLIANCE = f"""<section class="hero"><div class="wrap hero-cols">
  <div class="hero-copy">
    <p class="eyebrow"><b>Compliance</b> · a managed service</p>
    <h1 class="long">You run a construction business. <em>Not a compliance department.</em></h1>
    <p class="lede">Send us a photo, tell us the job, take one check-in phone call a week. We keep the licensing and safety paperwork current and audit-ready.</p>
    <div class="cta-row"><a class="btn btn-primary" href="contact.html">Book a call{ARROW}</a><a class="btn btn-outline" href="pricing.html">How pricing works</a></div>
  </div>
  {art(MOCK_CHAT, MOCK_SWMS, MOCK_CALL)}
</div></section>
<section class="stage"><div class="wrap">
  {video("wolf-compliance.mp4", "compliance-poster.jpg", "Wolf compliance explainer video")}
</div></section>
<section class="block"><div class="wrap">
  <p class="kicker">The service</p>
  <h2>What we look after.</h2>
  <div class="grid-2">
    <div class="card">{top("shield", "Always current")}<h3>Licences, tickets and insurances</h3><p>For your crew and your subcontractors. We record each one, track the expiry and chase the renewal before it lapses.</p></div>
    <div class="card">{top("filecheck", "Per job")}<h3>SWMS, only when you need one</h3><p>Tell us the job in your own words. We work out whether it needs a SWMS, ask only what matters, and send back a site-specific one that a person has checked.</p></div>
    <div class="card">{top("hardhat", "On site")}<h3>Toolbox talk memos</h3><p>A short, plain-English memo for each job on what to watch for. It goes to every worker's phone and they tap to sign. You keep the record.</p></div>
    <div class="card">{top("phone", "Every week")}<h3>A weekly check-in, to help not hinder</h3><p>Ten minutes on Friday. What's expired, what's due, what we need from you, and next week's jobs taken off your hands. No audits, no lectures.</p></div>
  </div>
</div></section>
{HUMAN}
{SOFTWARE}
<section class="block"><div class="wrap">
  <p class="kicker">How you reach us</p>
  <h2>No new software. <em>No logins.</em></h2>
  <p class="sub">The technology is ours to run. You deal with people, through the channels you already use.</p>
  {ADDR}
  {ones("Forward or CC it on any compliance problem and we sort it out.",
        'For photos, quick questions and "job on Monday".',
        "We check in weekly to help, not hinder. You always know where you stand.")}
</div></section>
{CTA}"""

TENDERS = f"""<section class="hero"><div class="wrap hero-cols">
  <div class="hero-copy">
    <p class="eyebrow"><b>Tender responses</b> · no win, no fee</p>
    <h1>The bigger jobs go to tender. <em>We'll write yours.</em></h1>
    <p class="lede">We find the opportunities, write the response and lodge it on time. You pay a percentage of the bids you win, and nothing on the ones you don't.</p>
    <div class="cta-row"><a class="btn btn-primary" href="contact.html">Book a call{ARROW}</a><a class="btn btn-outline" href="pricing.html">How pricing works</a></div>
  </div>
  {art(MOCK_OPPS, MOCK_BID)}
</div></section>
<section class="stage"><div class="wrap">
  {video("wolf-tenders.mp4", "tenders-poster.jpg", "Wolf tender responses explainer video")}
</div></section>
<section class="block"><div class="wrap">
  <p class="kicker">The process</p>
  <h2>From spotting it <em>to lodging it.</em></h2>
  <div class="grid-2">
    <div class="card">{top("search", "Find")}<h3>We find the work</h3><p>We watch the online tender portals and work our relationship channels with builders and agencies, then bring you the opportunities that fit your trade and region. You choose which to chase.</p></div>
    <div class="card">{top("pen", "Write")}<h3>We write the response</h3><p>Schedules, methodology, capability statements and referees, drafted in the buyer's format. You set the price. We do the rest.</p></div>
    <div class="card">{top("layers", "Reuse")}<h3>Your compliance file does half of it</h3><p>Licences, insurances and safety evidence come straight from the file we already keep for you, current and complete.</p></div>
    <div class="card">{top("send", "Lodge")}<h3>You approve, we lodge</h3><p>A person reviews every response before you see it. Nothing is lodged without your sign-off, and it goes in complete and on time.</p></div>
  </div>
</div></section>
<section class="band"><div class="wrap">
  <p class="kicker">The fee</p>
  <h2>No win, <em>no fee.</em></h2>
  <p class="sub">We back our work. That only makes sense if we chase the right opportunities together over time, so tender support runs on a six-month agreement.</p>
  <div class="grid-2">
    <div class="card hl"><span class="tag">You win the bid</span><p class="big">A percentage</p><h3>of the contract you've won</h3><p>Agreed up front, before we write a word.</p></div>
    <div class="card"><span class="tag">You don't</span><p class="big">Nothing</p><h3>for the response we wrote</h3><p>The risk on each bid is ours.</p></div>
  </div>
</div></section>
{CTA}"""


def qa(*pairs: tuple[str, str]) -> str:
    return "".join(f"<details><summary>{q}</summary><p>{a}</p></details>\n      " for q, a in pairs)


def group(title: str, *pairs: tuple[str, str]) -> str:
    return f'<div class="faq-group"><h3>{title} <span>{len(pairs)}</span></h3><div>\n      {qa(*pairs)}</div></div>'


FAQ = "\n    ".join([
    group("Getting started",
          ("Do we have to install or learn anything?", "No. There's no app, no login and nothing for your crew to download. You get an email address and a WhatsApp number, and one check-in phone call a week."),
          ("How do we get started?", "Book a call. We set up your address and WhatsApp number, you send us what you already have, such as licences, tickets and insurance certificates, and we build your register from that. Photos and forwarded emails are fine."),
          ("What does my crew have to do?", "Very little. Send a photo of a new ticket or licence when we ask, and tap to sign a toolbox talk memo on their phone. No accounts and no training."),
          ("What if something comes up before the weekly call?", "Send it straight away by email or WhatsApp. The weekly call is the check-in, not the only time you can reach us."),
          ("Do I need both services?", "No. Each stands on its own. They work best together, because the compliance file we keep for you supplies the licences, insurances and safety evidence every tender asks for.")),
    group("Compliance",
          ("Do we need a SWMS for every job?", "No. A Safe Work Method Statement is only required for high risk construction work. We check each job first and tell you why one is or isn't needed, then prepare it when it is."),
          ("Who is responsible for safety on site?", "You are. Your work health and safety duties stay with your business. We take on the paperwork and administration that sits behind them, and keep it current."),
          ("How is compliance priced?", "As a fixed monthly subscription that depends on the size of your crew and how many subcontractors you use. We quote it after a short call, so you know the cost before you start.")),
    group("Tenders",
          ("Why six months for tender support?", "Winning tendered work takes more than one bid. Six months lets us learn your business, build a pipeline of the right opportunities and improve each response on the last."),
          ("Do you guarantee we'll win?", "No, and nobody honestly can. What we do is make sure you bid on the right opportunities with complete, well-written responses lodged on time. If a bid doesn't win, you don't pay for it."),
          ("What percentage do you take on a winning tender?", "A percentage of the contract you win, agreed in writing before we start work on a bid. If the bid doesn't win, there's nothing to pay for that response."),
          ("Who sets the price and lodges the tender?", "You set the price and approve the final response. Nothing is lodged without your sign-off.")),
    group("About Wolf",
          ("Who actually reviews our documents?", "A legally trained professional with construction compliance experience reviews every document before it reaches you. Our systems do the reading, tracking and drafting, which is what keeps the service affordable."),
          ("Is this legal advice?", "No. Wolf is a compliance administration and tender support service. Where something needs legal advice, we'll tell you."),
          ("Which states do you cover?", "We're based in Canberra and work with businesses in the ACT and NSW. If you work elsewhere in Australia, talk to us."),
          ("Where is our information kept?", "In Australian-hosted storage wherever possible, with access limited to the people working on your account. We don't sell or share it.")),
])

PRICING = f"""<section class="hero"><div class="wrap">
  <p class="eyebrow"><b>Pricing</b> · two simple arrangements</p>
  <h1>Priced to give you <em>time back and peace of mind.</em></h1>
  <p class="lede">Two simple arrangements. Both are designed to do more than save you time: confidence that your compliance is in order, and a better win rate on the bigger work that goes to tender.</p>
</div></section>
<section class="block"><div class="wrap">
  <div class="grid-2" style="margin-top:0">
    <div class="card plan">{top("shield", "Compliance")}
      <p class="price">Subscription<small>A support arrangement, billed monthly</small></p>
      <p>Ongoing support for a fixed monthly fee, set by the size of your business and what you need.</p>
      <ul><li>Licence, ticket and insurance register, kept current</li><li>Expiry tracking and chasing</li><li>SWMS and toolbox talk memos as jobs need them</li><li>One check-in phone call a week</li></ul>
      <a class="btn btn-primary" href="contact.html">Ask for a quote{ARROW}</a></div>
    <div class="card plan">{top("award", "Tender responses")}
      <p class="price">No win, no fee<small>A percentage of the bids you win</small></p>
      <p>You pay only when a bid we wrote is successful. Requires signing up for six months of bid support.</p>
      <ul><li>Opportunities found online and through relationship channels</li><li>Responses written, reviewed and lodged</li><li>Nothing to pay on unsuccessful bids</li><li>Six-month bid support agreement</li></ul>
      <a class="btn btn-outline" href="contact.html">Talk to us about tenders{ARROW}</a></div>
  </div>
  <p class="terms">Fees and percentages are agreed in writing before work starts. No tender outcome is guaranteed. The six-month bid support agreement sets out which opportunities are covered and how a successful bid is defined.</p>
</div></section>
<section class="block alt" id="questions"><div class="wrap">
  <p class="kicker">Before you ask</p>
  <h2>Common questions.</h2>
  <div class="faq">
    {FAQ}
  </div>
</div></section>
{CTA}"""

CONTACT = f"""<section class="hero"><div class="wrap hero-cols">
  <div class="hero-copy">
    <p class="eyebrow"><b>Contact</b> · Canberra, ACT</p>
    <h1>Book a call. <em>Twenty minutes.</em></h1>
    <p class="lede">Tell us your trade, your crew size and what's taking up your time. We'll tell you plainly whether we can help and what it would cost.</p>
  </div>
  <div class="contact-card">
    <span class="tag">Email us</span>
    <p class="contact-line"><a href="mailto:{EMAIL}">{EMAIL}</a></p>
    <p class="note" style="margin:0">Email us with a good time to call and a phone number.</p>
    <ul><li>{icon("hardhat")}Your trade and crew size</li><li>{icon("clock")}What's taking up your time</li><li>{icon("phone")}A good time to call, and a number</li></ul>
    <a class="btn btn-primary" href="mailto:{EMAIL}?subject=Book%20a%20call">Email us{ARROW}</a>
  </div>
</div></section>
<section class="block"><div class="wrap">
  <p class="kicker">Who you'll deal with</p>
  <h2>Canberra based. <em>Qualified people.</em></h2>
  <p class="sub">We're a Canberra business working with trade and construction companies across the ACT and surrounding NSW.</p>
  <div class="grid-2">
    <div class="card">{top("scale", "Legal")}<h3>A legally trained professional, admitted in the ACT</h3><p>Every document is reviewed by someone with legal training and hands-on experience in construction compliance.</p></div>
    <div class="card">{top("chart", "Finance")}<h3>A Chartered Accountant on staff</h3><p>Commercial and financial experience behind your tender pricing schedules and the business side of compliance.</p></div>
  </div>
</div></section>
<section class="block alt"><div class="wrap">
  <p class="kicker">The process</p>
  <h2>What happens next.</h2>
  {steps(("A short call", "We ask about your work, your crew and where the paperwork hurts."),
         ("A plain proposal", "What we'd take on, what we'd need from you, and the fee."),
         ("We get started", "Send us your staff list and documents. We do the rest."))}
</div></section>"""

PAGES = {
    "index.html": ("Wolf | No new software. We just get on with it.",
                   "We keep compliance current and write tender responses for mid-sized Australian construction businesses. No new software and no logins.", HOME),
    "compliance.html": ("Compliance as a managed service | Wolf",
                        "Licences, insurances, SWMS and toolbox talks handled for trade businesses. One email, one WhatsApp number, one check-in phone call a week.", COMPLIANCE),
    "tenders.html": ("Tender responses, no win no fee | Wolf",
                     "We find tender opportunities, write the response and lodge it. You pay a percentage of the bids you win.", TENDERS),
    "pricing.html": ("Pricing | Wolf", "Compliance is a subscription support arrangement. Tender responses are a percentage of winning bids on a six-month bid support agreement.", PRICING),
    "contact.html": ("Contact | Wolf", "Book a 20-minute call with Wolf.", CONTACT),
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
        html = page(slug, title, desc, body, a.noindex)
        for f in MEDIA:
            html = html.replace(f"assets/{f}", f"assets/{f}?v={_mv(f)}")
        (out / slug).write_text(html, encoding="utf-8")
    for f in ("site.css", "site.js", "apple-touch-icon.png"):
        shutil.copy(HERE / f, out / f)
    shutil.copy(VIDEO / "inter-latin-wght-normal.woff2", out / "fonts" / "inter-latin-wght-normal.woff2")
    for f in MEDIA:
        shutil.copy(VIDEO / f, out / "assets" / f)
    print(f"Site written to {out} ({len(PAGES)} pages)")


if __name__ == "__main__":
    main()
