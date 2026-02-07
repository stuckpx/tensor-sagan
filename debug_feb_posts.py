
import requests
from bs4 import BeautifulSoup

URL = "http://www.haramain.info/search/label/Friday%20Khutbah"
# Try main page too
URL_MAIN = "http://www.haramain.info/"

def scan(url):
    print(f"Scanning {url}...")
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, "html.parser")
        links = soup.find_all("a", href=True)
        
        print(f"Found {len(links)} links.")
        print("-" * 40)
        
        # Look for Feb 2026 posts
        count = 0
        for l in links:
            href = l['href']
            text = l.get_text().strip()
            
            # Print anything that looks like a sermon post from Feb 2026
            if "2026/02" in href or "february-2026" in href.lower():
                # Filter noise (archive links)
                if text and len(text) > 10 and not "February 2026" == text:
                     print(f"[{text}] -> {href}")
                     count += 1
                     
        if count == 0:
            print("No Feb 2026 posts found!")
            
    except Exception as e:
        print(e)

print("Checking Label Page:")
scan(URL)
print("\nChecking Main Page:")
scan(URL_MAIN)
