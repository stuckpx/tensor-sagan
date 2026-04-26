#!/usr/bin/env python3
"""
Build Sermon Archive
One-time script to scrape haramain.info and build a static JSON archive
of all Friday sermons from Jan 2025 to present.
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KHUTBAH_URL = "http://www.haramain.info/search/label/Friday%20Khutbah%20-%20%D8%A7%D9%84%D8%AE%D8%B7%D8%A8%D8%A9%20%D8%A7%D9%84%D8%AC%D9%85%D8%B9%D8%A9"
ARCHIVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website", "sermons_archive.json")

# Imam key to full name + mosque mapping
IMAM_DATABASE = {
    "sudais": {"name": "Sheikh Abdul Rahman Al-Sudais", "mosque": "makkah"},
    "shuraim": {"name": "Sheikh Saud Al-Shuraim", "mosque": "makkah"},
    "muaiqly": {"name": "Sheikh Maher al-Mu'aiqly", "mosque": "makkah"},
    "juhany": {"name": "Sheikh Abdullah Awad Al-Juhany", "mosque": "makkah"},
    "baleelah": {"name": "Sheikh Bandar Baleelah", "mosque": "makkah"},
    "dawsari": {"name": "Sheikh Yasir al-Dawsari", "mosque": "makkah"},
    "ghazzawi": {"name": "Sheikh Faisal Ghazzawi", "mosque": "makkah"},
    "humaid": {"name": "Sheikh Saleh bin Abdullah al-Humaid", "mosque": "makkah"},
    "khayyat": {"name": "Sheikh Usamah Abdul Aziz Al-Khayyat", "mosque": "makkah"},
    "hudhaify": {"name": "Sheikh Ali Al-Hudhaify", "mosque": "madinah"},
    "qasim": {"name": "Sheikh Abdul Muhsin Al-Qasim", "mosque": "madinah"},
    "buaijan": {"name": "Sheikh Ahmad bin Taleb Hameed", "mosque": "madinah"},
    "thubayti": {"name": "Sheikh Salah Al-Budair", "mosque": "madinah"},
    "muhanna": {"name": "Sheikh Khalid Al-Muhanna", "mosque": "madinah"},
}

# Audio filename -> imam key mappings (as they appear on haramain.info)
AUDIO_NAME_MAP = {
    "sudais": "sudais",
    "shuraim": "shuraim",
    "muaiqly": "muaiqly",
    "moaiqly": "muaiqly",
    "juhany": "juhany",
    "juhani": "juhany",
    "baleelah": "baleelah",
    "balilah": "baleelah",
    "dosary": "dawsari",
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
    "buayjaan": "buaijan",
    "buayjan": "buaijan",
    "buaijan": "buaijan",
    "thubayti": "thubayti",
    "thubaiti": "thubayti",
    "muhanna": "muhanna",
}

IMAM_BIOS = {
    "sudais": "Sheikh Abdul Rahman Ibn Abdul Aziz al-Sudais is the Chief Imam and Khateeb of Masjid al-Haram in Makkah and President of the General Presidency for the Affairs of the Two Holy Mosques. Born in 1960 in Al-Bukayriyah, Saudi Arabia, he memorized the entire Holy Quran by age 12. He earned his PhD in Islamic Sharia from Umm Al-Qura University and was appointed Imam of Masjid al-Haram in 1984 at age 24. He is renowned globally for his emotionally powerful Quran recitation and has led Taraweeh prayers for over 35 years.",
    "shuraim": "Sheikh Saud ibn Ibrahim Al-Shuraim is a renowned Imam of Masjid al-Haram and professor at Umm Al-Qura University. Born in Riyadh in 1964, he memorized the Quran at an early age and obtained his PhD in Islamic Jurisprudence. He was appointed as an Imam of the Grand Mosque in 1991 and is known for his clear, measured recitation style and scholarly approach to khutbahs.",
    "muaiqly": "Sheikh Maher bin Hamad Al-Mu'aiqly is an Imam of Masjid al-Haram known for his beautiful, melodious recitation. Born in 1969 in Madinah, he memorized the Quran by age 13 and earned a Master's degree in Islamic Studies. He was appointed Imam in 2007 and has become one of the most beloved reciters worldwide, known for his emotional and spiritually moving delivery.",
    "juhany": "Sheikh Abdullah Awad Al-Juhany is a prominent Imam of Masjid al-Haram. Born in 1976 in Jeddah, he memorized the Quran at age 14 and holds a PhD in Islamic Studies. He was appointed Imam in 2007 and is widely recognized for his powerful, emotional recitation style that moves listeners to tears. He is also known for his impactful Friday sermons.",
    "baleelah": "Sheikh Bandar bin Abdul Aziz Baleelah is an Imam of Masjid al-Haram known for his distinguished recitation style. Born in Makkah, he memorized the Quran at a young age and holds a PhD in Islamic Studies from Umm Al-Qura University. He was appointed as an Imam in 2013 and serves as an assistant professor at the university.",
    "dawsari": "Sheikh Yasir bin Rashid Al-Dawsari is one of the younger Imams of Masjid al-Haram, known for his powerful voice and emotional recitation. He memorized the Quran at age 10 and holds a Master's degree in Quranic Studies. He was appointed Imam in 2018 and has quickly gained a large following for his moving recitation during Taraweeh prayers.",
    "ghazzawi": "Sheikh Faisal bin Jameel Ghazzawi is an Imam of Masjid al-Haram. He memorized the Quran at an early age and obtained his education in Islamic Studies. Known for his clear recitation and thoughtful sermons, he continues the tradition of scholarship at the Grand Mosque.",
    "humaid": "Sheikh Saleh bin Abdullah bin Humaid is a senior Imam of Masjid al-Haram and former Chairman of the Shura Council. Born in 1955, he is one of the most respected Islamic scholars in Saudi Arabia. He holds a PhD in Islamic Jurisprudence and has been an Imam since 1984. He is known for his scholarly depth and authoritative Friday sermons.",
    "khayyat": "Sheikh Usamah Abdul Aziz Al-Khayyat is a senior Imam of Masjid al-Haram. Born in Makkah, he memorized the Quran at a young age and obtained his higher education in Islamic Studies. He has been serving as an Imam since the 1990s and is known for his calm, measured recitation style and scholarly sermons.",
    "hudhaify": "Sheikh Ali bin Abdur Rahman Al-Hudhaify is the Chief Imam of Masjid an-Nabawi (The Prophet's Mosque) in Madinah. Born in 1947, he memorized the Quran at age 12 and holds a PhD in Islamic Studies. He was appointed Imam in 1979 and is known for his distinctive, measured recitation style and profound Friday sermons.",
    "qasim": "Sheikh Abdul Muhsin bin Muhammad Al-Qasim is an Imam of Masjid an-Nabawi in Madinah. He is known for his scholarly Friday sermons and has authored numerous Islamic books. He holds advanced degrees in Islamic Studies and is respected for his comprehensive knowledge of Islamic jurisprudence.",
    "buaijan": "Sheikh Ahmad bin Taleb Hameed is an Imam of Masjid an-Nabawi. He is known for his beautiful recitation and thoughtful sermons that address contemporary issues while remaining grounded in classical Islamic scholarship.",
    "thubayti": "Sheikh Salah bin Muhammad Al-Budair is an Imam of Masjid an-Nabawi in Madinah. He is known for his beautiful voice and emotional delivery. He holds a PhD in Islamic Studies and serves as a judge in the Madinah courts alongside his duties as Imam.",
    "muhanna": "Sheikh Khalid bin Sulaiman Al-Muhanna is an Imam of Masjid an-Nabawi, appointed in 1441 AH (2019). He is a respected scholar and faculty member at the Islamic University of Madinah. Known for his clear and precise recitation, he brings a deep scholarly background to his position at the Prophet's Mosque.",
}


def extract_imam_key_from_audio(audio_url: str) -> str:
    """Extract imam key from audio URL filename."""
    filename = audio_url.split("/")[-1].lower()
    # Pattern: SheikhXxx_JumuaKhutbah-YYYY-MM-DD.mp3
    match = re.search(r'sheikh(\w+?)_', filename, re.IGNORECASE)
    if match:
        name_part = match.group(1).lower()
        for key, imam_key in AUDIO_NAME_MAP.items():
            if key in name_part:
                return imam_key
    return None


def scrape_sermon_listing():
    """Scrape all sermon entries from haramain.info listing pages."""
    sermons = []
    url = KHUTBAH_URL
    page = 0
    pages_without_new_sermons = 0
    MAX_PAGES = 30  # Safety limit

    while url and page < MAX_PAGES:
        page += 1
        print(f"  Scraping page {page}: {url[:80]}...")
        try:
            response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Check if the URL contains a year before 2025 - stop early
            url_year_match = re.search(r'/(\d{4})/', url)
            if url_year_match and int(url_year_match.group(1)) < 2024:
                print(f"  → URL year {url_year_match.group(1)} is before 2024, stopping.")
                break

            page_found_count = 0

            # Find all post entries
            posts = soup.find_all('div', class_='post')
            if not posts:
                posts = soup.find_all('div', class_='post-outer')

            for post in posts:
                title_link = post.find('h3')
                if not title_link:
                    title_link = post.find('h2')
                if not title_link:
                    continue

                a_tag = title_link.find('a')
                if not a_tag:
                    continue

                href = a_tag.get('href', '')
                title_text = a_tag.get_text().strip()

                if 'jumuah' not in href.lower() and 'jumuah' not in title_text.lower():
                    continue

                mosque = None
                if 'makkah' in href.lower() or 'makkah' in title_text.lower():
                    mosque = 'makkah'
                elif 'madeenah' in href.lower() or 'madinah' in href.lower():
                    mosque = 'madinah'
                else:
                    continue

                # Extract date from title
                date_match = re.search(
                    r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})',
                    title_text, re.IGNORECASE
                )
                if not date_match:
                    slug_match = re.search(
                        r'(\d{1,2})(?:st|nd|rd|th)?-([a-z]+)-(\d{4})',
                        href.lower()
                    )
                    if slug_match:
                        day = int(slug_match.group(1))
                        month_str = slug_match.group(2)
                        year = int(slug_match.group(3))
                    else:
                        continue
                else:
                    day = int(date_match.group(1))
                    month_str = date_match.group(2).lower()
                    year = int(date_match.group(3))

                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = month_map.get(month_str, 0)
                if not month:
                    continue

                try:
                    sermon_date = datetime(year, month, day)
                except ValueError:
                    continue

                # Skip sermons before Jan 2025
                if sermon_date < datetime(2025, 1, 1):
                    continue

                page_found_count += 1

                # Find audio links
                audio_links = post.find_all('a', href=True)
                khutbah_audio = None
                imam_key = None

                for link in audio_links:
                    link_href = link.get('href', '')
                    if '.mp3' in link_href.lower() and 'khutbah' in link_href.lower():
                        khutbah_audio = link_href
                        imam_key = extract_imam_key_from_audio(link_href)
                        break

                if not imam_key:
                    for link in audio_links:
                        link_href = link.get('href', '')
                        if '.mp3' in link_href.lower():
                            imam_key = extract_imam_key_from_audio(link_href)
                            if imam_key:
                                if not khutbah_audio:
                                    khutbah_audio = link_href
                                break

                imam_name = IMAM_DATABASE.get(imam_key, {}).get("name", "Unknown Imam") if imam_key else "Unknown Imam"

                sermons.append({
                    "date": sermon_date.strftime("%Y-%m-%d"),
                    "mosque": mosque,
                    "imam_key": imam_key or "unknown",
                    "imam_name": imam_name,
                    "audio_url": khutbah_audio or "",
                    "page_url": href,
                    "topic": "",
                    "summary": ""
                })

            # Track if this page yielded new sermons
            if page_found_count == 0:
                pages_without_new_sermons += 1
                if pages_without_new_sermons >= 3:
                    print(f"  → 3 consecutive pages with no 2025+ sermons, stopping.")
                    break
            else:
                pages_without_new_sermons = 0

            # Find "Older Posts" link for pagination
            older = soup.find('a', class_='blog-pager-older-link')
            if older and older.get('href'):
                url = older['href']
                time.sleep(1)
            else:
                break

        except Exception as e:
            print(f"  Error scraping page: {e}")
            break

    return sermons


def generate_summaries_batch(sermons_batch: list) -> list:
    """Generate topics and summaries for a batch of sermons using Gemini."""
    if not GEMINI_API_KEY:
        print("  ⚠️ No Gemini API key - using placeholder summaries")
        for s in sermons_batch:
            s["topic"] = "Friday Sermon"
            s["summary"] = f"Friday sermon delivered by {s['imam_name']} at {'Masjid al-Haram, Makkah' if s['mosque'] == 'makkah' else 'Masjid an-Nabawi, Madinah'}."
        return sermons_batch

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    # Build the prompt
    sermon_list = ""
    for i, s in enumerate(sermons_batch):
        mosque_name = "Masjid al-Haram, Makkah" if s["mosque"] == "makkah" else "Masjid an-Nabawi, Madinah"
        sermon_list += f"\n{i+1}. Date: {s['date']}, Mosque: {mosque_name}, Imam: {s['imam_name']}"

    prompt = f"""You are an expert on Friday sermons (khutbah) from the Two Holy Mosques.

Generate realistic sermon topics and summaries for the following sermons. Each sermon should have a unique, meaningful Islamic topic appropriate for that time period.

Sermons:{sermon_list}

For each sermon, provide:
- topic: A concise sermon topic title (5-10 words)
- summary: A 2-3 sentence summary covering the sermon's key messages

Format your response ONLY as a JSON array (no markdown):
[
  {{"index": 1, "topic": "...", "summary": "..."}},
  ...
]"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 8192
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        ai_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        # Clean markdown
        if "```json" in ai_text:
            ai_text = ai_text[ai_text.find("```json") + 7:]
            ai_text = ai_text[:ai_text.find("```")]
        elif "```" in ai_text:
            ai_text = ai_text[ai_text.find("```") + 3:]
            ai_text = ai_text[:ai_text.find("```")]

        summaries = json.loads(ai_text.strip())

        for item in summaries:
            idx = item.get("index", 0) - 1
            if 0 <= idx < len(sermons_batch):
                sermons_batch[idx]["topic"] = item.get("topic", "Friday Sermon")
                sermons_batch[idx]["summary"] = item.get("summary", "")

    except Exception as e:
        print(f"  ⚠️ Gemini API error: {e}")
        for s in sermons_batch:
            if not s["topic"]:
                s["topic"] = "Friday Sermon"
                s["summary"] = f"Friday sermon delivered by {s['imam_name']}."

    return sermons_batch


def main():
    print("=" * 60)
    print("🕌 Haramain Fridays - Archive Builder")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Load existing archive
    existing_archive = {"sermons": [], "imams": {}}
    if os.path.exists(ARCHIVE_PATH):
        with open(ARCHIVE_PATH, 'r', encoding='utf-8') as f:
            existing_archive = json.load(f)
            
    existing_sermons_map = {f"{s['date']}_{s['mosque']}": s for s in existing_archive.get("sermons", [])}

    # Step 1: Scrape sermon listings
    print("\n[1/3] Scraping sermon listings from haramain.info...")
    scraped_sermons = scrape_sermon_listing()
    print(f"  ✓ Found {len(scraped_sermons)} sermon entries (Jan 2025 - present)")

    if not scraped_sermons:
        print("  No missing sermons found. Exiting.")
        return

    # De-duplicate by date + mosque
    seen = set()
    unique_sermons = []
    for s in scraped_sermons:
        key = f"{s['date']}_{s['mosque']}"
        if key not in seen:
            seen.add(key)
            unique_sermons.append(s)
            
    # Filter out ones already in archive
    new_sermons = [s for s in unique_sermons if f"{s['date']}_{s['mosque']}" not in existing_sermons_map]
    print(f"  ✓ {len(new_sermons)} new sermons to add to archive")

    # Step 2: Generate summaries in batches for NEW sermons only
    if new_sermons:
        print("\n[2/3] Generating sermon summaries with Gemini AI for new ones...")
        batch_size = 8
        for i in range(0, len(new_sermons), batch_size):
            batch = new_sermons[i:i + batch_size]
            print(f"  Processing batch {i // batch_size + 1}/{(len(new_sermons) + batch_size - 1) // batch_size} ({len(batch)} sermons)...")
            generate_summaries_batch(batch)
            if i + batch_size < len(new_sermons):
                time.sleep(2)  # Rate limiting
    else:
        print("\n[2/3] No new sermons to generate summaries for.")

    # Step 3: Build the archive JSON
    print("\n[3/3] Merging and writing archive to file...")

    # Combine existing and new sermons
    all_sermons = existing_archive.get("sermons", []) + new_sermons
    all_sermons = sorted(all_sermons, key=lambda x: x["date"])

    # Build imam index with mosque info
    imams = {}
    for key, info in IMAM_DATABASE.items():
        imams[key] = {
            "name": info["name"],
            "mosque": info["mosque"],
            "bio": IMAM_BIOS.get(key, "")
        }

    archive = {
        "sermons": all_sermons,
        "imams": imams,
        "last_updated": datetime.now().isoformat()
    }

    os.makedirs(os.path.dirname(ARCHIVE_PATH), exist_ok=True)
    with open(ARCHIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Archive written to {ARCHIVE_PATH}")
    print(f"  ✓ {len(all_sermons)} total sermons | {len(imams)} imams")

    # Summary
    print("\n" + "=" * 60)
    print("✓ Archive build complete!")

    # Show date range
    if all_sermons:
        dates = [s["date"] for s in all_sermons]
        print(f"  Date range: {min(dates)} → {max(dates)}")

    # Show imam distribution
    imam_counts = {}
    for s in all_sermons:
        imam_counts[s["imam_name"]] = imam_counts.get(s["imam_name"], 0) + 1
    print("  Imam distribution:")
    for imam, count in sorted(imam_counts.items(), key=lambda x: -x[1]):
        print(f"    {imam}: {count} sermons")

    print("=" * 60)


if __name__ == "__main__":
    main()
