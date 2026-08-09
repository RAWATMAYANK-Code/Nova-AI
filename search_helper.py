"""
search_helper.py
Performs lightweight live web/news search using Google News RSS and Wikipedia search APIs.
Provides real-time context to LLMs so they never complain about knowledge cutoffs.
"""

import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def search_live_web(query, max_results=5):
    """
    Fetches real-time web/news snippets using Google News RSS and Wikipedia APIs.
    Returns a formatted string of live search results.
    """
    snippets = []

    # 1. Try Google News RSS for current events and headlines
    try:
        rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        resp = requests.get(rss_url, headers={"User-Agent": USER_AGENT}, timeout=6)
        if resp.ok:
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")[:max_results]
            for idx, item in enumerate(items, 1):
                title = item.findtext("title") or ""
                pub_date = item.findtext("pubDate") or ""
                source = item.findtext("source") or "Google News"
                if title:
                    snippets.append(f"{idx}. [{source}] {title} ({pub_date})")
    except Exception as e:
        print(f"[search_helper] Google News RSS error: {e}")

    # 2. Try Wikipedia Search API for historical/factual background
    try:
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(query)}&utf8=&format=json"
        resp = requests.get(wiki_url, headers={"User-Agent": USER_AGENT}, timeout=5)
        if resp.ok:
            data = resp.json()
            search_items = data.get("query", {}).get("search", [])[:3]
            for item in search_items:
                title = item.get("title", "")
                snippet_raw = item.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '')
                if title and snippet_raw:
                    snippets.append(f"Wikipedia: {title} - {snippet_raw}")
    except Exception as e:
        print(f"[search_helper] Wikipedia Search error: {e}")

    if not snippets:
        return "No live search results retrieved."

    return "\n".join(snippets)


if __name__ == "__main__":
    print(search_live_web("Spain 2026 FIFA World Cup"))
