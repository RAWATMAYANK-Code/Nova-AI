"""
main.py
Full pipeline:

News/Claim Input
    -> Classify & extract claim using active API key (with key rotation)
    -> Verify claim with active model (using browser search / trained knowledge)
    -> Return verdict (Real, Fake, Misleading, or Unverified)
"""

from claim_extractor import classify_and_extract
from fact_check import fetch_related_articles
from explain import generate_verdict
from classifier import predict_with_ml
from general_fact_checker import check_general_fact


def check_news(news_text):
    print("\n[1] Classifying and extracting claim (single active model call)...")
    analysis = classify_and_extract(news_text)
    claim_type = analysis["type"]
    claim = analysis["claim"]
    print(f"    -> Type: {claim_type}, Claim: '{claim}', API: {analysis.get('api_used')}")

    # Step 1: Run fact check with active model key (browser search + knowledge)
    print("\n[2] Checking statement with active model key...")
    result = check_general_fact(news_text)
    print(f"    -> Verdict: {result.get('verdict')}, API Used: {result.get('api_used')}")

    if result.get("verdict") in ("Real", "Fake", "Misleading"):
        return result

    # Step 2: Try fetching articles if NEWSDATA_API_KEY is configured
    articles = fetch_related_articles(claim)
    if articles:
        print(f"\n[3] Found {len(articles)} articles -> Generating source-grounded verdict...")
        rag_res = generate_verdict(news_text, articles)
        if rag_res.get("verdict") in ("Real", "Fake", "Misleading"):
            return rag_res

    # Step 3: If live search and articles could not verify, return Unverified pattern report
    if result.get("verdict") == "Unverified" and result.get("failed"):
        print("\n[4] External APIs unavailable -> returning Unverified pattern analysis...")
        ml_res = predict_with_ml(news_text)
        return ml_res

    return result


if __name__ == "__main__":
    news = input("Paste the news/claim: ")
    res = check_news(news)

    print("\n===== FINAL RESULT =====")
    print(f"Verdict              : {res.get('verdict')}")
    print(f"Confidence           : {res.get('confidence')}")
    print(f"Confidence %         : {res.get('confidence_percent')}")
    print(f"Misleading %         : {res.get('misleading_percentage')}")
    print(f"Highlighted claim    : {res.get('highlighted_claim')}")
    print(f"Consensus fact       : {res.get('consensus_fact')}")
    print(f"Reason flagged       : {res.get('reason_flagged')}")
    print(f"Explanation          : {res.get('explanation')}")
    print(f"Sources              : {res.get('sources_checked')}")
    print(f"API Used             : {res.get('api_used')}")