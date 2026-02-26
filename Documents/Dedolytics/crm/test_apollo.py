import os
import requests
from dotenv import load_dotenv

load_dotenv()
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")


def test_match():
    url = "https://api.apollo.io/v1/people/match"
    headers = {"Cache-Control": "no-cache", "Content-Type": "application/json", "x-api-key": APOLLO_API_KEY}
    data = {"first_name": "Shweta", "last_name": "Agrawal", "organization_name": "Nike"}
    response = requests.post(url, headers=headers, json=data)
    print(f"Status: {response.status_code}")
    print(response.text)


if __name__ == "__main__":
    test_match()
