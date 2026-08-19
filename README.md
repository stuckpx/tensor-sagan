# Friday Sermon Email Automation 🕌

Automatically receive weekly email summaries of Friday sermons (khutbah) from Masjid al-Haram (Makkah) and Masjid an-Nabawi (Madinah).

## Features

- 📧 **Weekly Emails**: Beautifully formatted HTML emails sent every Friday once both Haramain mosques have published their sermons
- 🤖 **AI Summaries**: Uses Google Gemini to summarise the actual sermon audio
- 👤 **Imam Biographies**: Includes short bios of the imams who led the prayers
- ⏰ **Self-pacing scheduler**: A single hourly cron tick drives a state machine — it waits until both sermons are posted, drafts a review email to you, sends to subscribers only after you approve, and noops the rest of the time
- 🔁 **Approval reminders**: If you haven't approved a draft after 2 hours, it nudges you again — up to 5 reminders
- 🛡️ **Idempotent + race-safe**: Firestore transactions stop two ticks (or a future cloud cron) from double-blasting subscribers
- 🔗 **Recording Links**: Direct links to listen to the sermon recordings

## Quick Start

### 1. Configure Credentials

Copy the example environment file and add your credentials:

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

You'll need:
- **Gemini API Key**: Get one free at https://aistudio.google.com/apikey
- **SMTP Credentials**: For Gmail, create an App Password at https://myaccount.google.com/apppasswords
- **Firebase service account JSON**: place `harmainfridays-firebase-adminsdk-fbsvc-c21f19e297.json` (or your project's equivalent) at the repo root. Without it, the script can't read subscribers or save drafts.

### 2. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The launchd job invokes `.venv/bin/python3` directly, so the venv path matters.

### 3. Install the Scheduler

```bash
cp com.mj.haramain-fridays.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mj.haramain-fridays.plist
```

That's it — see [Scheduling](#scheduling) below for what the job actually does.

## How `--auto` works

`--auto` is the production entry point. Every tick it reads `drafts/<target_friday>` from Firestore and acts based on status:

| Status | Action |
|---|---|
| (no doc) | Check the [@Haramain_Recordings](https://www.youtube.com/@Haramain_Recordings) YouTube channel for **this Friday's** khutbah videos (strict date match — won't grab last week's), falling back to haramain.info per mosque. If both found, run AI summarisation (Gemini ingests the YouTube URLs directly), save a draft (status `pending`), email it to the reviewer with an "Approve" link. Otherwise wait. |
| `pending` | If 2+ hours since last reminder and fewer than 5 reminders sent, re-send the approval email with a "reminder" banner. Otherwise noop. |
| `approved` | Atomically transition `approved → sending` (Firestore transaction so concurrent ticks can't both send), email all subscribers, mark `sent`, append to the public archive. |
| `sending` | Another tick is mid-send — noop. |
| `sent` | Already done — noop. |

`target_friday` is "today if Friday, else most recent past Friday", so a Saturday-morning catch-up tick still operates on Friday's sermon.

After Saturday noon local time, if neither mosque has published, you get a single "no email this week" alert email so you know subscribers won't be hearing from us.

## Manual Usage

`--auto` is what runs on schedule. The legacy single-shot modes still exist for ad-hoc use:

```bash
# Recommended — single state-machine tick. Idempotent. Safe to run any time.
python3 friday_sermon_email.py --auto

# Build a draft for "today" and email it to the reviewer (legacy path; uses run-date, not target Friday)
python3 friday_sermon_email.py --draft

# Send to all subscribers if today's draft has been approved (legacy path)
python3 friday_sermon_email.py --send

# Probe the public site; exits non-zero and emails an alert if it's broken
python3 friday_sermon_email.py --healthcheck
```

⚠️ The legacy `--draft` path uses `set()` and will overwrite an existing draft (and its `sent` audit trail). Prefer `--auto` for anything you wire to a cron.

## Scheduling

Installed via launchd at `~/Library/LaunchAgents/com.mj.haramain-fridays.plist`. Fires hourly:
- **Friday 06:00 – 23:00** local
- **Saturday 00:00 – 12:00** local

(31 ticks/week. Most are noops.)

A second agent, `~/Library/LaunchAgents/com.mj.haramain-uptime.plist`, runs
`--healthcheck` at **08:00 and 20:00** daily and logs to
`~/Library/Logs/haramain-uptime.log`.

### Website uptime check

`--healthcheck` requests `/`, `/archive`, `/api/archive` and
`/api/approve_draft`, and emails an alert if any of them misbehaves (at most
one alert per calendar day, tracked in the Firestore `health_alerts`
collection). `--auto` also runs it just before emailing a draft, and adds a
warning banner to that email if the site is unhealthy — otherwise the Approve
button could be dead on arrival.

Note `/api/approve_draft` is expected to return **400**, not 200: with no token
it should reject the request. A **404** there means routing is broken.

That endpoint matters because it is what the Approve button in the weekly
review email points at. In July 2026 a Vercel routing change made every URL on
the site return 404 for roughly six days without anyone noticing — Vercel kept
reporting builds as "Ready", and nothing here made a real request. The fix was
removing a `rewrites` rule from `vercel.json` that was overriding Vercel's own
Flask routing and passing the rewrite destination to Flask as the request path.

### Useful commands

```bash
# Is it loaded?
launchctl list | grep haramain

# Tail the log
tail -f ~/Library/Logs/haramain-fridays.log

# Force a tick now (uses the same command launchd does)
~/tensor-sagan/.venv/bin/python3 ~/tensor-sagan/friday_sermon_email.py --auto

# Reload after editing the plist
launchctl unload ~/Library/LaunchAgents/com.mj.haramain-fridays.plist
launchctl load   ~/Library/LaunchAgents/com.mj.haramain-fridays.plist
```

### Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.mj.haramain-fridays.plist
rm ~/Library/LaunchAgents/com.mj.haramain-fridays.plist
```

⚠️ launchd can't fire while your Mac is asleep. If you need true reliability, run `--auto` from a cloud cron instead (Vercel cron + a Flask wrapper, GitHub Actions, etc.). The state machine is already designed to be safe under concurrent runners.

## Configuration

All configuration is via the `.env` file:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key for AI summaries |
| `SMTP_EMAIL` | Sending address |
| `SMTP_PASSWORD` | SMTP password (Gmail App Password recommended) |
| `SMTP_SERVER` | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | SMTP port (default: 587) |
| `RECIPIENT_EMAIL` | (legacy / not used by `--auto`; subscribers come from Firestore) |

`--auto` also has a few constants near the top of `run_auto_tick()` you can tweak:

| Constant | Default | Meaning |
|---|---|---|
| `AUTO_REVIEWER_EMAIL` | `mjeelani@gmail.com` | Address that receives the draft + reminders |
| `AUTO_MAX_REMINDERS` | `5` | Max reminder emails on top of the initial draft |
| `AUTO_REMINDER_INTERVAL_HOURS` | `2` | Minimum gap between reminders |

## Data Sources

- **Sermon recordings (primary)**: [@Haramain_Recordings](https://www.youtube.com/@Haramain_Recordings) YouTube channel — khutbah videos are discovered via the channel's search page (titles follow `"5th Jun 2026 Makkah Jumu'ah Khutbah Sheikh Dosary"`), and Gemini summarises the YouTube URLs directly (no audio download/upload)
- **Sermon recordings (fallback)**: [haramain.info](http://www.haramain.info) — used per mosque when the YouTube lookup comes up empty
- **Subscribers, drafts, approval state, archive**: Firestore (`subscribers`, `drafts`, `archive` collections)
- **Imam biographies**: built-in database in `friday_sermon_email.py`

### Archive storage model

The website archive (`/api/archive`, `/sermons/<slug>`) reads from a single
Firestore document at `archive/all` containing `{sermons:[...], imams:{...}}`.
`save_to_archive()` updates this doc on every successful auto-send, so the
website reflects new sermons within ~1 hour (edge-cache TTL) without any
redeploy. The `website/sermons_archive.json` file is kept as a backup
mirror and as a last-resort fallback when Firestore is unreachable.

To stay within the Firestore free tier (50K reads/day), the archive is
stored as one document (1 read/page-load instead of 1 per sermon) and the
Flask routes set `Cache-Control: public, s-maxage=3600` so Vercel's edge
absorbs most traffic. Doc size is ~125 KiB at 145 entries; the Firestore
1 MiB single-doc cap gives us headroom for ~1000 entries (~10 years).

### Vercel deployment

The Flask app supports two ways to authenticate with Firebase:

1. **`harmainfridays-firebase-adminsdk-fbsvc-*.json`** at the repo root
   (used locally; not committed — in `.gitignore`)
2. **`FIREBASE_SERVICE_ACCOUNT_JSON`** environment variable containing the
   raw JSON contents of the service account key (used on Vercel)

To deploy archive-write-through on Vercel, set
`FIREBASE_SERVICE_ACCOUNT_JSON` in the project's Environment Variables
(Production scope) to the *contents* of your service account JSON.

## Files

```
tensor-sagan/
├── friday_sermon_email.py            # Main script (--auto / --draft / --send)
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
├── .env                              # Your credentials (create this)
├── com.mj.haramain-fridays.plist     # launchd scheduler (hourly --auto)
├── api/                              # Vercel entry point → website/server.py
├── website/                          # Flask app: subscribe, unsubscribe, /api/approve_draft, archive
└── harmainfridays-firebase-adminsdk-fbsvc-*.json  # Firebase creds (not committed)
```

## Troubleshooting

### Email not sending
- Check SMTP credentials in `.env`
- For Gmail, you must use an App Password (not your account password) and 2FA must be on

### Draft email never arrives
- `tail ~/Library/Logs/haramain-fridays.log` — every tick logs its target Friday + decided action
- Most common cause on Friday morning: neither YouTube nor haramain.info has the khutbah up yet → the script correctly waits

### Archive commits pile up locally but never reach GitHub
- Symptom: `git log origin/main..HEAD` shows unpushed "Auto-sync sermon archive"
  commits, and `~/Library/Logs/haramain-fridays.log` contains
  `archive push failed (committed locally): remote: Permission to
  stuckpx/tensor-sagan.git denied to <other-account>`.
- Cause: this Mac has two GitHub accounts authenticated in `gh`, and the
  *active* one is not the account that owns this repo. Git resolves
  credentials through the macOS keychain, so `gh auth switch` alone does not
  fix it.
- Fix (already applied, recorded here in case it regresses): the remote is
  `https://stuckpx@github.com/...` and the repo sets
  `git config --local credential.username stuckpx`, which pins this
  repository to the owning account regardless of which account `gh` has
  active.
- Note the send itself is unaffected — the git sync is deliberately
  best-effort and cannot break the weekly email — which is exactly why this
  failed quietly for two Fridays (2026-08-07 and 2026-08-14) before anyone
  noticed.

### Subscribers never got the email
- Did you click the "Approve Draft" link? Without that, status stays `pending` and `--auto` won't send. (You'll be reminded up to 5 times.)
- Check `drafts/<friday-date>` in Firestore — `status` should be `sent` once it's been blasted

### "No sermon published this week" alert
- Means by Saturday noon local, at least one mosque's khutbah was still missing from both YouTube and haramain.info. The script chose not to send a half-complete email rather than guess

## License

MIT
