from __future__ import annotations

import asyncio

import httpx
try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - compatibility fallback
    from duckduckgo_search import DDGS

from app.config import Settings
from app.utils.text import normalize_text


class SearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search_context(self, query: str) -> str:
        provider = self.settings.internet_search_provider.lower()
        try:
            if provider == "serpapi" and self.settings.serpapi_api_key:
                results = await self._search_serpapi(query)
            else:
                results = await asyncio.to_thread(self._search_duckduckgo, query)
        except Exception:
            results = []
        return self._format_results(results)

    def _search_duckduckgo(self, query: str) -> list[dict[str, str]]:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=self.settings.web_result_limit))

    async def _search_serpapi(self, query: str) -> list[dict[str, str]]:
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.settings.serpapi_api_key,
            "num": self.settings.web_result_limit,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            response.raise_for_status()
        data = response.json()
        organic = data.get("organic_results", [])
        return [
            {
                "title": item.get("title", ""),
                "body": item.get("snippet", ""),
                "href": item.get("link", ""),
            }
            for item in organic
        ]

    def _format_results(self, results: list[dict[str, str]]) -> str:
        if not results:
            return "NO_CONTEXT_FOUND"

        lines: list[str] = []
        for index, item in enumerate(results[: self.settings.web_result_limit], start=1):
            title = normalize_text(item.get("title", ""))
            snippet = normalize_text(item.get("body", ""))
            href = item.get("href", "")
            line = f"{index}. {title} | {snippet}"
            if href:
                line = f"{line} | URL: {href}"
            lines.append(line)

        return normalize_text("\n".join(lines))[: self.settings.web_context_char_limit]
