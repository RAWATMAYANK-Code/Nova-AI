"""
gemini_checker.py
Uses Google Gemini as a second independent AI opinion for fact-checking.
Given the same related articles used for the Groq verdict, this gives an
independent second verdict so we can combine multiple models (ensemble).
"""

import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-3.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# requests' HTTPError messages include the full request URL, which for
# Gemini contains ?key=<API_KEY>. NEVER let raw exception text reach the
# user without stripping that out first.
API_KEY_PATTERN = re.compile(r"key=[^&\s\"']+", re.IGNORECASE)


def safe_error(prefix, exc):
    msg = API_KEY_PATTERN.sub("key=REDACTED", str(exc))
    return f"{prefix}: {msg}"


def generate_verdict_gemini(original_news, articles):
    """
    Same job as explain.py's generate_verdict(), but using Gemini instead of Groq.
    Used as a second opinion for ensemble voting.
    """
    if not GEMINI_API_KEY:
        return {
            "verdict": "Unverified",
            "confidence": "N/A",
            "misleading_percentage": None,
            "highlighted_claim": "",
            "consensus_fact": "",
            "reason_flagged": "",
            "explanation": "GEMINI_API_KEY not set in .env file.",
            "sources_checked": []
        }

    if not articles:
        return {
            "verdict": "Unverified",
            "confidence": "N/A",
            "misleading_percentage": None,
            "highlighted_claim": "",
            "consensus_fact": "",
            "reason_flagged": "",
            "explanation": "No related articles available for Gemini to check.",
            "sources_checked": []
        }

    context = ""
    for i, a in enumerate(articles, 1):
        context += f"{i}. Title: {a['title']}\n   Source: {a['source_id']}\n   Description: {a['description']}\n\n"

    prompt = f"""You are a fact-checking assistant. Compare the ORIGINAL NEWS CLAIM below
with the RELATED ARTICLES retrieved from trusted news sources. Based ONLY on this
retrieved context (do not use outside knowledge), decide if the claim appears to be
Real, Fake, Misleading, or Unverified. "Misleading" means the claim is built on a
true, consensus fact but distorts, exaggerates, or strips context from it.

Respond with ONLY a JSON object, nothing else, in this exact format:
{{
  "verdict": "Real, Fake, Misleading, or Unverified",
  "confidence": "80%",
  "misleading_percentage": <integer 0-100 estimating how much of the claim is inaccurate or lacks context; 0 if fully accurate, 100 if entirely false>,
  "highlighted_claim": "<the specific short phrase, figure, or quote from the original claim that is most in question, verbatim, under 8 words; empty string if not applicable>",
  "consensus_fact": "<2-3 sentences stating the broadly agreed-upon, verifiable fact relevant to this claim, grounded in the retrieved articles>",
  "reason_flagged": "<2-3 sentences explaining specifically why the claim is false or misleading and what context is missing; empty string if the verdict is fully Real>",
  "explanation": "<4-6 sentence narrative synthesizing the above for a general reader>",
  "sources_checked": ["source1", "source2"]
}}

ORIGINAL NEWS CLAIM:
\"\"\"{original_news}\"\"\"

RELATED ARTICLES:
{context}

JSON response:"""

    try:
        response = requests.post(
            URL,
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]

        result = json.loads(raw)
        return result

    except Exception as e:
        return {
            "verdict": "Unverified",
            "confidence": "N/A",
            "misleading_percentage": None,
            "highlighted_claim": "",
            "consensus_fact": "",
            "reason_flagged": "",
            "explanation": safe_error("Gemini check failed", e),
            "sources_checked": [],
            "failed": True
        }


if __name__ == "__main__":
    sample_articles = [
        {"title": "Govt denies free laptop scheme rumor", "source_id": "pib",
         "description": "PIB Fact Check clarifies no such scheme exists."}
    ]
    print(generate_verdict_gemini("Govt giving free laptops to all students", sample_articles))