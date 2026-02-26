import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
url = "https://ca.search.yahoo.com/search?p=restaurants+mississauga+ontario"
r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, "html.parser")
links = [a["href"] for a in soup.find_all("a", href=True) if "http" in a["href"] and "yahoo" not in a["href"]]
print("Links:", links[:10])
