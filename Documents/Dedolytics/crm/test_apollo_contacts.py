import os
import requests
from dotenv import load_dotenv

load_dotenv()
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")


def test_contacts():
    url = "https://api.apollo.io/v1/contacts/search"
    headers = {"Cache-Control": "no-cache", "Content-Type": "application/json", "x-api-key": APOLLO_API_KEY}
    data = {}
    response = requests.post(url, headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(response.text)


if __name__ == "__main__":
    test_contacts()
