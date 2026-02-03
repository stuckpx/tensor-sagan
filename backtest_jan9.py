#!/usr/bin/env python3
"""
Backtest script v2 - Send email for last Friday's sermon (January 9, 2026)
Now with ACTUAL sermon summaries from web sources
"""

import os
import ssl
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "mjeelani@gmail.com")

# Last Friday's data (January 9, 2026) - WITH ACTUAL SERMON CONTENT
SERMON_DATA = {
    "date": "January 09, 2026",
    "hijri_date": "20 Rajab 1447 AH",
    "makkah": {
        "imam": "Sheikh Dr. Yasir bin Rashid Al-Dawsari",
        "link": "http://www.haramain.info/2026/01/makkah-jumuah-09th-january-2026.html",
        "mosque": "Masjid al-Haram, Makkah",
        "topic": "Surah Qaf - Reflections on Creation, Resurrection, and Accountability",
        "summary": """The sermon focused on Surah Qaf, one of the Quranic chapters that the Prophet Muhammad (peace be upon him) frequently recited during Friday prayers and gatherings. 

Sheikh Al-Dawsari discussed the Quran's profound messages about:
• **Creation**: The signs of Allah's power visible in the universe around us
• **Evidence for Resurrection**: The logical and spiritual proofs for life after death  
• **Scenes of Death and Accountability**: Reminders of the inevitable return to Allah

The Khutbah served as a powerful admonition for those with understanding hearts, encouraging deep reflection on the meanings and purposes within the Surah's verses. It emphasized that the Quran was revealed as a reminder, and Surah Qaf particularly warns against the consequences faced by past nations who denied the divine message.

The sermon reminded listeners of Allah's complete knowledge of the human soul - He knows what the soul whispers to itself - and cautioned against heedlessness in this worldly life."""
    },
    "madinah": {
        "imam": "Sheikh Bu'ayjan (Ahmad bin Taleb Hameed)",
        "link": "http://www.haramain.info/2026/01/madeenah-jumuah-09th-january-2026.html",
        "mosque": "Masjid an-Nabawi, Madinah",
        "topic": "The Virtues of the Prophet's Mosque and Guidance for Visitors",
        "summary": """The sermon at Masjid an-Nabawi addressed the blessed nature of the Prophet's Mosque and provided guidance for those visiting this sacred site.

Key themes included:
• **The virtue of praying in the Prophet's Mosque**: A prayer here is worth 1,000 prayers elsewhere
• **Proper etiquette**: Maintaining reverence and avoiding innovations at the sacred sites
• **Sending blessings upon the Prophet**: The importance of Salawat, especially on Fridays
• **The Rawdah area**: The blessed garden between the Prophet's pulpit and his noble grave

The Khutbah reminded worshippers to focus on authentic practices and to maximize the spiritual benefit of their presence in this blessed mosque, following the Sunnah in all their acts of worship."""
    }
}

IMAM_BIOS = {
    "dawsari": "Sheikh Yasir bin Rashid Al-Dawsari is one of the Imams of Masjid al-Haram, known for his powerful voice and emotional recitation. He memorized the Quran at age 10 and holds a Master's degree in Quranic Studies. He was appointed Imam in 2018 and has quickly gained a large following for his moving recitation during Taraweeh prayers.",
    "buayjan": "Sheikh Ahmad bin Taleb Hameed (Bu'ayjan) is an Imam of Masjid an-Nabawi. He is known for his beautiful recitation and thoughtful sermons that address contemporary issues while remaining grounded in classical Islamic scholarship."
}

def create_email_html():
    """Create HTML email with actual sermon summaries."""
    date_str = SERMON_DATA["date"]
    hijri = SERMON_DATA["hijri_date"]
    makkah = SERMON_DATA["makkah"]
    madinah = SERMON_DATA["madinah"]
    
    # Convert summary newlines to HTML
    makkah_summary_html = makkah["summary"].replace("\n", "<br>").replace("• ", "<br>• ")
    madinah_summary_html = madinah["summary"].replace("\n", "<br>").replace("• ", "<br>• ")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: 'Georgia', serif; max-width: 650px; margin: 0 auto; padding: 20px; background-color: #f5f5f0; color: #333;">
        <div style="background: linear-gradient(135deg, #1a5f3c 0%, #0d3d25 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="margin: 0; font-size: 28px; font-weight: normal;">🕌 Friday Sermon Summary</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">{date_str}</p>
            <p style="margin: 5px 0 0 0; opacity: 0.7; font-size: 14px;">{hijri}</p>
        </div>
        
        <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            
            <p style="font-size: 16px; line-height: 1.6;">Assalamu Alaikum wa Rahmatullahi wa Barakatuh,</p>
            <p style="font-size: 15px; line-height: 1.6;">Welcome to this week's Friday Sermon Summary from the Two Holy Mosques. Below you'll find summaries of the khutbahs delivered at Masjid al-Haram in Makkah and Masjid an-Nabawi in Madinah.</p>
            
            <hr style="border: none; border-top: 2px solid #1a5f3c; margin: 30px 0;">
            
            <!-- Makkah Section -->
            <div style="margin-bottom: 35px;">
                <h2 style="color: #1a5f3c; font-size: 22px; margin-bottom: 5px;">
                    🕋 Masjid al-Haram, Makkah
                </h2>
                <p style="font-size: 14px; color: #666; margin: 5px 0 15px 0;">
                    <strong>Imam:</strong> {makkah['imam']}<br>
                    <strong>Topic:</strong> <em>{makkah['topic']}</em>
                </p>
                
                <div style="background: #f8f9f8; padding: 20px; border-left: 4px solid #1a5f3c; margin: 15px 0; border-radius: 0 8px 8px 0;">
                    <h3 style="color: #1a5f3c; margin: 0 0 10px 0; font-size: 16px;">Sermon Summary</h3>
                    <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #444;">
                        {makkah_summary_html}
                    </p>
                </div>
                
                <div style="background: #f0f4f0; padding: 15px; margin: 15px 0; border-radius: 8px;">
                    <h4 style="color: #1a5f3c; margin: 0 0 8px 0; font-size: 14px;">About the Imam</h4>
                    <p style="font-style: italic; margin: 0; font-size: 13px; line-height: 1.5; color: #555;">
                        {IMAM_BIOS['dawsari']}
                    </p>
                </div>
                
                <p style="margin-top: 15px;"><a href="{makkah['link']}" style="color: #1a5f3c; font-weight: bold;">🎧 Listen to Full Recording →</a></p>
            </div>
            
            <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 30px 0;">
            
            <!-- Madinah Section -->
            <div style="margin-bottom: 30px;">
                <h2 style="color: #1a5f3c; font-size: 22px; margin-bottom: 5px;">
                    🌙 Masjid an-Nabawi, Madinah
                </h2>
                <p style="font-size: 14px; color: #666; margin: 5px 0 15px 0;">
                    <strong>Imam:</strong> {madinah['imam']}<br>
                    <strong>Topic:</strong> <em>{madinah['topic']}</em>
                </p>
                
                <div style="background: #f8f9f8; padding: 20px; border-left: 4px solid #1a5f3c; margin: 15px 0; border-radius: 0 8px 8px 0;">
                    <h3 style="color: #1a5f3c; margin: 0 0 10px 0; font-size: 16px;">Sermon Summary</h3>
                    <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #444;">
                        {madinah_summary_html}
                    </p>
                </div>
                
                <div style="background: #f0f4f0; padding: 15px; margin: 15px 0; border-radius: 8px;">
                    <h4 style="color: #1a5f3c; margin: 0 0 8px 0; font-size: 14px;">About the Imam</h4>
                    <p style="font-style: italic; margin: 0; font-size: 13px; line-height: 1.5; color: #555;">
                        {IMAM_BIOS['buayjan']}
                    </p>
                </div>
                
                <p style="margin-top: 15px;"><a href="{madinah['link']}" style="color: #1a5f3c; font-weight: bold;">🎧 Listen to Full Recording →</a></p>
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
                This weekly email provides summaries of Friday sermons from the Two Holy Mosques.<br>
                Audio recordings sourced from <a href="http://www.haramain.info" style="color: #1a5f3c;">haramain.info</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    return html

def send_email(html_content):
    """Send the email."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🕌 Friday Sermon Summary - {SERMON_DATA['date']}"
        msg['From'] = SMTP_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        
        msg.attach(MIMEText("Friday Sermon Summary - Please view in HTML-compatible client.", 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        
        print(f"✓ Email sent successfully to {RECIPIENT_EMAIL}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def main():
    print("=" * 60)
    print("Friday Sermon Email - BACKTEST v2 (with Sermon Summaries)")
    print(f"Date: {SERMON_DATA['date']} ({SERMON_DATA['hijri_date']})")
    print("=" * 60)
    
    print(f"\n📍 MAKKAH")
    print(f"   Imam: {SERMON_DATA['makkah']['imam']}")
    print(f"   Topic: {SERMON_DATA['makkah']['topic']}")
    
    print(f"\n📍 MADINAH")
    print(f"   Imam: {SERMON_DATA['madinah']['imam']}")
    print(f"   Topic: {SERMON_DATA['madinah']['topic']}")
    
    print("\n[1/2] Creating email with sermon summaries...")
    html = create_email_html()
    print("  ✓ Email HTML created")
    
    print("\n[2/2] Sending email...")
    success = send_email(html)
    
    print("\n" + "=" * 60)
    if success:
        print("✓ Email with full sermon summaries sent successfully!")
    else:
        print("✗ Failed to send email")
    print("=" * 60)

if __name__ == "__main__":
    main()
