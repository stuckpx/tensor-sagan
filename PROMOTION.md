# Haramain Fridays — Growth Playbook (Agent-Executable)

Research-grounded promotion plan for https://www.haramainfridays.com, written so
each task can be handed to a Claude (Opus-class) agent session as a
self-contained prompt. Last researched: 2026-07-08.

## Context (paste into any executing agent's prompt)

> Haramain Fridays (https://www.haramainfridays.com) emails a free weekly
> English summary of the Friday khutbahs from Masjid al-Haram (Makkah) and
> Masjid an-Nabawi (Madinah). Summaries are AI-generated from the official
> sermon recordings and human-reviewed before send. Stack: Flask on Vercel
> (`website/server.py`), Firestore (subscribers/drafts/archive), weekly
> pipeline in `friday_sermon_email.py`, repo `stuckpx/tensor-sagan` (public).
> ~150 per-sermon SEO pages exist at `/sermons/<mosque>-<date>` with full
> meta/OG/Schema.org markup, sitemap at `/sitemap.xml` (157 URLs), valid
> robots.txt, og:image live. 16 subscribers as of 2026-06-27.

**Positioning (use everywhere):** competitors offer live audio, translations,
or PDFs (Manarat al-Haramain official streams, archive.org translations,
theislamicinformation.com listen-pages). Nobody offers a *written 5-minute
weekly summary by email*. That's the wedge: "Missed Jumu'ah at the Haramain?
Read both khutbahs in 5 minutes."

## Guardrails (apply to every task)

- Religious content: never editorialize beyond the sermon's content; keep the
  existing human-review gate for anything public-facing.
- Disclose AI-generated summaries where asked; never claim official affiliation
  with the Haramain, Saudi authorities, or haramain.info / Haramain Recordings.
- Never repost the audio/video recordings themselves (not our copyright) —
  link to them. Our summaries and cards are ours; the recordings are not.
- No spam: no unsolicited bulk DMs, no purchased lists, no astroturfing
  (r/islam is heavily moderated — value-first participation by a human only).
- Anything that posts publicly or emails a stranger: draft → human approves.

---

## Tier 0 — Emergency: the site is invisible (do first)

### T0.1 Get indexed by Google & Bing
- **Finding:** `site:haramainfridays.com` returns zero results on Google
  (2026-07-08). Sitemap/robots are healthy; the site simply has ~no backlinks
  and was never submitted to Search Console.
- **Access needed:** user's Google account (GSC property already verified via
  `website/google427bdf617b8c1116.html`) + create Bing Webmaster account.
- **Agent prompt:** "In Google Search Console for haramainfridays.com, submit
  https://www.haramainfridays.com/sitemap.xml, then use URL Inspection to
  request indexing for the homepage, /archive, and the 5 newest
  /sermons/<slug> pages. Import the property into Bing Webmaster Tools (it can
  import from GSC) and submit the sitemap there. Report indexed-page counts
  weekly." *(Browser task — user present for login, or do manually: ~15 min.)*
- **Done when:** GSC shows sitemap "Success"; `site:` queries return pages.

### T0.2 Add analytics (currently flying blind)
- **Finding:** no analytics of any kind on the site — channel attribution is
  impossible. Email links already carry `utm_source=email`.
- **Agent prompt:** "Add Vercel Web Analytics (or Plausible/GoatCounter if
  preferred — privacy-first, no cookie banner needed) to every page served by
  `website/server.py` in repo stuckpx/tensor-sagan. Verify events appear, then
  document in README how to read weekly traffic by source/UTM."
- **Done when:** page views + referrers visible per week; subscribe conversions
  countable against source.

### T0.3 Seed the first backlinks (directories)
- **Why:** indexing + authority need at least a handful of inbound links; for
  a niche site, Islamic directories + newsletter directories are the free
  starting set. (Directory traffic itself ≈ 0 — this is for SEO discovery.)
- **Agent prompt:** "Submit https://www.haramainfridays.com to: BackToJannah
  Islamic directory (backtojannah.com/islamic-directory — genuine non-profit
  sites accepted), muhammadisite.com/islamic-links, IslamicFinder's directory,
  intoislam.com directory, and newsletter directories InboxReads and similar
  free listings. Use the positioning line above, category 'Islamic /
  newsletter'. Log each submission URL + status in PROMOTION_LOG.md. Draft
  but do NOT submit anything requiring payment."
- **Done when:** ≥5 submissions logged; links live within ~30 days.

---

## Tier 1 — One-time builds that compound (agent-executable in-repo)

### T1.1 RSS/Atom feed
Newsletter/blog aggregators, Feedly discovery, and some Muslim content
aggregators ingest RSS. **Prompt:** "Add `/feed.xml` (Atom) to
`website/server.py`, listing the 20 newest sermons (title = topic + mosque,
link = sermon page, summary = sermon summary). Add `<link rel=alternate>` to
page heads and the feed to sitemap/robots. Validate with a feed validator."

### T1.2 Topic hub pages (programmatic SEO)
~150 sermons cluster into recurring themes (Hajj, patience, Ramadan, tawhid,
family…). Hub pages catch topical searches the per-date pages can't.
**Prompt:** "In stuckpx/tensor-sagan, derive 15–25 topic clusters from
`website/sermons_archive.json` topics/summaries (e.g. via keyword grouping).
Add `/topics/<slug>` pages to server.py listing matching sermons with intro
copy, cross-link from sermon pages ('More khutbahs on Patience'), add to
sitemap. Keep it static-simple: build the mapping into a JSON checked into the
repo, regenerated by `build_archive.py`."

### T1.3 Per-sermon share cards (dynamic og:image)
Static og-image.png is live; per-sermon cards (topic + imam + date) make every
shared sermon link unique and clickable. **Prompt:** "Add a card generator
(Pillow, `/og/<slug>.png` route or pre-generated files) rendering mosque name,
imam, topic, date on the brand green/gold. Wire per-sermon og:image +
twitter:image. Cache aggressively." *(This same generator later powers
Telegram/WhatsApp delivery if that idea is revived.)*

### T1.4 Homepage conversion pass
Social proof + clarity. **Prompt:** "On index.html: headline to 'Both Friday
khutbahs from Makkah & Madinah — summarized in your inbox every week, free';
add live subscriber count from `/api/` endpoint rounded ('Join 16+ readers' →
auto-updates); add 3-sermon preview strip pulled from the archive so visitors
see the product before subscribing; add a one-line 'How it works' (recorded →
summarized → reviewed → emailed Friday)."

### T1.5 Email referral loop
Every send should recruit. **Prompt:** "In `friday_sermon_email.py`'s
subscriber template, add a postscript block: 'Know someone who'd love this?
Forward it — or share haramainfridays.com/?utm_source=referral'. Track via
UTM (needs T0.2). Keep the existing WhatsApp/forward buttons."

---

## Tier 2 — Recurring weekly loop (scheduled agent task, Fridays after send)

### T2.1 Weekly share kit
**Prompt (run as a scheduled task each Friday after the email sends):** "Read
this week's two entries from Firestore archive/all (repo
/Users/mj/tensor-sagan, creds JSON in root). Generate: (a) an X/Threads post
≤280 chars per mosque with topic hook + sermon-page link, (b) a WhatsApp/
Telegram-formatted message (bold headers, both topics, one link), (c) a
Facebook/LinkedIn paragraph. Save to scratch + email them to
mjeelani@gmail.com titled 'Share kit — <date>' so a human can paste them into
their communities. Do not post anywhere directly."

### T2.2 Weekly growth report
**Prompt (same schedule):** "Report: subscriber count + deltas (Firestore),
GSC indexed pages/impressions/clicks if accessible, top referrers from
analytics, and any failed pipeline steps from
~/Library/Logs/haramain-fridays.log. Email a 10-line summary to
mjeelani@gmail.com." *(Extends the existing verify-youtube-sermon-pipeline
pattern.)*

---

## Tier 3 — Human-led, agent-assisted (highest ceiling in this niche)

### T3.1 WhatsApp seeding (the #1 channel for this audience)
Human posts the weekly share-kit message into family/masjid/community groups;
research consistently shows Muslim audiences discover content via WhatsApp
forwards more than any platform. Agent's role: T2.1 makes this a 30-second
weekly task.

### T3.2 Masjid & Islamic-center outreach
**Prompt:** "Research 25 English-speaking masjid newsletters / Islamic centers
(US/UK/Nigeria/Malaysia — match current subscriber geography). For each, draft
a 90-word personalized note offering the weekly summary as free content for
their Friday announcements, with a subscribe link. Output a CSV (name, city,
contact, draft). Send NOTHING — deliver drafts for human review."

### T3.3 Muslim newsletter cross-promo
**Prompt:** "Find 10 active Muslim-interest newsletters (Substack/beehiiv
etc.). For each: audience size if public, contact, and a 2-line cross-promo
pitch ('we mention you, you mention us'). Drafts only."

### T3.4 Reddit/forum participation — value-first, human only
r/islam removes most promotional posts. Viable pattern: human participates in
weekly khutbah discussion threads; where genuinely relevant, links a specific
sermon page (not the homepage). Agent may draft comment-length sermon recaps
on request; a human decides where/whether to post.

### T3.5 Short-video clips (dawahtainment) — deliberately deferred
TikTok/IG dominate Muslim Gen-Z discovery (2026 research), but doing this
right needs original visuals (we cannot repost Haramain Recordings footage)
and sustained effort. Revisit only if T0–T2 plateau; a text-card→voiceover
format using our own summaries would be the compliant angle.

---

## What NOT to do
- Don't buy lists or run giveaway-bait signups (poison for a 16-person list).
- Don't repost khutbah audio/video clips — link, never re-host.
- Don't bulk-DM or auto-post to religious communities.
- Don't over-invest in press/PR — near-zero conversion for newsletters.

## KPI baseline (2026-07-08)
| Metric | Now | 90-day target |
|---|---|---|
| Google-indexed pages | ~0 | 150+ |
| Subscribers | 16 | 50 |
| Analytics | none | live w/ source attribution |
| Referring domains | ~0 | 8+ |
| Weekly share kit | manual/none | automated |
