import re
import requests
from bs4 import BeautifulSoup
import config


def get_posts(per_page: int = 20) -> list[dict]:
            """Fetch content from a URL.

                Strategy:
                    1. Try the WordPress REST API (/wp-json/wp/v2/posts) first.
                        2. If that fails (non-WordPress site), fall back to scraping the page
                               directly using BeautifulSoup and return it as a single post.
                                   """
            base_url = config.WP_SITE_URL.rstrip("/")
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; BlogToCarousel/1.0)",
                "Accept": "application/json",
            }

    # --- Attempt 1: WordPress REST API ---
            wp_url = f"{base_url}/wp-json/wp/v2/posts"
            params = {"per_page": per_page, "orderby": "date", "status": "publish"}
            try:
                            resp = requests.get(wp_url, params=params, headers=headers, timeout=15)
                            resp.raise_for_status()
                            data = resp.json()
                            if isinstance(data, list) and len(data) > 0 and "id" in data[0]:
                                                posts = []
                                                for item in data:
                                                                        posts.append({
                                                                                                    "id": item["id"],
                                                                                                    "slug": item["slug"],
                                                                                                    "title": _strip_html(item["title"]["rendered"]),
                                                                                                    "content": _clean_content(item["content"]["rendered"]),
                                                                                                    "link": item["link"],
                                                                        })
                                                                    return posts
except Exception:
        pass  # WordPress API not available — fall back to scraping

    # --- Attempt 2: Generic web scraping ---
    return _scrape_page(base_url)


def _scrape_page(url: str) -> list[dict]:
            """Scrape any web page and return its main content as a single post."""
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; BlogToCarousel/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            try:
                            resp = requests.get(url, headers=headers, timeout=15)
                            resp.raise_for_status()
except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch page from {url}: {e}")

    # Detect encoding: respect HTTP header, then fall back to apparent encoding
    # (handles non-UTF-8 sites like windows-1256 Arabic pages)
    if resp.encoding and resp.encoding.lower() not in ("utf-8", "utf8"):
                    html = resp.content.decode(resp.encoding, errors="replace")
else:
                # Use chardet/apparent_encoding as a better fallback than raw bytes
                encoding = resp.apparent_encoding or "utf-8"
                html = resp.content.decode(encoding, errors="replace")

    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else url

    # Extract main content — try common article containers in priority order
    # Includes id-based selectors for non-standard sites (e.g. div#bodytext)
    content_html = None
    for selector in [
                    "article",
                    "main",
                    '[role="main"]',
                    "#bodytext",
                    "#body-text",
                    "#main-content",
                    "#page-content",
                    ".post-content",
                    ".entry-content",
                    ".article-body",
                    ".article-content",
                    ".content-body",
                    ".content",
                    "#content",
                    ".container .row",
    ]:
                    el = soup.select_one(selector)
                    if el:
                                        content_html = str(el)
                                        break

                # Fall back to the full body if no known container found
                if not content_html:
                                body = soup.find("body")
                                content_html = str(body) if body else html

    content = _clean_content(content_html)

    return [{
                    "id": 1,
                    "slug": re.sub(r"[^a-z0-9]+", "-", url.split("//")[-1].lower()).strip("-"),
                    "title": title,
                    "content": content,
                    "link": url,
    }]


def _strip_html(html: str) -> str:
            return BeautifulSoup(html, "html.parser").get_text()


def _clean_content(html: str) -> str:
            soup = BeautifulSoup(html, "html.parser")
            # Remove non-content elements
            for tag in soup(["script", "style", "figure", "img", "iframe", "nav",
                                                  "header", "footer", "aside", "form", "button"]):
                                                                  tag.decompose()
                                                              text = soup.get_text(separator="\n")
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
