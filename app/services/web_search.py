import os
import asyncio
import httpx
from typing import List, Dict, Any, Optional

class WebSearchService:
    """
    Live Web Search Grounding service supporting:
    - DuckDuckGo Search (free, no key needed)
    - Tavily AI Search (optional high-precision search)
    - Direct HTTP fallback
    """
    def __init__(self, tavily_api_key: Optional[str] = None):
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")

    async def search(self, query: str, max_results: int = 5, api_key: Optional[str] = None) -> List[Dict[str, str]]:
        tavily_key = api_key or self.tavily_api_key

        # If Tavily key is available, use Tavily for high-quality AI grounding
        if tavily_key:
            try:
                results = await self._search_tavily(query, tavily_key, max_results)
                if results:
                    return results
            except Exception as e:
                print(f"[WebSearch] Tavily error: {e}, falling back to DuckDuckGo")

        # Use DuckDuckGo
        try:
            results = await self._search_duckduckgo(query, max_results)
            if results:
                return results
        except Exception as e:
            print(f"[WebSearch] DuckDuckGo library error: {e}, falling back to HTTP")

        # Fallback to direct HTTP search
        try:
            return await self._search_http_fallback(query, max_results)
        except Exception as e:
            print(f"[WebSearch] HTTP search error: {e}")
            return []

    async def _search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        def _sync_ddg():
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        loop = asyncio.get_event_loop()
        raw_results = await loop.run_in_executor(None, _sync_ddg)
        
        formatted = []
        for item in raw_results:
            title = (item.get("title") or "").strip()
            href = (item.get("href") or "").strip()
            body = (item.get("body") or "").strip()
            if not title or not href:
                continue

            lower_href = href.lower()
            lower_title = title.lower()

            # Filter out grokipedia, internal redirect proxies, and confusing domains
            if any(bad in lower_href or bad in lower_title for bad in ["grokipedia", "grok.", "grok/"]):
                continue

            formatted.append({
                "title": title,
                "url": href,
                "snippet": body
            })
        return formatted

    async def _search_tavily(self, query: str, api_key: str, max_results: int = 5) -> List[Dict[str, str]]:
        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "max_results": max_results
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", "")
                    })
                return results
        return []

    async def _search_http_fallback(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        endpoint = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.post(endpoint, data={"q": query})
            if resp.status_code == 200:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    results = []
                    for a in soup.find_all("a", class_="result__url"):
                        t = a.get_text(strip=True)
                        h = a.get("href", "")
                        if "grokipedia" in h.lower() or "grok" in h.lower():
                            continue
                        results.append({"title": t, "url": h, "snippet": ""})
                    return results[:max_results]
                except ImportError:
                    return []
        return []

    def format_grounding_prompt(self, query: str, results: List[Dict[str, str]]) -> str:
        if not results:
            return ""

        grounding_text = f"### نتایج جستجوی زنده در وب:\n"
        grounding_text += "اطلاعات موثق و دست‌اول زیر از وب استخراج شده است. از این اطلاعات به‌روز جهت ارائه پاسخی دقیق، سلیس و کامل به زبان فارسی استفاده فرمایید:\n\n"

        for idx, item in enumerate(results, 1):
            grounding_text += f"[{idx}] {item['title']}\n"
            grounding_text += f"پیوند: {item['url']}\n"
            if item.get('snippet'):
                grounding_text += f"خلاصه: {item['snippet']}\n\n"

        return grounding_text
