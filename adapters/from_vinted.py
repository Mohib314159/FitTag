"""Vinted listing ingestion — adapted from Mohib's JeansFinder scraper.

JeansFinder's pattern (scrape a marketplace's JSON API → embed → rank → learn from
feedback) is exactly what FitTag needs to (a) run the engine on real listings for the
demo and the returns-impact number, (b) feed the Tier-3 "find more like this, in my
size" feature (CLIP visual similarity × measured fit), and (c) push measurements back
into a listing's fields (auto-fill).

This reuses JeansFinder's approach: pull a session cookie from the Vinted homepage, then
query the internal /api/v2/catalog/items JSON endpoint the Vinted frontend itself uses —
no browser, no HTML parsing. Conservative delays; respect Vinted's terms and rate limits.

NOTE: requires outbound access to vinted.* and is intended to run outside the sandbox.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

VINTED_BASE = "https://www.vinted.co.uk"
CATALOG_ITEMS = "/api/v2/catalog/items"
UA = "Mozilla/5.0 (FitTag listing ingest; contact you@example.com)"


@dataclass
class Listing:
    id: str
    title: str
    brand: str
    size_label: str          # the label that lies — the reason FitTag exists
    price: float
    currency: str
    url: str
    image_urls: list[str] = field(default_factory=list)


class VintedClient:
    """Minimal Vinted JSON client (JeansFinder-style cookie bootstrap + catalog query)."""

    def __init__(self, base: str = VINTED_BASE, min_delay: float = 2.0):
        self.base = base
        self.min_delay = min_delay
        self._client = httpx.Client(headers={"User-Agent": UA}, timeout=20.0, follow_redirects=True)
        self._last = 0.0
        self._bootstrap_cookie()

    def _bootstrap_cookie(self):
        # hitting the homepage sets the session cookie the API requires
        self._client.get(self.base + "/")

    def _throttle(self):
        wait = self.min_delay - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def search(self, query: str, per_page: int = 96, pages: int = 1,
               catalog_ids: str = "", brand_ids: str = "") -> list[Listing]:
        """Query the catalog. Pulls multiple pages; re-bootstraps the cookie if it expires."""
        out: list[Listing] = []
        for page in range(1, pages + 1):
            self._throttle()
            params = {"search_text": query, "per_page": per_page, "page": page,
                      "catalog_ids": catalog_ids, "brand_ids": brand_ids, "order": "newest_first"}
            r = self._client.get(self.base + CATALOG_ITEMS, params=params)
            if r.status_code in (401, 403):           # cookie expired -> refresh once
                self._bootstrap_cookie()
                r = self._client.get(self.base + CATALOG_ITEMS, params=params)
            r.raise_for_status()
            for it in r.json().get("items", []):
                out.append(_parse_item(it))
        return out

    def fetch_image(self, url: str) -> bytes:
        self._throttle()
        return self._client.get(url).content

    def close(self):
        self._client.close()


def _parse_item(it: dict) -> Listing:
    photos = it.get("photos") or ([it["photo"]] if it.get("photo") else [])
    urls = [p.get("full_size_url") or p.get("url") for p in photos if p]
    price = it.get("price")
    if isinstance(price, dict):                       # Vinted nests price as {amount, currency}
        amount = float(price.get("amount", 0) or 0); currency = price.get("currency_code", "GBP")
    else:
        amount = float(price or 0); currency = it.get("currency", "GBP")
    return Listing(
        id=str(it.get("id", "")),
        title=it.get("title", ""),
        brand=(it.get("brand_title") or it.get("brand") or ""),
        size_label=it.get("size_title", ""),
        price=amount, currency=currency,
        url=it.get("url", ""),
        image_urls=[u for u in urls if u],
    )


if __name__ == "__main__":
    # Example (run outside the sandbox): pull a page of listings to measure / aggregate.
    c = VintedClient()
    for lst in c.search("levi 501 vintage", per_page=20, pages=1)[:5]:
        print(f"{lst.brand:<12} size={lst.size_label:<8} £{lst.price:<6} {lst.title[:40]}")
    c.close()
