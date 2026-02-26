import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
url = "https://www.bing.com/search?q=restaurants+mississauga+ontario"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")
links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if href.startswith("http") and "bing.com" not in href and "microsoft" not in href:
        links.append(href)
print("Links:", links[:10])
