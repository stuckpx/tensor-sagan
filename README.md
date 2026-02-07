# Friday Sermon Email Automation 🕌

Automatically receive weekly email summaries of Friday sermons (khutbah) from Masjid al-Haram (Makkah) and Masjid an-Nabawi (Madinah).

## Features

- 📧 **Weekly Emails**: Beautifully formatted HTML emails every Friday
- 🤖 **AI Summaries**: Uses Google Gemini to generate sermon summaries
- 👤 **Imam Biographies**: Includes short bios of the imams who led the prayers
- ⏰ **Scheduled**: Runs automatically at 5:00 PM Makkah time every Friday
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

### 2. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Run Setup

```bash
./setup.sh
```

This interactive script will:
- Help you configure your `.env` file
- Optionally run a test to verify everything works
- Install the weekly scheduler

## Manual Usage
 
Run the script manually at any time:
 
```bash
# PROD MODE: Sends to ALL subscribers
python3 friday_sermon_email.py

# TEST MODE: Sends ONLY to mjeelani@gmail.com
python3 friday_sermon_email.py --test
```

## Scheduling

The script is configured to run every **Friday at 5:00 PM Makkah time** (AST - UTC+3), which is:
- 14:00 UTC
- 6:00 AM PST
- 9:00 AM EST

### Install Scheduler Manually

```bash
cp com.mj.friday-sermon-email.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mj.friday-sermon-email.plist
```

### Check Scheduler Status

```bash
launchctl list | grep friday-sermon
```

### View Logs

```bash
tail -f ~/Library/Logs/friday-sermon-email.log
```

### Uninstall Scheduler

```bash
launchctl unload ~/Library/LaunchAgents/com.mj.friday-sermon-email.plist
rm ~/Library/LaunchAgents/com.mj.friday-sermon-email.plist
```

## Configuration

All configuration is done via the `.env` file:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key for AI summaries |
| `SMTP_EMAIL` | Your email address for sending |
| `SMTP_PASSWORD` | SMTP password (App Password for Gmail) |
| `SMTP_SERVER` | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | SMTP port (default: 587) |
| `RECIPIENT_EMAIL` | Email to receive summaries |

## Data Sources

- **Sermon Recordings**: [haramain.info](http://www.haramain.info) - Archive of Haramain recordings
- **Imam Information**: Built-in database of current Haramain imams

## Files

```
tensor-sagan/
├── friday_sermon_email.py    # Main script
├── setup.sh                  # Interactive setup script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template
├── .env                      # Your credentials (create this)
└── com.mj.friday-sermon-email.plist  # launchd scheduler
```

## Troubleshooting

### Email not sending
- Check your SMTP credentials in `.env`
- For Gmail, ensure you're using an App Password, not your regular password
- Verify 2FA is enabled on your Google account

### Script not running on schedule
- Check if the job is loaded: `launchctl list | grep friday-sermon`
- View logs: `tail -f ~/Library/Logs/friday-sermon-email.log`
- Ensure your Mac is awake at the scheduled time

### No sermon data found
- The script uses haramain.info which is updated regularly
- If no data is found, the script generates content using AI

## License

MIT
