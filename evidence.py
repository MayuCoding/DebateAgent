"""
Evidence-first web search and content extraction module.

This module implements the evidence-first approach:
1. Search the web for the topic
2. Gather real URLs with actual content
3. Summarize each source using the LLM
4. Return verified evidence for response generation
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from decorators import span


class SearchResult(BaseModel):
    """A single search result from Tavily."""
    title: str
    url: str
    content: str = Field(description="Snippet or extracted content from the page")
    score: float = Field(default=0.0, description="Relevance score from search")


class SourceSummary(BaseModel):
    """A summarized source with its URL and key points."""
    url: str
    title: str
    summary: str = Field(description="LLM-generated summary of the source content")
    key_claims: List[str] = Field(description="Key claims/facts extracted from this source")
    relevance_to_topic: str = Field(description="How this source relates to the debate topic")


class GatheredEvidence(BaseModel):
    """Collection of verified evidence from web search."""
    query_used: str
    sources: List[SourceSummary]


@span("web_search")
def search_web_for_evidence(
    motion: str,
    side: str,
    tavily_api_key: str,
    max_results: int = 8,
) -> List[SearchResult]:
    """
    Search the web for evidence related to the debate motion.
    
    Args:
        motion: The debate motion/topic
        side: Which side to search evidence for (pro/con)
        tavily_api_key: Tavily API key
        max_results: Maximum number of results to return
    
    Returns:
        List of SearchResult with real URLs and content
    """
    from tavily import TavilyClient
    
    client = TavilyClient(api_key=tavily_api_key)
    
    if side == "pro":
        query = f"arguments supporting: {motion} evidence research studies"
    else:
        query = f"arguments against: {motion} evidence research studies criticism"
    
    print(f"[evidence] Searching: {query[:80]}...")
    
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_raw_content=False,
        include_domains=[
            "ncbi.nlm.nih.gov",
            "pubmed.ncbi.nlm.nih.gov", 
            "nhtsa.gov",
            "who.int",
            "gov",
            "edu",
            "wikipedia.org",
            "sciencedirect.com",
            "nature.com",
            "bmj.com",
            "thelancet.com",
        ],
    )
    
    results = []
    for r in response.get("results", []):
        results.append(SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            content=r.get("content", ""),
            score=r.get("score", 0.0),
        ))
    
    print(f"[evidence] Found {len(results)} sources")
    return results


@span("summarize_sources")
def summarize_sources(
    search_results: List[SearchResult],
    motion: str,
    side: str,
    client: Any,
    model: str,
) -> List[SourceSummary]:
    """
    Summarize each search result using the LLM.
    
    This step extracts key claims and assesses relevance to the debate topic.
    Each summary is tied to its real URL.
    """
    if not search_results:
        return []
    
    sources_text = "\n\n".join([
        f"Source {i+1}:\nTitle: {r.title}\nURL: {r.url}\nContent: {r.content}"
        for i, r in enumerate(search_results)
    ])
    
    system = f"""You are a research assistant analyzing sources for a debate.
Motion: {motion}
Side being argued: {side}

For each source provided, extract:
1. A concise summary of the main points
2. Key claims or facts that can be used as evidence
3. How this source relates to the debate topic

Return a JSON object with a 'sources' array containing summaries for each source.
Each source summary must include: url, title, summary, key_claims (array), relevance_to_topic.
IMPORTANT: Use the EXACT URLs provided - do not modify or fabricate URLs."""

    class SourceSummaryList(BaseModel):
        sources: List[SourceSummary]
    
    print(f"[evidence] Summarizing {len(search_results)} sources...")
    
    result: SourceSummaryList = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": sources_text},
        ],
        temperature=0.1,
        max_tokens=2000,
        response_model=SourceSummaryList,
        max_retries=2,
    )
    
    return result.sources


@span("gather_evidence")
def gather_evidence(
    motion: str,
    side: str,
    tavily_api_key: Optional[str],
    client: Any,
    model: str,
) -> GatheredEvidence:
    """
    Main evidence gathering pipeline:
    1. Search web for topic
    2. Gather links with content
    3. Summarize each source
    4. Return verified evidence with real URLs
    
    If no Tavily API key is provided, returns empty evidence.
    """
    if not tavily_api_key:
        print("[evidence] No TAVILY_API_KEY set - skipping web search")
        return GatheredEvidence(
            query_used="",
            sources=[],
        )
    
    if side == "pro":
        query = f"arguments supporting: {motion}"
    else:
        query = f"arguments against: {motion}"
    
    search_results = search_web_for_evidence(
        motion=motion,
        side=side,
        tavily_api_key=tavily_api_key,
    )
    
    if not search_results:
        print("[evidence] No search results found")
        return GatheredEvidence(query_used=query, sources=[])
    
    summaries = summarize_sources(
        search_results=search_results,
        motion=motion,
        side=side,
        client=client,
        model=model,
    )
    
    print(f"[evidence] Gathered {len(summaries)} verified sources")
    
    return GatheredEvidence(
        query_used=query,
        sources=summaries,
    )
