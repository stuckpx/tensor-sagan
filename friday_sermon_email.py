#!/usr/bin/env python3
"""
Friday Sermon Email Automation
Fetches Friday khutbah information from Makkah and Medina grand mosques,
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
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
FIREBASE_CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harmainfridays-firebase-adminsdk-fbsvc-c21f19e297.json')

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
    "thubayti": {
        "name": "Sheikh Salah Al-Budair",
        "bio": "Sheikh Salah bin Muhammad Al-Budair is an Imam of Masjid an-Nabawi in Madinah. He is known for his beautiful voice and emotional delivery. He holds a PhD in Islamic Studies and serves as a judge in the Madinah courts alongside his duties as Imam."
    },
    "muhanna": {
        "name": "Sheikh Khalid Al-Muhanna",
        "bio": "Sheikh Khalid bin Sulaiman Al-Muhanna is an Imam of Masjid an-Nabawi, appointed in 1441 AH (2019). He is a respected scholar and faculty member at the Islamic University of Madinah. Known for his clear and precise recitation, he brings a deep scholarly background to his position at the Prophet's Mosque."
    },
}


def get_imam_key(imam_name: str) -> str:
    """Match an imam name to our database key."""
    name_lower = imam_name.lower()
    
    # Direct keyword matching
    keywords = {
        "sudais": "sudais",
        "shuraim": "shuraim",
        "muaiqly": "muaiqly",
        "mu'aiqly": "muaiqly",
        "moaiqly": "muaiqly",
        "juhany": "juhany",
        "juhani": "juhany",
        "baleelah": "baleelah",
        "balilah": "baleelah",
        "dawsari": "dawsari",
        "dosari": "dawsari",
        "ghazzawi": "ghazzawi",
        "gazzawi": "ghazzawi",
        "humaid": "humaid",
        "khayyat": "khayyat",
        "khayat": "khayyat",
        "hudhaify": "hudhaify",
        "hudaifi": "hudhaify",
        "qasim": "qasim",
        "budair": "thubayti",
        "budayr": "thubayti",
        "budayr": "thubayti",
        "thubaity": "thubayti",
        "muhanna": "muhanna",
    }
    
    for keyword, key in keywords.items():
        if keyword in name_lower:
            return key
    
    return None


def fetch_khutbah_data() -> dict:
    """Fetch the latest Friday khutbah information from haramain.info."""
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
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                
                if date_match:
                    year = int(date_match.group(1))
                    # Default month from URL (archive month)
                    month = int(date_match.group(2))
                    
                    # Try to extract REAL month and day from slug
                    # e.g. makkah-jumuah-30th-january-2026.html
                    slug_match = re.search(r'-(\d{1,2})(?:st|nd|rd|th)?-([a-z]+)-(\d{4})', href.lower())
                    
                    if slug_match:
                        # Use the extracted date from the slug as it's the actual event date
                        day = int(slug_match.group(1))
                        month_str = slug_match.group(2)
                        year = int(slug_match.group(3))
                        if month_str in month_map:
                            month = month_map[month_str]
                    else:
                        # Fallback to just day extraction if full pattern fails
                        day_match = re.search(r'-(\d{1,2})(?:st|nd|rd|th)?-', href.lower())
                        if day_match:
                            day = int(day_match.group(1))

                sort_key = (year, month, day)

                if 'makkah' in href.lower() or 'makkah' in text:
                    makkah_candidates.append({'href': href, 'date': sort_key})
                elif 'madeenah' in href.lower() or 'madinah' in href.lower() or 'madinah' in text:
                    madinah_candidates.append({'href': href, 'date': sort_key})

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
        
        # Try extracting from page body if not found
        if imam_name == "Unknown Imam":
            # Look for imam name in page content - restrict to post body if possible
            content_div = soup.find('div', class_='post-body') or soup.find('div', class_='entry-content')
            
            if content_div:
                # 1. Check Text
                body_text = content_div.get_text()
                imam_name = extract_imam_from_text(body_text)
                
                # 2. Check MP3 Links (common on this site)
                if imam_name == "Unknown Imam":
                    links = content_div.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '').lower()
                        if '.mp3' in href or 'audio' in href:
                            # Try to find imam key in the filename
                            key = get_imam_key(href)
                            if key and key in IMAM_BIOS:
                                imam_name = IMAM_BIOS[key]['name']
                                break
            else:
                body_text = soup.get_text() # Fallback to full text
                imam_name = extract_imam_from_text(body_text)
        
        return {
            "title": title_text,
            "link": url,
            "imam": imam_name,
            "mosque": mosque_name
        }



        
    except Exception as e:
        print(f"  Warning: Could not fetch sermon page {url}: {e}")
        return {
            "title": "Friday Sermon",
            "link": url,
            "imam": "Unknown Imam",
            "mosque": mosque_name
        }


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
        "dawsari": "Sheikh Yasir al-Dawsari",
        "dosari": "Sheikh Yasir al-Dawsari",
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
        "budair": "Sheikh Salah Al-Budair",
        "buayjan": "Sheikh Ahmad bin Taleb Hameed",
        "bu'ayjan": "Sheikh Ahmad bin Taleb Hameed",
        "thubayti": "Sheikh Saleh bin Muhammad Al-Thubayti",
        "thubaiti": "Sheikh Saleh bin Muhammad Al-Thubayti",
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


def generate_ai_content(sermon_data: dict) -> dict:
    """Generate sermon summaries using Gemini API."""
    if not GEMINI_API_KEY:
        return generate_fallback_content(sermon_data)
        
    makkah_imam = sermon_data.get('makkah', {}).get('imam', 'the Imam')
    madinah_imam = sermon_data.get('madinah', {}).get('imam', 'the Imam')
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    last_friday = datetime.now()
    # Adjust to find the most recent Friday
    days_since_friday = (last_friday.weekday() - 4) % 7
    last_friday -= timedelta(days=days_since_friday)
    
    date_str = last_friday.strftime('%B %d, %Y')
    
    prompt = f"""You are an expert on Friday sermons (khutbah) from the Two Holy Mosques in Makkah and Madinah.

Today is {date_str}. Generate authentic-style Friday sermon summaries for:

1. **Masjid al-Haram, Makkah** - Imam: {makkah_imam}
2. **Masjid an-Nabawi, Madinah** - Imam: {madinah_imam}

FOR EACH MOSQUE, provide:
- **topic**: A meaningful Islamic topic appropriate for this week
- **summary**: A detailed 4-6 sentence summary of the sermon's key messages, Quranic references, and lessons

Format your response ONLY as JSON (no markdown):
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

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        ai_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        sermon_content = parse_sermon_json(ai_text)
        
        return {
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
        
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return generate_fallback_content(sermon_data)


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
    except:
        # If JSON parsing fails, try to extract content manually
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

    # Using port 3000 as configured
    unsubscribe_link = f"http://localhost:3000/unsubscribe?token={unsubscribe_token}"
    
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
    </body>
    </html>
    """
    
    return html


def send_email_to_subscriber(html_content: str, email: str, token: str = None) -> bool:
    """Send the email to a single subscriber."""
    if not all([SMTP_EMAIL, SMTP_PASSWORD]):
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🕌 Friday Sermon Summary - {datetime.now().strftime('%B %d, %Y')}"
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
    html = create_email_html(sermon_data, ai_content)
    
    # Add unsubscribe link if token provided
    if token:
        unsubscribe_html = f"""
            <p style="text-align: center; color: #999; font-size: 11px; margin-top: 15px;">
                <a href="http://localhost:3000/unsubscribe?token={token}" style="color: #999;">Unsubscribe</a>
            </p>
        </div>
    </body>
    </html>
        """
        # Replace the closing tags with unsubscribe link + closing tags
        html = html.replace('</div>\n    </body>\n    </html>', unsubscribe_html)
    
    return html



def main():
    import sys
    
    # Check for Test Mode
    is_test_mode = len(sys.argv) > 1 and (sys.argv[1] == '--test' or sys.argv[1] == 'test')
    
    print("=" * 60)
    print("🕌 Haramain Fridays - Friday Sermon Email Automation")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'🧪 TEST (mjeelani@gmail.com only)' if is_test_mode else '🚀 PROD (All Subscribers)'}")
    print("=" * 60)
    
    # 1. Load Subscribers
    print("\n[1/5] Loading subscribers...")
    
    if is_test_mode:
        subscribers = [{'email': 'mjeelani@gmail.com', 'active': True, 'language': 'en'}]
        print(f"  ✓ Loaded 1 test subscriber")
    else:
        # Load from Firebase in Prod
        subscribers = load_subscribers()
        
    if not subscribers:
        print("No subscribers found. Exiting.")
        return
        
    print(f"  ✓ Found {len(subscribers)} active subscriber(s)")
    
    # 2. Fetch Sermon Data
    print("\n[2/5] Fetching sermon data from haramain.info...")
    sermon_data = fetch_khutbah_data()
    print(f"  Makkah: {sermon_data.get('makkah', {}).get('imam', 'Unknown')} ({sermon_data.get('makkah', {}).get('link', 'No Link')})")
    print(f"  Madinah: {sermon_data.get('madinah', {}).get('imam', 'Unknown')} ({sermon_data.get('madinah', {}).get('link', 'No Link')})")
    
    # 3. Generate AI Content
    print("\n[3/5] Generating AI summaries...")
    ai_content = generate_ai_content(sermon_data)
    print("  ✓ Content generated")
    
    # 4. Send Emails
    print("\n[4/5] Sending emails...")
    sent_count = 0
    
    for sub in subscribers:
        email = sub.get('email')
        token = sub.get('token', '')
        
        # Create HTML content
        html_content = create_email_html(sermon_data, ai_content, token)
        
        # Send
        if send_email_to_subscriber(html_content, email, token):
            sent_count += 1
            
    # Summary
    print("\n" + "=" * 60)
    print(f"✓ Completed: {sent_count}/{len(subscribers)} emails sent successfully")
    print("=" * 60)

if __name__ == "__main__":
    main()

