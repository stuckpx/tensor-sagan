#!/usr/bin/env python3
"""
Friday Sermon Email Automation
Fetches Friday khutbah recordings from Makkah and Medina grand mosques
(YouTube @Haramain_Recordings primary, haramain.info fallback),
generates AI summaries and imam biographies, and sends a weekly email.
"""

import os
import re
import ssl
import json
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Current GA Flash model (bumped from gemini-2.5-flash, June 2026). Flash tier
# is the right fit for summarisation; revisit periodically — these go stale.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
FIREBASE_CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harmainfridays-firebase-adminsdk-fbsvc-c21f19e297.json')

# Public website URL — used for unsubscribe links + the "subscribe / view online"
# CTAs in the weekly email. Override locally with WEBSITE_BASE_URL=...
WEBSITE_BASE_URL = os.getenv("WEBSITE_BASE_URL", "https://www.haramainfridays.com").rstrip("/")

# Initialize Firebase
db = None
if os.path.exists(FIREBASE_CREDENTIALS_PATH):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print(f"✓ Connected to Firebase")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
else:
    print(f"⚠️ Firebase credentials not found at {FIREBASE_CREDENTIALS_PATH}")
    print("Email sending will fail without database.")

# Haramain khutbah archive URL
KHUTBAH_URL = "http://www.haramain.info/search/label/Friday%20Khutbah%20-%20%D8%A7%D9%84%D8%AE%D8%B7%D8%A8%D8%A9%20%D8%A7%D9%84%D8%AC%D9%85%D8%B9%D8%A9"


def load_subscribers():
    """Load active subscribers from Firestore."""
    if not db:
        print("Error: Database connection not established")
        return []
    
    try:
        subscribers = []
        # Query for active subscribers
        docs = db.collection('subscribers').where('active', '==', True).stream()
        for doc in docs:
            sub = doc.to_dict()
            # Ensure 'active' field is explicitly True, as Firestore's where clause might not be strict enough for all cases
            if sub.get('active', True): 
                subscribers.append(sub)
        return subscribers
    except Exception as e:
        print(f"Error fetching subscribers: {e}")
        return []

# Database of Haramain Imams with biographical information
IMAM_BIOS = {
    "sudais": {
        "name": "Sheikh Abdul Rahman Al-Sudais",
        "bio": "Sheikh Abdul Rahman Ibn Abdul Aziz al-Sudais is the Chief Imam and Khateeb of Masjid al-Haram in Makkah and President of the General Presidency for the Affairs of the Two Holy Mosques. Born in 1960 in Al-Bukayriyah, Saudi Arabia, he memorized the entire Holy Quran by age 12. He earned his PhD in Islamic Sharia from Umm Al-Qura University and was appointed Imam of Masjid al-Haram in 1984 at age 24. He is renowned globally for his emotionally powerful Quran recitation and has led Taraweeh prayers for over 35 years."
    },
    "shuraim": {
        "name": "Sheikh Saud Al-Shuraim",
        "bio": "Sheikh Saud ibn Ibrahim Al-Shuraim is a renowned Imam of Masjid al-Haram and professor at Umm Al-Qura University. Born in Riyadh in 1964, he memorized the Quran at an early age and obtained his PhD in Islamic Jurisprudence. He was appointed as an Imam of the Grand Mosque in 1991 and is known for his clear, measured recitation style and scholarly approach to khutbahs."
    },
    "muaiqly": {
        "name": "Sheikh Maher al-Mu'aiqly",
        "bio": "Sheikh Maher bin Hamad Al-Mu'aiqly is an Imam of Masjid al-Haram known for his beautiful, melodious recitation. Born in 1969 in Madinah, he memorized the Quran by age 13 and earned a Master's degree in Islamic Studies. He was appointed Imam in 2007 and has become one of the most beloved reciters worldwide, known for his emotional and spiritually moving delivery."
    },
    "juhany": {
        "name": "Sheikh Abdullah Awad Al-Juhany",
        "bio": "Sheikh Abdullah Awad Al-Juhany is a prominent Imam of Masjid al-Haram. Born in 1976 in Jeddah, he memorized the Quran at age 14 and holds a PhD in Islamic Studies. He was appointed Imam in 2007 and is widely recognized for his powerful, emotional recitation style that moves listeners to tears. He is also known for his impactful Friday sermons."
    },
    "baleelah": {
        "name": "Sheikh Bandar Baleelah",
        "bio": "Sheikh Bandar bin Abdul Aziz Baleelah is an Imam of Masjid al-Haram known for his distinguished recitation style. Born in Makkah, he memorized the Quran at a young age and holds a PhD in Islamic Studies from Umm Al-Qura University. He was appointed as an Imam in 2013 and serves as an assistant professor at the university."
    },
    "dawsari": {
        "name": "Sheikh Yasir al-Dawsari",
        "bio": "Sheikh Yasir bin Rashid Al-Dawsari is one of the younger Imams of Masjid al-Haram, known for his powerful voice and emotional recitation. He memorized the Quran at age 10 and holds a Master's degree in Quranic Studies. He was appointed Imam in 2018 and has quickly gained a large following for his moving recitation during Taraweeh prayers."
    },
    "ghazzawi": {
        "name": "Sheikh Faisal Ghazzawi",
        "bio": "Sheikh Faisal bin Jameel Ghazzawi is an Imam of Masjid al-Haram. He memorized the Quran at an early age and obtained his education in Islamic Studies. Known for his clear recitation and thoughtful sermons, he continues the tradition of scholarship at the Grand Mosque."
    },
    "humaid": {
        "name": "Sheikh Saleh bin Abdullah al-Humaid",
        "bio": "Sheikh Saleh bin Abdullah bin Humaid is a senior Imam of Masjid al-Haram and former Chairman of the Shura Council. Born in 1955, he is one of the most respected Islamic scholars in Saudi Arabia. He holds a PhD in Islamic Jurisprudence and has been an Imam since 1984. He is known for his scholarly depth and authoritative Friday sermons."
    },
    "khayyat": {
        "name": "Sheikh Usamah Abdul Aziz Al-Khayyat",
        "bio": "Sheikh Usamah Abdul Aziz Al-Khayyat is a senior Imam of Masjid al-Haram. Born in Makkah, he memorized the Quran at a young age and obtained his higher education in Islamic Studies. He has been serving as an Imam since the 1990s and is known for his calm, measured recitation style and scholarly sermons."
    },
    "hudhaify": {
        "name": "Sheikh Ali Al-Hudhaify",
        "bio": "Sheikh Ali bin Abdur Rahman Al-Hudhaify is the Chief Imam of Masjid an-Nabawi (The Prophet's Mosque) in Madinah. Born in 1947, he memorized the Quran at age 12 and holds a PhD in Islamic Studies. He was appointed Imam in 1979 and is known for his distinctive, measured recitation style and profound Friday sermons."
    },
    "qasim": {
        "name": "Sheikh Abdul Muhsin Al-Qasim",
        "bio": "Sheikh Abdul Muhsin bin Muhammad Al-Qasim is an Imam of Masjid an-Nabawi in Madinah. He is known for his scholarly Friday sermons and has authored numerous Islamic books. He holds advanced degrees in Islamic Studies and is respected for his comprehensive knowledge of Islamic jurisprudence."
    },
    "buaijan": {
        "name": "Sheikh Ahmad bin Taleb Hameed",
        "bio": "Sheikh Ahmad bin Taleb Hameed is an Imam of Masjid an-Nabawi. He is known for his beautiful recitation and thoughtful sermons that address contemporary issues while remaining grounded in classical Islamic scholarship."
    },
    "buayjan": {
        "name": "Sheikh Bu'ayjan",
        "bio": "Sheikh Bu'ayjan is an Imam and Khateeb of Masjid an-Nabawi in Madinah, known for his Friday khutbahs delivered at the Prophet's Mosque."
    },
    "budair": {
        "name": "Sheikh Salah Al-Budair",
        "bio": "Sheikh Salah bin Muhammad Al-Budair is an Imam of Masjid an-Nabawi in Madinah. He is known for his beautiful voice and emotional delivery. He holds a PhD in Islamic Studies and serves as a judge in the Madinah courts alongside his duties as Imam."
    },
    "thubayti": {
        "name": "Sheikh Saleh bin Muhammad Al-Thubayti",
        "bio": "Sheikh Saleh bin Muhammad Al-Thubayti is a respected Imam of Masjid an-Nabawi in Madinah. He is known for his calm and powerful recitation, and his Friday Khutbahs are known to be very articulate and scholarly."
    },
    "muhanna": {
        "name": "Sheikh Khalid Al-Muhanna",
        "bio": "Sheikh Khalid bin Sulaiman Al-Muhanna is an Imam of Masjid an-Nabawi, appointed in 1441 AH (2019). He is a respected scholar and faculty member at the Islamic University of Madinah. Known for his clear and precise recitation, he brings a deep scholarly background to his position at the Prophet's Mosque."
    },
    "alesheikh": {
        "name": "Sheikh Hussayn Aal Sheikh",
        "bio": "Sheikh Hussayn bin Abdulaziz Aal Sheikh is an Imam and Khateeb of Masjid an-Nabawi in Madinah. A descendant of Sheikh Muhammad bin Abdul Wahhab, he holds a doctorate in Fiqh (Islamic Jurisprudence) and serves as a judge in Madinah. His khutbahs are known for their strong scholarly foundation."
    },
}


def get_imam_key(imam_name: str) -> str:
    """Match an imam name to our database key."""
    name_lower = imam_name.lower()
    # YouTube titles use typographic apostrophes ("Mu'ayqali", "Bu'ayjaan");
    # normalize them, and also try an apostrophe-stripped copy so those
    # spellings match the filename-style keywords below.
    for fancy in ("’", "‘", "`"):
        name_lower = name_lower.replace(fancy, "'")
    name_stripped = name_lower.replace("'", "")

    # Direct keyword matching
    keywords = {
        "sudais": "sudais",
        "shuraim": "shuraim",
        "muaiqly": "muaiqly",
        "mu'aiqly": "muaiqly",
        "moaiqly": "muaiqly",
        "muayqali": "muaiqly",
        "juhany": "juhany",
        "juhani": "juhany",
        "baleelah": "baleelah",
        "balilah": "baleelah",
        "dawsari": "dawsari",
        "dosari": "dawsari",
        "dosary": "dawsari",
        "ghazzawi": "ghazzawi",
        "gazzawi": "ghazzawi",
        "humaid": "humaid",
        "khayyat": "khayyat",
        "khayat": "khayyat",
        "hudhaify": "hudhaify",
        "hudhaifi": "hudhaify",
        "qasim": "qasim",
        "qaasim": "qasim",
        "budair": "budair",
        "budayr": "budair",
        "thubayti": "thubayti",
        "thubaiti": "thubayti",
        "thubaity": "thubayti",
        "muhanna": "muhanna",
        "ale sheikh": "alesheikh",
        "aal sheikh": "alesheikh",
        # URL filename variants — haramain.info / quranicaudio mirror MP3s use these
        "alsheikh": "alesheikh",        # e.g. "SheikhAlSheikh_JumuaKhutbah-..."
        "buayjaan": "buayjan",          # e.g. "SheikhBuayjaan_JumuaKhutbah-..." → Sheikh Bu'ayjan
        "buayjan":  "buayjan",
        "bu'ayjan": "buayjan",          # display-name form (with apostrophe)
        "buaijaan": "buayjan",
        "hameed":   "buaijan",          # Sheikh Ahmad bin Taleb Hameed (distinct from Bu'ayjan)
        "ahmad bin taleb": "buaijan",
        "hudayfi":  "hudhaify",         # alt spelling of Hudhayfi
    }
    
    for keyword, key in keywords.items():
        if keyword in name_lower or keyword in name_stripped:
            return key

    return None


def fetch_khutbah_data(target_friday=None) -> dict:
    """Fetch Friday khutbah information from haramain.info.

    If target_friday (a date) is provided, only return links whose URL slug
    parses to that exact (year, month, day). This is the "is this week's
    sermon actually posted yet?" guard used by --auto mode. Without it,
    the function falls back to "most recent" sorting (legacy behavior).
    """
    try:
        response = requests.get(KHUTBAH_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        sermons = {
            "makkah": None,
            "madinah": None
        }
        
        # Find all links on the page
        all_links = soup.find_all('a', href=True)
        
        makkah_link = None
        madinah_link = None
        
        # Collect candidate links
        makkah_candidates = []
        madinah_candidates = []
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text().lower()
            
            # Skip non-html posts
            if href.lower().endswith(('.mp3', '.pdf', '.jpg', '.png')):
                continue
            
            # Identify candidates
            # Identify candidates
            if 'jumuah' in href.lower() or 'jumu' in text:
                # Extract date from URL for sorting (YYYY/MM)
                # Format: http://www.haramain.info/2026/02/...
                date_match = re.search(r'/(\d{4})/(\d{2})/', href)
                year, month, day = 0, 0, 0
                
                # Month mapping
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12,
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
                    'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                
                if date_match:
                    year = int(date_match.group(1))
                    # Default month from URL (archive month)
                    month = int(date_match.group(2))
                    
                    # Try to extract REAL month and day from slug
                    patterns = re.findall(r'-(\d{1,2})(?:st|nd|rd|th)?-([a-z]+)', href.lower())
                    found_gregorian = False
                    for d_str, m_str in patterns:
                        if m_str in month_map:
                            day = int(d_str)
                            month = month_map[m_str]
                            found_gregorian = True
                    
                    if not found_gregorian:
                        # Fallback to just day extraction if full pattern fails
                        day_match = re.search(r'-(\d{1,2})(?:st|nd|rd|th)?-', href.lower())
                        if day_match:
                            day = int(day_match.group(1))

                sort_key = (year, month, day)

                if 'makkah' in href.lower() or 'makkah' in text:
                    makkah_candidates.append({'href': href, 'date': sort_key})
                elif 'madeenah' in href.lower() or 'madinah' in href.lower() or 'madinah' in text:
                    madinah_candidates.append({'href': href, 'date': sort_key})

        # If a target Friday is given, filter strictly to that date.
        # This prevents silently picking up last week's post when this
        # week's hasn't been published yet.
        if target_friday is not None:
            tf_key = (target_friday.year, target_friday.month, target_friday.day)
            makkah_candidates = [c for c in makkah_candidates if c['date'] == tf_key]
            madinah_candidates = [c for c in madinah_candidates if c['date'] == tf_key]

        # Sort descending by date (YYYY, MM, DD)
        makkah_candidates.sort(key=lambda x: x['date'], reverse=True)
        madinah_candidates.sort(key=lambda x: x['date'], reverse=True)

        if makkah_candidates:
            makkah_link = makkah_candidates[0]['href']

        if madinah_candidates:
            madinah_link = madinah_candidates[0]['href']
        
        # Fetch Makkah sermon page to get imam name
        if makkah_link:
            sermons["makkah"] = fetch_sermon_details(makkah_link, "Masjid al-Haram, Makkah")
        
        # Fetch Madinah sermon page to get imam name
        if madinah_link:
            sermons["madinah"] = fetch_sermon_details(madinah_link, "Masjid an-Nabawi, Madinah")
        
        return sermons
        
    except Exception as e:
        print(f"Error fetching khutbah data: {e}")
        return {"makkah": None, "madinah": None}


def fetch_sermon_details(url: str, mosque_name: str) -> dict:
    """Fetch sermon details from individual sermon page."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to get imam from meta description
        meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
        
        imam_name = "Unknown Imam"
        
        if meta_desc:
            desc_content = meta_desc.get('content', '')
            # Look for "Sheikh X" pattern in description
            imam_name = extract_imam_from_text(desc_content)
        
        # Also check the page title
        title = soup.find('title')
        title_text = title.get_text() if title else ""
        
        if imam_name == "Unknown Imam":
            # Check tags/labels for Imam name
            tags = soup.find_all('a', rel='tag')
            for tag in tags:
                tag_text = tag.get_text()
                name = extract_imam_name(tag_text)
                if name != "Unknown Imam":
                    imam_name = name
                    break
        
        audio_url = ""
        # Try extracting from page body if not found
        content_div = soup.find('div', class_='post-body') or soup.find('div', class_='entry-content')
        
        if content_div:
            # 1. Check Text
            if imam_name == "Unknown Imam":
                body_text = content_div.get_text()
                imam_name = extract_imam_from_text(body_text)
                
            # 2. Check MP3 Links (common on this site)
            links = content_div.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                href_lower = href.lower()
                if '.mp3' in href_lower or 'audio' in href_lower:
                    if 'khutbah' in href_lower and not audio_url:
                        audio_url = href
                    # Try to find imam key in the filename
                    if imam_name == "Unknown Imam":
                        key = get_imam_key(href_lower)
                        if key and key in IMAM_BIOS:
                            imam_name = IMAM_BIOS[key]['name']
        elif imam_name == "Unknown Imam":
            body_text = soup.get_text() # Fallback to full text
            imam_name = extract_imam_from_text(body_text)
        
        return {
            "title": title_text,
            "link": url,
            "imam": imam_name,
            "mosque": mosque_name,
            "audio_url": audio_url
        }



        
    except Exception as e:
        print(f"  Warning: Could not fetch sermon page {url}: {e}")
        return {
            "title": "Friday Sermon",
            "link": url,
            "imam": "Unknown Imam",
            "mosque": mosque_name,
            "audio_url": ""
        }


# ---------------------------------------------------------------------------
# YouTube source: @Haramain_Recordings channel
# ---------------------------------------------------------------------------

YOUTUBE_CHANNEL_HANDLE = "Haramain_Recordings"


def _youtube_date_str(d) -> str:
    """Format a date the way Haramain_Recordings titles do: '5th Jun 2026'."""
    day = d.day
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix} {d.strftime('%b %Y')}"


def _normalize_title(t: str) -> str:
    for fancy in ("’", "‘", "`"):
        t = t.replace(fancy, "'")
    return " ".join(t.split())


def fetch_khutbah_data_youtube(target_friday) -> dict:
    """Find this Friday's khutbah videos on the Haramain_Recordings channel.

    Titles follow a rigid pattern, e.g.
        "5th Jun 2026 Makkah Jumu'ah Khutbah Sheikh Dosary"
    so we search the channel for the date string and parse the matching
    titles. The channel posts every salaah/adhaan (~15 videos/day), so the
    channel RSS feed scrolls too fast to be useful and we hit the search
    page instead (keyless, no API quota). Returns the same shape as
    fetch_khutbah_data(); either mosque may be None.
    """
    from urllib.parse import quote
    date_str = _youtube_date_str(target_friday)
    query = f"{date_str} Jumu'ah Khutbah"
    url = f"https://www.youtube.com/@{YOUTUBE_CHANNEL_HANDLE}/search?query={quote(query)}"
    sermons = {"makkah": None, "madinah": None}
    try:
        resp = requests.get(url, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en"})
        resp.raise_for_status()
        m = (re.search(r'var ytInitialData = ({.*?});</script>', resp.text)
             or re.search(r'window\["ytInitialData"\]\s*=\s*({.*?});', resp.text))
        if not m:
            print("  ⚠️ YouTube: ytInitialData not found in search page")
            return sermons

        videos = []

        def walk(o):
            if isinstance(o, dict):
                if 'videoRenderer' in o:
                    v = o['videoRenderer']
                    title = ''.join(r.get('text', '') for r in v.get('title', {}).get('runs', []))
                    if v.get('videoId') and title:
                        videos.append((v['videoId'], title))
                for vv in o.values():
                    walk(vv)
            elif isinstance(o, list):
                for vv in o:
                    walk(vv)

        walk(json.loads(m.group(1)))

        date_lower = date_str.lower()
        for video_id, raw_title in videos:
            title = _normalize_title(raw_title)
            t_lower = title.lower()
            if not t_lower.startswith(date_lower):
                continue
            # Exclude sibling uploads: Jumu'ah Salaah, Adhaan, Translation
            if "khutbah" not in t_lower or "translation" in t_lower:
                continue
            if "adhaan" in t_lower or "salaah" in t_lower:
                continue
            # 'madeen' catches Madeenah and typo variants like "Madeenaah"
            if "makkah" in t_lower:
                mosque_key, mosque_name = "makkah", "Masjid al-Haram, Makkah"
            elif "madeen" in t_lower or "madinah" in t_lower:
                mosque_key, mosque_name = "madinah", "Masjid an-Nabawi, Madinah"
            else:
                continue
            if sermons[mosque_key]:
                continue

            imam = "Unknown Imam"
            im = re.search(r"sheikh\s+(.*)$", title, re.IGNORECASE)
            if im:
                raw_imam = f"Sheikh {im.group(1).strip()}"
                key = get_imam_key(raw_imam)
                imam = IMAM_BIOS[key]["name"] if key and key in IMAM_BIOS else raw_imam

            watch_url = f"https://www.youtube.com/watch?v={video_id}"
            sermons[mosque_key] = {
                "title": title,
                "link": watch_url,
                "imam": imam,
                "mosque": mosque_name,
                "audio_url": watch_url,
                "video_url": watch_url,  # signals Gemini direct-URL ingestion
            }
    except Exception as e:
        print(f"  ⚠️ YouTube fetch failed: {e}")
    return sermons


def fetch_khutbah_data_any(target_friday) -> dict:
    """YouTube first (haramain.info has been unreliable), haramain.info fills gaps."""
    sermons = fetch_khutbah_data_youtube(target_friday)
    if sermons.get("makkah") and sermons.get("madinah"):
        print("  source: YouTube (both mosques)")
        return sermons
    fallback = fetch_khutbah_data(target_friday=target_friday)
    for k in ("makkah", "madinah"):
        if not sermons.get(k) and fallback.get(k):
            sermons[k] = fallback[k]
            print(f"  source: haramain.info fallback for {k}")
    return sermons


def extract_imam_from_text(text: str) -> str:
    """Extract imam name from text content."""
    # Look for known imam names in the text
    text_lower = text.lower()
    
    imam_mappings = {
        "juhany": "Sheikh Abdullah Awad Al-Juhany",
        "juhani": "Sheikh Abdullah Awad Al-Juhany",
        "sudais": "Sheikh Abdul Rahman Al-Sudais",
        "shuraim": "Sheikh Saud Al-Shuraim",
        "muaiqly": "Sheikh Maher al-Mu'aiqly",
        "mu'aiqly": "Sheikh Maher al-Mu'aiqly",
        "maher": "Sheikh Maher al-Mu'aiqly",
        "muayqali": "Sheikh Maher al-Mu'aiqly",
        "dawsari": "Sheikh Yasir al-Dawsari",
        "dosari": "Sheikh Yasir al-Dawsari",
        "dosary": "Sheikh Yasir al-Dawsari",
        "baleelah": "Sheikh Bandar Baleelah",
        "bandar": "Sheikh Bandar Baleelah",
        "ghazzawi": "Sheikh Faisal Ghazzawi",
        "gazzawi": "Sheikh Faisal Ghazzawi",
        "humaid": "Sheikh Saleh bin Abdullah al-Humaid",
        "khayyat": "Sheikh Usamah Abdul Aziz Al-Khayyat",
        "khayat": "Sheikh Usamah Abdul Aziz Al-Khayyat",
        "hudhaify": "Sheikh Ali Al-Hudhaify",
        "hudhayfi": "Sheikh Ali Al-Hudhaify",
        "hudaifi": "Sheikh Ali Al-Hudhaify",
        "hudhaifi": "Sheikh Ali Al-Hudhaify",
        "qasim": "Sheikh Abdul Muhsin Al-Qasim",
        "qaasim": "Sheikh Abdul Muhsin Al-Qasim",
        "budair": "Sheikh Salah Al-Budair",
        "buayjan": "Sheikh Bu'ayjan",
        "buayjaan": "Sheikh Bu'ayjan",
        "hameed": "Sheikh Ahmad bin Taleb Hameed",
        "ahmad bin taleb": "Sheikh Ahmad bin Taleb Hameed",
        "thubayti": "Sheikh Saleh bin Muhammad Al-Thubayti",
        "thubaiti": "Sheikh Saleh bin Muhammad Al-Thubayti",
        "thubaity": "Sheikh Saleh bin Muhammad Al-Thubayti",
        "ale sheikh": "Sheikh Hussayn Aal Sheikh",
        "aal sheikh": "Sheikh Hussayn Aal Sheikh",
    }
    
    for keyword, full_name in imam_mappings.items():
        if keyword in text_lower:
            return full_name
    
    return "Unknown Imam"


def extract_imam_name(title: str, text_content: str = "") -> str:
    """Extract imam name from a sermon title."""
    # Common patterns: "Sheikh X", "Sh. X", "Imam X"
    patterns = [
        r'(?:Sheikh|Sh\.|Shaykh|Imam)\s+([A-Za-z\s\-\']+?)(?:\s*[-–]\s*|\s*$)',
        r'(?:led by|by)\s+(?:Sheikh|Sh\.|Shaykh|Imam)?\s*([A-Za-z\s\-\']+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Check for known imam names directly
    for key, info in IMAM_BIOS.items():
        if key in title.lower() or info["name"].split()[-1].lower() in title.lower():
            return info["name"]
    
    return "Unknown Imam"


def upload_audio_to_gemini(audio_url: str) -> str:
    """Download audio from URL and upload to Gemini File API."""
    import tempfile
    
    if not audio_url or not GEMINI_API_KEY:
        return None
        
    try:
        print(f"  Downloading auth for AI text generation from {audio_url}")
        resp = requests.get(audio_url, stream=True)
        resp.raise_for_status()
        
        fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        with os.fdopen(fd, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                
        num_bytes = os.path.getsize(temp_path)
        
        print(f"  Uploading {num_bytes} bytes to Gemini...")
        upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={GEMINI_API_KEY}"
        headers = {
            "X-Goog-Upload-Command": "start, upload, finalize",
            "X-Goog-Upload-Header-Content-Length": str(num_bytes),
            "X-Goog-Upload-Header-Content-Type": "audio/mp3",
            "Content-Type": "audio/mp3"
        }
        
        with open(temp_path, "rb") as f:
            upl_resp = requests.post(upload_url, headers=headers, data=f, timeout=120)
            
        os.remove(temp_path) # Clean up
        
        if upl_resp.status_code == 200:
            file_uri = upl_resp.json().get("file", {}).get("uri")
            print(f"  ✓ Uploaded audio to {file_uri}")
            return file_uri
        else:
            print(f"  ⚠️ Error uploading to Gemini: {upl_resp.text}")
            return None
            
    except Exception as e:
        print(f"  ⚠️ Error processing audio URL {audio_url}: {e}")
        return None


def generate_ai_content(sermon_data: dict) -> dict:
    """Generate sermon summaries using Gemini API."""
    if not GEMINI_API_KEY:
        return generate_fallback_content(sermon_data)
        
    makkah_imam = sermon_data.get('makkah', {}).get('imam', 'the Imam')
    madinah_imam = sermon_data.get('madinah', {}).get('imam', 'the Imam')

    def media_uri(info):
        """YouTube URLs go to Gemini as-is; MP3s need download + Files upload."""
        if not info:
            return None
        if info.get('video_url'):
            return info['video_url']
        if info.get('audio_url'):
            return upload_audio_to_gemini(info['audio_url'])
        return None

    makkah_uri = media_uri(sermon_data.get('makkah'))
    madinah_uri = media_uri(sermon_data.get('madinah'))
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    last_friday = datetime.now()
    # Adjust to find the most recent Friday
    days_since_friday = (last_friday.weekday() - 4) % 7
    last_friday -= timedelta(days=days_since_friday)
    
    date_str = last_friday.strftime('%B %d, %Y')
    
    prompt = f"""You are an expert on Friday sermons (khutbah) from the Two Holy Mosques in Makkah and Madinah.

Today is {date_str}. Generate authentic Friday sermon summaries for:

1. **Masjid al-Haram, Makkah** - Imam: {makkah_imam}
2. **Masjid an-Nabawi, Madinah** - Imam: {madinah_imam}

FOR EACH MOSQUE, provide:
- **topic**: A meaningful Islamic topic appropriate for this week
- **summary**: A detailed 4-6 sentence summary of the sermon's key messages, Quranic references, and lessons. """

    if makkah_uri or madinah_uri:
        prompt += "\n\nI have provided recordings of the sermons. Please listen to them to generate accurate summaries from the actual Arabic khutbahs. "
        if makkah_uri and madinah_uri:
            prompt += "The FIRST recording attached is Makkah's khutbah, and the SECOND recording attached is Madinah's khutbah."
        elif makkah_uri:
            prompt += "The attached recording is Makkah's khutbah. For Madinah, provide a general but realistic summary."
        elif madinah_uri:
            prompt += "The attached recording is Madinah's khutbah. For Makkah, provide a general but realistic summary."
            
    prompt += f"""\n\nFormat your response ONLY as JSON (no markdown):
{{
  "makkah": {{
    "topic": "Topic title",
    "summary": "Detailed summary..."
  }},
  "madinah": {{
    "topic": "Topic title", 
    "summary": "Detailed summary..."
  }},
  "introduction": "A warm 2-3 sentence welcome for the newsletter."
}}"""

    def file_part(uri):
        fd = {"fileUri": uri}
        if "youtube.com" not in uri:  # uploaded MP3s need an explicit mimeType
            fd["mimeType"] = "audio/mp3"
        return {"fileData": fd}

    parts = []
    if makkah_uri:
        parts.append(file_part(makkah_uri))
    if madinah_uri:
        parts.append(file_part(madinah_uri))

    parts.append({"text": prompt})

    # Server-side enforced output shape — the API guarantees valid JSON
    # matching this schema, so blank-summary drafts from free-form output
    # (the 2026-05-22 incident) can't recur. parse_sermon_json stays as a
    # second line of defense.
    mosque_schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["topic", "summary"],
    }
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseJsonSchema": {
                "type": "object",
                "properties": {
                    "makkah": mosque_schema,
                    "madinah": mosque_schema,
                    "introduction": {"type": "string"},
                },
                "required": ["makkah", "madinah", "introduction"],
            },
        }
    }
    
    try:
        # YouTube URLs are fetched/processed server-side inside this call,
        # which can take several minutes — far longer than uploaded audio.
        response = requests.post(url, json=payload, timeout=600)
        response.raise_for_status()
        
        result = response.json()
        candidates = result.get("candidates") or []
        ai_text = ""
        if candidates:
            ai_text = (candidates[0].get("content", {}).get("parts", [{}])[0] or {}).get("text", "") or ""
        if not ai_text:
            finish = (candidates[0].get("finishReason") if candidates else None)
            pf = result.get("promptFeedback")
            print(f"  ⚠️ Gemini returned no text. finishReason={finish} promptFeedback={pf} keys={list(result.keys())}")

        sermon_content = parse_sermon_json(ai_text)

        content = {
            "makkah_topic": sermon_content.get("makkah", {}).get("topic", "Friday Sermon"),
            "makkah_summary": sermon_content.get("makkah", {}).get("summary", ""),
            "madinah_topic": sermon_content.get("madinah", {}).get("topic", "Friday Sermon"),
            "madinah_summary": sermon_content.get("madinah", {}).get("summary", ""),
            "introduction": sermon_content.get("introduction", f"Welcome to this week's Friday Sermon Summary from the Two Holy Mosques. This week, the prayers at Masjid al-Haram were led by {makkah_imam}, and at Masjid an-Nabawi by {madinah_imam}."),
            "makkah_bio": get_imam_bio(makkah_imam),
            "madinah_bio": get_imam_bio(madinah_imam),
            "makkah_imam": makkah_imam,
            "madinah_imam": madinah_imam
        }
        if not (content["makkah_summary"] or content["madinah_summary"]):
            # Parse failure / empty response — let --auto retry next tick
            # instead of shipping a draft with blank summaries (2026-05-22).
            content["ai_failed"] = True
        return content

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        fallback = generate_fallback_content(sermon_data)
        fallback["ai_failed"] = True
        return fallback


def parse_sermon_json(text: str) -> dict:
    """Parse JSON from AI response, handling markdown code blocks."""
    # Try to extract JSON from markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()
    
    try:
        return json.loads(text)
    except Exception as e:
        # Loud failure so we don't silently ship a draft with empty summaries
        # (see 2026-05-22 incident).
        preview = (text or "")[:500]
        print(f"  ⚠️ parse_sermon_json failed: {e}; raw preview (first 500 chars): {preview!r}")
        return {
            "makkah": {"topic": "Friday Sermon", "summary": ""},
            "madinah": {"topic": "Friday Sermon", "summary": ""},
            "introduction": ""
        }


def get_imam_bio(imam_name: str) -> str:
    """Get biography for an imam from our database."""
    key = get_imam_key(imam_name)
    if key and key in IMAM_BIOS:
        return IMAM_BIOS[key]["bio"]
    return f"{imam_name} is an esteemed Imam of one of Islam's holiest mosques, known for their scholarly knowledge and spiritual leadership."


def generate_fallback_content(sermon_data: dict) -> dict:
    """Generate content without AI if API is unavailable."""
    makkah_info = sermon_data.get("makkah", {}) or {}
    madinah_info = sermon_data.get("madinah", {}) or {}
    
    makkah_imam = makkah_info.get("imam", "the Imam")
    madinah_imam = madinah_info.get("imam", "the Imam")
    
    return {
        "makkah_topic": "Friday Sermon",
        "makkah_summary": "Summary not available. Please listen to the recording for the full sermon.",
        "madinah_topic": "Friday Sermon",
        "madinah_summary": "Summary not available. Please listen to the recording for the full sermon.",
        "introduction": f"""Assalamu Alaikum wa Rahmatullahi wa Barakatuh,
        Welcome to this week's Friday Sermon Summary from the Two Holy Mosques.
        This week, the Friday prayers at Masjid al-Haram in Makkah were led by {makkah_imam}, 
        while Masjid an-Nabawi in Madinah was led by {madinah_imam}.
        The Friday sermon (khutbah) is a blessed opportunity for Muslims worldwide to receive 
        guidance and spiritual nourishment. We encourage you to listen to the full recordings 
        for the complete spiritual benefit.""",
        "makkah_bio": get_imam_bio(makkah_imam),
        "madinah_bio": get_imam_bio(madinah_imam),
        "makkah_imam": makkah_imam,
        "madinah_imam": madinah_imam
    }


def create_email_html(sermon_data: dict, ai_content: dict, unsubscribe_token: str) -> str:
    """Create the HTML email content."""
    
    makkah = sermon_data.get('makkah', {})
    madinah = sermon_data.get('madinah', {})
    
    makkah_imam = ai_content.get('makkah_imam', makkah.get('imam', 'Unknown Imam'))
    madinah_imam = ai_content.get('madinah_imam', madinah.get('imam', 'Unknown Imam'))
    
    makkah_topic = ai_content.get('makkah_topic', 'Friday Sermon')
    makkah_summary = ai_content.get('makkah_summary', '')
    madinah_topic = ai_content.get('madinah_topic', 'Friday Sermon')
    madinah_summary = ai_content.get('madinah_summary', '')
    intro_html = ai_content.get('introduction', f"Welcome to this week's Friday Sermon Summary.")

    unsubscribe_link = f"{WEBSITE_BASE_URL}/unsubscribe?token={unsubscribe_token}"
    subscribe_link = f"{WEBSITE_BASE_URL}/?utm_source=email&utm_medium=forward&utm_campaign=weekly"
    # Pre-built share text for the "forward to a friend" buttons
    from urllib.parse import quote as _q
    forward_subject = _q("Friday Sermon Summary — Masjid al-Haram & Masjid an-Nabawi")
    forward_body = _q(f"Assalamu Alaikum,\n\nThought you'd appreciate this week's Friday sermon "
                      f"summary from the Two Holy Mosques. Subscribe (free) here:\n{subscribe_link}\n")
    whatsapp_share = _q(f"Friday sermon summary from Masjid al-Haram & Masjid an-Nabawi — subscribe for weekly emails: {subscribe_link}")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; }}
            .header {{ background-color: #0d5c3f; color: #ffffff; padding: 30px 20px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: normal; letter-spacing: 1px; }}
            .content {{ padding: 30px 20px; }}
            .mosque-section {{ margin-bottom: 35px; border-bottom: 1px solid #eee; padding-bottom: 25px; }}
            .mosque-section:last-child {{ border-bottom: none; }}
            .mosque-title {{ color: #0d5c3f; font-size: 18px; font-weight: bold; margin-bottom: 15px; display: flex; align-items: center; }}
            .mosque-icon {{ margin-right: 10px; font-size: 24px; }}
            .imam-name {{ font-weight: bold; color: #555; margin-bottom: 10px; display: block; }}
            .sermon-topic {{ color: #c89d2a; font-size: 16px; margin-bottom: 10px; font-weight: bold; }}
            .summary-text {{ color: #444; font-size: 15px; text-align: left; }}
            .footer {{ background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #ddd; }}
            .footer a {{ color: #0d5c3f; text-decoration: none; }}
            .rtl {{ direction: rtl; text-align: right; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #1a5f3c; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="margin: 0; font-size: 24px;">🕌 Haramain Fridays</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Weekly Sermon Summary</p>
            </div>
        
            <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            
            <p style="font-size: 16px; line-height: 1.6;">Assalamu Alaikum wa Rahmatullahi wa Barakatuh,</p>
            {intro_html}
            
            <hr style="border: none; border-top: 2px solid #1a5f3c; margin: 30px 0;">
            
            <!-- Makkah Section -->
            <div style="margin-bottom: 35px;">
                <h2 style="color: #1a5f3c; font-size: 22px; margin-bottom: 5px;">
                    🕋 Masjid al-Haram, Makkah
                </h2>
                <p style="font-size: 14px; color: #666; margin: 5px 0;">
                    <strong>Imam:</strong> {ai_content.get('makkah_imam', 'Unknown')}
                </p>
                <p style="font-size: 14px; color: #1a5f3c; margin: 5px 0 15px 0;">
                    <strong>Topic:</strong> <em>{makkah_topic}</em>
                </p>
                
                <div style="background: #f8f9f8; padding: 20px; border-left: 4px solid #1a5f3c; margin: 15px 0; border-radius: 0 8px 8px 0;">
                    <h3 style="color: #1a5f3c; margin: 0 0 10px 0; font-size: 16px;">Sermon Summary</h3>
                    <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #444;">
                        {makkah_summary if makkah_summary else 'Summary not available. Please listen to the recording for the full sermon.'}
                    </p>
                </div>
                
                <div style="background: #f0f4f0; padding: 15px; margin: 15px 0; border-radius: 8px;">
                    <h4 style="color: #1a5f3c; margin: 0 0 8px 0; font-size: 14px;">About the Imam</h4>
                    <p style="font-style: italic; margin: 0; font-size: 13px; line-height: 1.5; color: #555;">
                        {ai_content.get('makkah_bio', '')}
                    </p>
                </div>
                
                {f'<p style="margin-top: 15px;"><a href="{makkah.get("link", "#")}" style="color: #1a5f3c; font-weight: bold;">🎧 Listen to Full Recording →</a></p>' if makkah.get("link") else ''}
            </div>
            
            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
            
            <!-- Madinah Section -->
            <div style="margin-bottom: 30px;">
                <h2 style="color: #1a5f3c; font-size: 22px; margin-bottom: 5px;">
                    🌙 Masjid an-Nabawi, Madinah
                </h2>
                <p style="font-size: 14px; color: #666; margin: 5px 0;">
                    <strong>Imam:</strong> {ai_content.get('madinah_imam', 'Unknown')}
                </p>
                <p style="font-size: 14px; color: #1a5f3c; margin: 5px 0 15px 0;">
                    <strong>Topic:</strong> <em>{madinah_topic}</em>
                </p>
                
                <div style="background: #f8f9f8; padding: 20px; border-left: 4px solid #1a5f3c; margin: 15px 0; border-radius: 0 8px 8px 0;">
                    <h3 style="color: #1a5f3c; margin: 0 0 10px 0; font-size: 16px;">Sermon Summary</h3>
                    <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #444;">
                        {madinah_summary if madinah_summary else 'Summary not available. Please listen to the recording for the full sermon.'}
                    </p>
                </div>
                
                <div style="background: #f0f4f0; padding: 15px; margin: 15px 0; border-radius: 8px;">
                    <h4 style="color: #1a5f3c; margin: 0 0 8px 0; font-size: 14px;">About the Imam</h4>
                    <p style="font-style: italic; margin: 0; font-size: 13px; line-height: 1.5; color: #555;">
                        {ai_content.get('madinah_bio', '')}
                    </p>
                </div>
                
                {f'<p style="margin-top: 15px;"><a href="{madinah.get("link", "#")}" style="color: #1a5f3c; font-weight: bold;">🎧 Listen to Full Recording →</a></p>' if madinah.get("link") else ''}
            </div>
            
            <hr style="border: none; border-top: 2px solid #1a5f3c; margin: 30px 0;">

            <!-- Forward + Subscribe CTA — gives recipients an obvious way to share
                 the email with friends/family, and for forwarded copies, a clear
                 path to subscribe. Single biggest lever for organic growth. -->
            <div style="background: #f0f4f0; padding: 22px; border-radius: 10px; text-align: center; margin: 25px 0;">
                <h3 style="color: #1a5f3c; margin: 0 0 8px 0; font-size: 17px;">📨 Found this beneficial?</h3>
                <p style="margin: 0 0 16px 0; color: #555; font-size: 14px;">Forward to someone who would appreciate it. Each share is sadaqah jariyah, in shaa Allah.</p>
                <div style="margin-bottom: 14px;">
                    <a href="https://wa.me/?text={whatsapp_share}"
                       style="display: inline-block; background: #25D366; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 4px;">💬 Share on WhatsApp</a>
                    <a href="mailto:?subject={forward_subject}&body={forward_body}"
                       style="display: inline-block; background: #1a5f3c; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 4px;">✉️ Forward by Email</a>
                </div>
                <p style="margin: 12px 0 0 0; font-size: 13px; color: #777;">
                    Were you forwarded this email? <a href="{subscribe_link}" style="color: #1a5f3c; font-weight: 600;">Subscribe to receive it weekly →</a>
                </p>
            </div>

            <div style="text-align: center; padding: 20px 0;">
                <p style="color: #1a5f3c; font-size: 16px; margin: 0;">
                    <em>"And remind, for indeed, the reminder benefits the believers."</em>
                </p>
                <p style="color: #888; font-size: 12px; margin: 10px 0 0 0;">— Surah Adh-Dhariyat (51:55)</p>
            </div>
            
            <p style="text-align: center; color: #888; font-size: 14px; margin-top: 20px;">
                May Allah accept our prayers and grant us beneficial knowledge.<br>
                <strong style="color: #1a5f3c;">Jumu'ah Mubarak! 🤲</strong>
            </p>
            
            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 25px 0 15px 0;">
            
            <p style="text-align: center; color: #aaa; font-size: 11px;">
                This weekly summary is generated using AI to aggregate sermon information.<br>
                Audio recordings sourced from <a href="http://www.haramain.info" style="color: #1a5f3c;">haramain.info</a>
            </p>
        </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_email_to_subscriber(html_content: str, email: str, token: str = None, subject: str = None) -> bool:
    """Send the email to a single subscriber.

    If `subject` is provided, it overrides the default. --auto mode uses this
    so the subject reflects the target Friday rather than the run date.
    """
    if not all([SMTP_EMAIL, SMTP_PASSWORD]):
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject or f"🕌 Friday Sermon Summary - {datetime.now().strftime('%B %d, %Y')}"
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        
        # Plain text fallback
        text_content = "Friday Sermon Summary - Please view this email in an HTML-compatible email client."
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, email, msg.as_string())
        
        return True
        
    except Exception as e:
        print(f"    Error sending to {email}: {e}")
        return False


def create_email_with_unsubscribe(sermon_data: dict, ai_content: dict, token: str = None) -> str:
    """Create email HTML with optional unsubscribe link."""
    html = create_email_html(sermon_data, ai_content, token)
    
    # Add unsubscribe link if token provided
    if token:
        unsubscribe_html = f"""
            <p style="text-align: center; color: #999; font-size: 11px; margin-top: 15px;">
                <a href="{WEBSITE_BASE_URL}/unsubscribe?token={token}" style="color: #999;">Unsubscribe</a>
            </p>
        </div>
    </body>
    </html>
        """
        # Replace the closing tags with unsubscribe link + closing tags
        html = html.replace('</div>\n    </body>\n    </html>', unsubscribe_html)
    
    return html



def _git_sync_archive(archive_path: str, date_str: str):
    """Commit + push the archive JSON mirror so git never drifts from Firestore.

    Firestore is canonical and the live site reads it directly, so this is
    purely housekeeping for the git backup. It is therefore best-effort:
    every step is fenced and logged, and nothing here can raise into — or
    slow down past a hard timeout — the weekly email tick. If the push
    fails (e.g. launchd can't reach the keychain, or the branch is behind),
    we log it and move on; the next successful run or a manual push catches
    up.
    """
    import subprocess
    import shutil

    repo_dir = os.path.dirname(os.path.abspath(__file__))
    git = shutil.which("git")
    if not git:
        print("  ⚠️ git not found on PATH — skipping archive auto-commit")
        return

    def run(args, **kw):
        # GIT_TERMINAL_PROMPT=0 so a missing credential never hangs the tick.
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        return subprocess.run([git, *args], cwd=repo_dir, env=env,
                              capture_output=True, text=True, timeout=60, **kw)

    rel = os.path.relpath(archive_path, repo_dir)
    try:
        # Nothing changed vs HEAD? Then there's nothing to sync.
        if run(["diff", "--quiet", "HEAD", "--", rel]).returncode == 0:
            return
        # Commit only the archive pathspec — never sweep up unrelated edits.
        msg = f"Auto-sync sermon archive for {date_str}"
        c = run(["commit", "-m", msg, "--", rel])
        if c.returncode != 0:
            print(f"  ⚠️ archive auto-commit failed: {c.stderr.strip() or c.stdout.strip()}")
            return
        print(f"  ✓ archive auto-committed ({rel})")
        p = run(["push", "origin", "HEAD"])
        if p.returncode == 0:
            print(f"  ✓ archive pushed to origin")
        else:
            print(f"  ⚠️ archive push failed (committed locally): "
                  f"{p.stderr.strip() or p.stdout.strip()}")
    except subprocess.TimeoutExpired:
        print("  ⚠️ git archive sync timed out — skipped")
    except Exception as e:
        print(f"  ⚠️ git archive sync error: {e}")


def save_to_archive(sermon_data: dict, ai_content: dict, target_date_str: str = None,
                    auto_commit: bool = False):
    """Save this week's sermon data to the archive.

    Source of truth is the Firestore `archive/all` document — that's what
    the live website reads, so writes show up instantly without a Vercel
    redeploy. The local website/sermons_archive.json file is updated in
    parallel as a backup / fallback for offline server runs.

    When `auto_commit` is True (production send paths), the JSON mirror is
    also committed + pushed to git so the backup never drifts. Best-effort:
    git failures are logged, never raised. Off by default so tests and
    manual backfills don't push.

    `target_date_str` ("YYYY-MM-DD") should be the Friday the sermon was
    delivered. If omitted, falls back to today's date for backwards
    compatibility — but note that running the archive write on Saturday
    (e.g. via --auto catch-up) without this argument will mis-date the
    entry to the run date.
    """
    archive_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website", "sermons_archive.json")
    date_str = target_date_str or datetime.now().strftime("%Y-%m-%d")

    # ---- Load current archive (Firestore preferred, file fallback) ----
    archive = None
    if db is not None:
        try:
            snap = db.collection('archive').document('all').get()
            if snap.exists:
                d = snap.to_dict() or {}
                archive = {
                    "sermons": d.get("sermons", []),
                    "imams": d.get("imams", {}),
                    "last_updated": d.get("last_updated", ""),
                }
        except Exception as e:
            print(f"  ⚠️ Firestore archive read failed: {e}")

    if archive is None:
        if os.path.exists(archive_path):
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive = json.load(f)
        else:
            archive = {"sermons": [], "imams": {}, "last_updated": ""}

    # ---- Build new entries (per-(date, mosque) dedup) ----
    existing_keys = {(s["date"], s["mosque"]) for s in archive["sermons"]}
    added = 0
    for mosque_key in ["makkah", "madinah"]:
        if (date_str, mosque_key) in existing_keys:
            continue

        data = sermon_data.get(mosque_key, {})
        if not data:
            continue

        imam_name = data.get("imam", "Unknown Imam")
        imam_key = get_imam_key(imam_name) or "unknown"

        # generate_ai_content returns flat keys; build_archive.py uses nested.
        # Accept both so this is the one place that knows about the format.
        nested = ai_content.get(mosque_key) or {}
        topic = (
            ai_content.get(f"{mosque_key}_topic")
            or nested.get("topic")
            or "Friday Sermon"
        )
        summary = (
            ai_content.get(f"{mosque_key}_summary")
            or nested.get("summary")
            or f"Friday sermon delivered at {mosque_key}."
        )

        sermon_entry = {
            "date": date_str,
            "mosque": mosque_key,
            "imam_key": imam_key,
            "imam_name": IMAM_BIOS.get(imam_key, {}).get("name", imam_name),
            "topic": topic,
            "summary": summary,
            "audio_url": data.get("audio_url", data.get("link", "")),
            "page_url": data.get("page_url", data.get("link", ""))
        }
        archive["sermons"].append(sermon_entry)
        added += 1

    if added == 0:
        print(f"  ⚠️ Archive already has entries for {date_str} (both mosques), skipping.")
        return

    archive["last_updated"] = datetime.now().isoformat()
    archive["sermons"].sort(key=lambda x: (x["date"], x["mosque"]))

    # ---- Write to Firestore (canonical) ----
    if db is not None:
        try:
            db.collection('archive').document('all').set({
                "sermons": archive["sermons"],
                "imams": archive["imams"],
                "last_updated": archive["last_updated"],
            })
            print(f"  ✓ Wrote {added} entry/entries for {date_str} to Firestore archive/all "
                  f"({len(archive['sermons'])} total)")
        except Exception as e:
            print(f"  ⚠️ Firestore archive write failed: {e}")

    # ---- Mirror to JSON file (backup) ----
    mirror_ok = False
    try:
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(archive, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Mirrored archive to {archive_path}")
        mirror_ok = True
    except Exception as e:
        print(f"  ⚠️ Failed to mirror archive to JSON file: {e}")

    # ---- Auto-commit the mirror so git never drifts from Firestore ----
    if auto_commit and mirror_ok:
        _git_sync_archive(archive_path, date_str)


def save_draft(sermon_data: dict, ai_content: dict) -> str:
    """Save sermon data as a draft in Firestore and return an approval token."""
    import uuid
    if not db:
        print("Error: Database connection not established for saving draft.")
        return None
        
    today = datetime.now().strftime("%Y-%m-%d")
    token = str(uuid.uuid4())
    
    draft_data = {
        'id': today,
        'sermon_data': sermon_data,
        'ai_content': ai_content,
        'status': 'pending',
        'token': token,
        'created_at': datetime.now().isoformat()
    }
    
    try:
        db.collection('drafts').document(today).set(draft_data)
        print(f"  ✓ Draft saved for {today}")
        return token
    except Exception as e:
        print(f"  ⚠️ Failed to save draft: {e}")
        return None

def get_draft(date_str: str) -> dict:
    """Get a draft from Firestore."""
    if not db:
        return None
    try:
        doc = db.collection('drafts').document(date_str).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"  ⚠️ Failed to get draft: {e}")
    return None

def update_draft_status(date_str: str, status: str):
    """Update the status of a draft in Firestore."""
    if not db:
        return
    try:
        db.collection('drafts').document(date_str).update({'status': status})
    except Exception as e:
        print(f"  ⚠️ Failed to update draft status: {e}")


# ---------------------------------------------------------------------------
# --auto mode: state-machine driven, idempotent, hourly retry
# ---------------------------------------------------------------------------

# Tunables for --auto
AUTO_REVIEWER_EMAIL = "mjeelani@gmail.com"
AUTO_MAX_REMINDERS = 5            # max reminder emails after the initial draft email
AUTO_REMINDER_INTERVAL_HOURS = 2  # hours between reminders


def _target_friday(now: datetime = None):
    """Return the date of the most recent Friday (today if today is Friday).

    All --auto reads/writes key by this date in YYYY-MM-DD form so a
    Saturday-morning catch-up tick still operates on Friday's sermon.
    """
    from datetime import date as _date_type
    if now is None:
        now = datetime.now()
    # Python: Monday=0 ... Friday=4 ... Sunday=6
    days_back = (now.weekday() - 4) % 7
    return (now - timedelta(days=days_back)).date()


def save_draft_atomic(date_str: str, sermon_data: dict, ai_content: dict) -> str:
    """Idempotent draft save using a Firestore transaction.

    - If no doc exists at drafts/<date_str>, create it (status=pending) and
      return the new token.
    - If a doc already exists, NEVER overwrite it. If status is `pending`,
      return the existing token (so retries email the same approval link).
      If status is in {approved, sending, sent}, return None (caller should
      treat as "another tick handled this; do nothing").

    This is what stops a stray --draft / --auto run from clobbering a
    `sent` doc the way our test did to 2026-05-09 earlier today.
    """
    import uuid
    if not db:
        print("Error: Database connection not established for saving draft.")
        return None

    ref = db.collection('drafts').document(date_str)
    transaction = db.transaction()

    @firestore.transactional
    def _run(tx):
        snap = ref.get(transaction=tx)
        if snap.exists:
            existing = snap.to_dict() or {}
            status = existing.get('status')
            if status == 'pending':
                return existing.get('token')  # reuse so links keep working
            return None  # approved/sending/sent — leave untouched
        # Create fresh
        token = str(uuid.uuid4())
        tx.set(ref, {
            'id': date_str,
            'sermon_data': sermon_data,
            'ai_content': ai_content,
            'status': 'pending',
            'token': token,
            'created_at': datetime.now().isoformat(),
            'reminder_count': 0,
            'last_reminder_at': None,
        })
        return token

    try:
        return _run(transaction)
    except Exception as e:
        print(f"  ⚠️ save_draft_atomic failed: {e}")
        return None


def claim_send_lock(date_str: str) -> bool:
    """Atomically transition status `approved` → `sending`.

    Returns True only if THIS process won the race. Concurrent ticks (or a
    future Vercel-cron runner) will see `sending`/`sent` and bail out, so
    subscribers never get duplicate emails.
    """
    if not db:
        return False
    ref = db.collection('drafts').document(date_str)
    transaction = db.transaction()

    @firestore.transactional
    def _run(tx):
        snap = ref.get(transaction=tx)
        if not snap.exists:
            return False
        if (snap.to_dict() or {}).get('status') != 'approved':
            return False
        tx.update(ref, {
            'status': 'sending',
            'sending_started_at': datetime.now().isoformat(),
        })
        return True

    try:
        return _run(transaction)
    except Exception as e:
        print(f"  ⚠️ claim_send_lock failed: {e}")
        return False


def _build_reviewer_email(target_date_str: str, sermon_data: dict, ai_content: dict, token: str) -> str:
    """Build the draft-review HTML (same as legacy --draft path)."""
    approval_link = f"https://www.haramainfridays.com/api/approve_draft?date={target_date_str}&token={token}"
    html_content = create_email_html(sermon_data, ai_content, None)
    draft_notice = f"""
    <div style="background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 15px; margin-bottom: 20px; border-radius: 5px; text-align: center;">
        <h3 style="margin-top: 0;">📝 Draft Review</h3>
        <p>Please review the summary below. If everything looks good, approve it so it can be sent to all subscribers.</p>
        <a href="{approval_link}" style="display: inline-block; background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px;">Approve Draft</a>
    </div>
    """
    return html_content.replace('<body>', f'<body>\n{draft_notice}')


def _send_admin_alert(subject: str, body_text: str):
    """Plain-text alert to the reviewer (used for 'no publish' notice)."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_EMAIL
        msg['To'] = AUTO_REVIEWER_EMAIL
        msg.attach(MIMEText(body_text, 'plain'))
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, AUTO_REVIEWER_EMAIL, msg.as_string())
    except Exception as e:
        print(f"  ⚠️ Failed to send admin alert: {e}")


def run_auto_tick():
    """One iteration of the Friday email state machine. Idempotent.

    Cron this hourly; whatever state we're in, the right thing happens
    (or nothing happens) and the script exits.
    """
    now = datetime.now()
    tf = _target_friday(now)
    tf_str = tf.strftime("%Y-%m-%d")
    print(f"[auto-tick {now.strftime('%Y-%m-%d %H:%M')}] target_friday={tf_str}")

    if not db:
        print("  ⚠️ No Firestore connection — bailing.")
        return

    draft = get_draft(tf_str)
    status = (draft or {}).get('status')

    # ---- Terminal states: nothing to do ----
    if status == 'sent':
        print(f"  status=sent → noop")
        return
    if status == 'sending':
        print(f"  status=sending (another tick is mid-send) → noop")
        return

    # ---- Approved: send to all subscribers under an atomic lock ----
    if status == 'approved':
        if not claim_send_lock(tf_str):
            print(f"  could not claim send lock (race) → noop")
            return
        sermon_data = draft.get('sermon_data', {}) or {}
        ai_content = draft.get('ai_content', {}) or {}

        subscribers = load_subscribers()
        if not subscribers:
            print(f"  ⚠️ No subscribers found. Reverting status to approved.")
            update_draft_status(tf_str, 'approved')
            return

        nice_date = tf.strftime('%B %d, %Y')
        subject = f"🕌 Friday Sermon Summary - {nice_date}"
        sent_count = 0
        print(f"  sending to {len(subscribers)} subscriber(s) for {tf_str}...")
        for sub in subscribers:
            email = sub.get('email')
            sub_token = sub.get('token', '')
            html = create_email_with_unsubscribe(sermon_data, ai_content, sub_token)
            if send_email_to_subscriber(html, email, sub_token, subject=subject):
                sent_count += 1

        update_draft_status(tf_str, 'sent')
        try:
            db.collection('drafts').document(tf_str).update({
                'sent_at': datetime.now().isoformat(),
                'sent_count': sent_count,
            })
        except Exception:
            pass
        try:
            save_to_archive(sermon_data, ai_content, target_date_str=tf_str, auto_commit=True)
        except Exception as e:
            print(f"  ⚠️ archive save failed: {e}")
        print(f"  ✓ sent {sent_count}/{len(subscribers)} → status=sent")
        return

    # ---- Pending: maybe nudge reviewer with a reminder ----
    if status == 'pending':
        reminder_count = int(draft.get('reminder_count') or 0)
        last_at_str = draft.get('last_reminder_at') or draft.get('created_at')
        try:
            last_at = datetime.fromisoformat(last_at_str)
        except Exception:
            last_at = now  # if unparseable, treat as just-now to defer

        hours_since = (now - last_at).total_seconds() / 3600.0
        if reminder_count >= AUTO_MAX_REMINDERS:
            print(f"  status=pending reminder_count={reminder_count} (max reached) → noop")
            return
        if hours_since < AUTO_REMINDER_INTERVAL_HOURS:
            print(f"  status=pending reminder_count={reminder_count} hours_since={hours_since:.1f} → too soon, noop")
            return

        token = draft.get('token')
        sermon_data = draft.get('sermon_data', {}) or {}
        ai_content = draft.get('ai_content', {}) or {}
        html = _build_reviewer_email(tf_str, sermon_data, ai_content, token)
        # Prepend a "this is a reminder" banner so the reviewer notices.
        reminder_banner = (
            f"<div style=\"background:#f8d7da;border:1px solid #f5c2c7;color:#842029;"
            f"padding:12px;margin:0 0 10px 0;border-radius:5px;text-align:center;\">"
            f"⏰ Reminder {reminder_count + 1}/{AUTO_MAX_REMINDERS}: "
            f"please review &amp; approve so subscribers can receive this week's sermon."
            f"</div>"
        )
        html = html.replace('<body>', f'<body>\n{reminder_banner}')
        subject = f"⏰ Reminder ({reminder_count + 1}/{AUTO_MAX_REMINDERS}): Approve Friday Sermon Draft - {tf.strftime('%B %d, %Y')}"
        if send_email_to_subscriber(html, AUTO_REVIEWER_EMAIL, None, subject=subject):
            try:
                db.collection('drafts').document(tf_str).update({
                    'reminder_count': reminder_count + 1,
                    'last_reminder_at': now.isoformat(),
                })
                print(f"  ✓ reminder {reminder_count + 1}/{AUTO_MAX_REMINDERS} sent")
            except Exception as e:
                print(f"  ⚠️ reminder bookkeeping failed: {e}")
        else:
            print(f"  ⚠️ failed to send reminder")
        return

    # ---- No draft yet: try to fetch this Friday's sermons ----
    print(f"  no draft for {tf_str} — checking YouTube (haramain.info fallback)...")
    sermon_data = fetch_khutbah_data_any(tf)
    have_makkah = bool(sermon_data.get('makkah'))
    have_madinah = bool(sermon_data.get('madinah'))

    if not (have_makkah and have_madinah):
        # Saturday after noon = both sermons should certainly be up by now.
        # Send a one-time "no email going out" alert.
        is_saturday_after_noon = now.weekday() == 5 and now.hour >= 12
        if is_saturday_after_noon:
            try:
                # Mark in Firestore so we only alert once per week.
                alert_ref = db.collection('drafts').document(tf_str + '__no_publish_alert')
                if not alert_ref.get().exists:
                    _send_admin_alert(
                        subject=f"⚠️ Haramain Fridays: no sermon published for {tf_str}",
                        body_text=(
                            f"Heads up — by Saturday noon, haramain.info still hasn't posted "
                            f"both sermons for {tf_str}.\n"
                            f"  Makkah available: {have_makkah}\n"
                            f"  Madinah available: {have_madinah}\n\n"
                            f"No subscriber email will go out this week unless both appear later "
                            f"and a draft gets approved before subscribers expect it.\n"
                        ),
                    )
                    alert_ref.set({'created_at': now.isoformat()})
                    print(f"  ⚠️ Saturday noon escalation: alert sent")
            except Exception as e:
                print(f"  ⚠️ no-publish alert flow failed: {e}")
        else:
            print(f"  not yet available (makkah={have_makkah}, madinah={have_madinah}) → wait")
        return

    # ---- Both sermons posted: fetch AI, save draft, email reviewer ----
    print(f"  ✓ both sermons posted, generating AI content...")
    ai_content = generate_ai_content(sermon_data)
    if ai_content.pop('ai_failed', False):
        # Transient Gemini failure (timeout, parse error, ...). Don't save a
        # draft with placeholder/blank summaries — the hourly tick retries.
        # (With no GEMINI_API_KEY at all, the flag is never set and the
        # plain fallback content still flows through as before.)
        print(f"  ⚠️ AI summarisation failed — not saving draft, will retry next tick")
        return
    token = save_draft_atomic(tf_str, sermon_data, ai_content)
    if not token:
        print(f"  another tick beat us to it (or status moved past pending) → noop")
        return

    html = _build_reviewer_email(tf_str, sermon_data, ai_content, token)
    subject = f"📝 Draft: Friday Sermon Summary - {tf.strftime('%B %d, %Y')} (review & approve)"
    if send_email_to_subscriber(html, AUTO_REVIEWER_EMAIL, None, subject=subject):
        print(f"  ✓ draft saved + review email sent to {AUTO_REVIEWER_EMAIL}")
    else:
        print(f"  ⚠️ draft saved but review email failed to send")


def main():
    import sys
    
    # Check for Mode
    is_draft_mode = '--draft' in sys.argv
    is_send_mode = '--send' in sys.argv
    is_auto_mode = '--auto' in sys.argv

    if not (is_draft_mode or is_send_mode or is_auto_mode):
        print("Please specify --auto (recommended, hourly cron), --draft, or --send.")
        print("Usage: python3 friday_sermon_email.py [--auto | --draft | --send]")
        return

    if is_auto_mode:
        run_auto_tick()
        return
    
    print("=" * 60)
    print("🕌 Haramain Fridays - Friday Sermon Email Automation")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'📝 DRAFT (mjeelani@gmail.com only)' if is_draft_mode else '🚀 SEND (All Subscribers)'}")
    print("=" * 60)
    
    today = datetime.now().strftime("%Y-%m-%d")

    if is_draft_mode:
        print("\n[1/4] Fetching sermon data (YouTube, haramain.info fallback)...")
        sermon_data = fetch_khutbah_data_any(_target_friday(datetime.now()))
        print(f"  Makkah: {sermon_data.get('makkah', {}).get('imam', 'Unknown')} ({sermon_data.get('makkah', {}).get('link', 'No Link')})")
        print(f"  Madinah: {sermon_data.get('madinah', {}).get('imam', 'Unknown')} ({sermon_data.get('madinah', {}).get('link', 'No Link')})")
        
        print("\n[2/4] Generating AI summaries...")
        ai_content = generate_ai_content(sermon_data)
        if ai_content.pop('ai_failed', False):
            print("  ⚠️ AI summarisation failed — draft will contain placeholder summaries")
        else:
            print("  ✓ Content generated")
        
        print("\n[3/4] Saving Draft...")
        token = save_draft(sermon_data, ai_content)
        
        if not token:
            print("Failed to save draft. Exiting.")
            return
            
        print("\n[4/4] Sending draft email for review...")
        approval_link = f"https://www.haramainfridays.com/api/approve_draft?date={today}&token={token}"
        
        # Prepend an approval box to the email for the draft
        html_content = create_email_html(sermon_data, ai_content, None)
        draft_notice = f"""
        <div style="background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 15px; margin-bottom: 20px; border-radius: 5px; text-align: center;">
            <h3 style="margin-top: 0;">📝 Draft Review</h3>
            <p>Please review the summary below. If everything looks good, approve it so it can be sent at 6 PM.</p>
            <a href="{approval_link}" style="display: inline-block; background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px;">Approve Draft</a>
        </div>
        """
        html_content = html_content.replace('<body>', f'<body>\n{draft_notice}')
        
        # Send only to the reviewer
        if send_email_to_subscriber(html_content, "mjeelani@gmail.com", None):
            print("  ✓ Draft email sent to mjeelani@gmail.com")
        else:
            print("  ⚠️ Failed to send draft email.")
            
    elif is_send_mode:
        print(f"\n[1/5] Checking for approved draft for {today}...")
        draft = get_draft(today)
        
        if not draft:
            print("  ⚠️ No draft found for today. Exiting.")
            return
            
        status = draft.get('status')
        if status != 'approved':
            print(f"  ⚠️ Draft status is '{status}', not 'approved'. Aborting send.")
            
            # Optional: Send a notification that it was aborted
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"⚠️ Friday Sermon Send Aborted"
            msg['From'] = SMTP_EMAIL
            msg['To'] = "mjeelani@gmail.com"
            msg.attach(MIMEText(f"The 6 PM Friday Sermon email blast was aborted because the draft ({today}) was not approved. Current status: {status}.", 'plain'))
            
            try:
                context = ssl.create_default_context()
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls(context=context)
                    server.login(SMTP_EMAIL, SMTP_PASSWORD)
                    server.sendmail(SMTP_EMAIL, "mjeelani@gmail.com", msg.as_string())
            except Exception as e:
                pass
            return
            
        print("  ✓ Draft is approved.")
        
        sermon_data = draft.get('sermon_data', {})
        ai_content = draft.get('ai_content', {})
        
        print("\n[2/5] Loading active subscribers...")
        subscribers = load_subscribers()
        
        if not subscribers:
            print("No subscribers found. Exiting.")
            return
            
        print(f"  ✓ Found {len(subscribers)} active subscriber(s)")
        
        print("\n[3/5] Sending emails to all subscribers...")
        sent_count = 0
        
        for sub in subscribers:
            email = sub.get('email')
            token = sub.get('token', '')
            
            # Create HTML content
            html_content = create_email_with_unsubscribe(sermon_data, ai_content, token)
            
            # Send
            if send_email_to_subscriber(html_content, email, token):
                sent_count += 1
                
        print(f"\n[4/5] Marking draft as sent...")
        update_draft_status(today, 'sent')
        
        print("\n[5/5] Saving to sermon archive...")
        save_to_archive(sermon_data, ai_content, target_date_str=today, auto_commit=True)
                
        # Summary
        print("\n" + "=" * 60)
        print(f"✓ Completed: {sent_count}/{len(subscribers)} emails sent successfully")
        print("=" * 60)

if __name__ == "__main__":
    main()

