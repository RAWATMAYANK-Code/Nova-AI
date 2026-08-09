"""
fact_check.py
Fetches related news articles if NEWSDATA_API_KEY is present; otherwise returns an empty list cleanly.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL = "https://newsdata.io/api/1/news"


def fetch_related_articles(query, language="en", max_results=10):
    load_dotenv(override=True)
    api_key = os.getenv("NEWSDATA_API_KEY")

    if not api_key:
        print("[fact_check] NEWSDATA_API_KEY not configured. Skipping external article search.")
        return []

    params = {
        "apikey": api_key,
        "q": query,
        "language": language,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            print(f"[fact_check] API returned an error: {data}")
            return []

        articles = data.get("results", [])[:max_results]

        cleaned = []
        for a in articles:
            cleaned.append({
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "link": a.get("link", ""),
                "source_id": a.get("source_id", ""),
                "pubDate": a.get("pubDate", ""),
            })

        return cleaned

    except requests.exceptions.RequestException as e:
        print(f"[fact_check] Request failed: {e}")
        return []


if __name__ == "__main__":
    test_query = "India election results"
    results = fetch_related_articles(test_query)
    for r in results:
        print(r["title"], "-", r["source_id"])