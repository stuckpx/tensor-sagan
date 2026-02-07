
import requests
from bs4 import BeautifulSoup
import re

URL = "http://www.haramain.info/2026/02/madeenah-jumuah-06th-february-2026.html"

def debug_madinah():
    print(f"Fetching {URL}...")
    r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.content, "html.parser")
    
    # Check Title
    print(f"Title: {soup.title.string}")
    
    # Check Meta Description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        print(f"Meta Description: {meta_desc['content']}")
        
    # Check Post Body Text
    content_div = soup.find('div', class_='post-body') or soup.find('div', class_='entry-content')
    if content_div:
        print(f"Body Text Sample: {content_div.get_text()[:500]}")
        
        # Check MP3 Links
        print("\nLinks in Body:")
        links = content_div.find_all('a', href=True)
        for l in links:
            print(f" - {l['href']}")

debug_madinah()
