"""Reads the brand's official website for facts (deterministic; every URL is recorded).

Instagram itself is not scraped (its terms forbid it); post screenshots and captions
are collected by hand and passed in through the brief.
"""

from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .schemas import Source

USER_AGENT = "Mozilla/5.0 (compatible; brand-post-recipe/0.1)"
MAX_CHARS = 6000
LINK_KEYWORDS = ("piv", "beer", "shop", "trgovina", "proizvod", "product", "o-nama", "about", "asortiman")


class WebReader:
    def __init__(self, max_pages: int = 8, client: httpx.Client | None = None):
        self.max_pages = max_pages
        self.client = client or httpx.Client(
            timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def read_site(self, website: str, extra_urls: list[str]) -> list[Source]:
        """Home page + extra URLs from the brief + relevant internal links found on the home page."""
        home, links = self._fetch(website, collect_links=True)
        queue = [u for u in extra_urls if u != website] + links
        sources = [home]
        seen = {website.rstrip("/")}
        for url in queue:
            if len(sources) >= self.max_pages:
                break
            if url.rstrip("/") in seen:
                continue
            seen.add(url.rstrip("/"))
            sources.append(self._fetch(url)[0])
        return sources

    def _fetch(self, url: str, collect_links: bool = False) -> tuple[Source, list[str]]:
        try:
            response = self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            return Source(url=url, ok=False, error=str(e) or type(e).__name__), []

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        links_soup = BeautifulSoup(response.text, "html.parser") if collect_links else None

        # Keep the main content only: navigation, footers and "related products" are noise for the model
        for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer", "form"]):
            tag.decompose()
        for tag in soup.select(".related, .upsells, .cross-sells, .widget, .sidebar"):
            tag.decompose()
        main = soup.select_one("div.product") or soup.find("main") or soup.body or soup
        text = " ".join(main.get_text(" ").split())[:MAX_CHARS]
        soup = links_soup or soup

        links: list[str] = []
        if collect_links:
            host = urlparse(str(response.url)).netloc
            for a in soup.find_all("a", href=True):
                href = urljoin(str(response.url), a["href"]).split("#")[0]
                if urlparse(href).netloc == host and any(k in href.lower() for k in LINK_KEYWORDS):
                    if href not in links:
                        links.append(href)

        return Source(url=str(response.url), ok=True, title=title, text=text), links
