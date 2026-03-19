"""
News relevance filter for Opening Bell.

Removes yFinance articles where the ticker only appears as a tag
rather than as the actual subject of the article.
"""
# Future improvements if news quality is still insufficient:
# - Fetch full article body via trafilatura for richer LLM context
# - LLM relevance pre-filter for edge cases keyword matching misses

from utils.debug import debug_log


def filter_relevant_articles(articles: list, symbol: str, company_name: str) -> list:
    """
    Return only articles where symbol or a significant word from company_name
    appears in the title or summary (case-insensitive).

    Falls back to the full unfiltered list if nothing passes, so callers
    always receive at least some data.
    """
    symbol_lower = symbol.lower()
    name_keywords = [w.lower() for w in company_name.split() if len(w) > 4]
    keywords = [symbol_lower] + name_keywords

    relevant = []
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        if any(kw in text for kw in keywords):
            relevant.append(article)

    return relevant if relevant else articles


def enrich_articles(articles: list, symbol: str, company_name: str) -> list:
    """
    Filter articles for relevance, log the results, and return the filtered list.
    """
    filtered = filter_relevant_articles(articles, symbol, company_name)

    print(f"  [{symbol}] {len(articles)} articles → {len(filtered)} relevant")

    if filtered:
        debug_content = "\n\n".join(
            f"[{a.get('published', 'unknown date')}] {a.get('title', '')}\n  {a.get('summary', '')}"
            for a in filtered
        )
    else:
        debug_content = "(no articles)"
    debug_log(f"FILTERED NEWS — {symbol}", debug_content)

    return filtered
