import re
import requests
from bs4 import BeautifulSoup
import config

# Common browser-like headers to avoid blocks
_HEADERS = {
                "User-Agent": (
                                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
}

# CSS selectors tried in priority order to extract main content
_CONTENT_SELECTORS = [
                "article",
                "main",
                '[role="main"]',
                "#bodytext",
                "#body-text",
                "#main-content",
                "#page-content",
                "#article-content",
                ".post-content",
                ".entry-content",
                ".article-body",
                ".article-content",
                ".content-body",
                ".content",
                "#content",
                ".container",
]


def get_posts(per_page: int = 20) -> list[dict]:
                """Fetch content from a URL.

                    Tries the WordPress REST API first; falls back to generic HTML scraping
                        for any other website.
                            """
                base_url = config.WP_SITE_URL.rstrip("/")

    # --- Attempt 1: WordPress REST API ---
                wp_posts = _try_wordpress_api(base_url, per_page)
                if wp_posts is not None:
                                    return wp_posts

                # --- Attempt 2: Generic web scraping ---
                return _scrape_page(base_url)


def _try_wordpress_api(base_url: str, per_page: int):
                """Return list of posts from WP REST API, or None if not a WP site."""
                url = f"{base_url}/wp-json/wp/v2/posts"
                params = {"per_page": per_page, "orderby": "date", "status": "publish"}
                try:
                                    resp = requests.get(url, params=params, headers=_HEADERS, timeout=15, verify=True)
                                    # Only treat as WP if we get a successful response with JSON
                                    if resp.status_code != 200:
                                                            return None
                                                        ct = resp.headers.get("content-type", "")
                                    if "json" not in ct:
                                                            return None
                                                        data = resp.json()
                                    if not isinstance(data, list) or not data or "id" not in data[0]:
                                                            return None
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
        return None


def _scrape_page(url: str) -> list[dict]:
                """Scrape any web page and return its main content as a single post."""
                try:
                                    resp = requests.get(url, headers=_HEADERS, timeout=20, verify=True)
                                    resp.raise_for_status()
except requests.exceptions.SSLError:
        # Retry without SSL verification for sites with certificate issues
        resp = requests.get(url, headers=_HEADERS, timeout=20, verify=False)
        resp.raise_for_status()
except requests.RequestException as e:
        raise RuntimeError(f"Could not fetch {url}: {e}")

    # Decode response — respect the charset from Content-Type header
    html = _decode_response(resp)

    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else url

    # Main content: try known selectors, then fall back to full body
    content_html = None
    for selector in _CONTENT_SELECTORS:
                        el = soup.select_one(selector)
                        if el:
                                                content_html = str(el)
                                                break
                                        if not content_html:
                                                            body = soup.find("body")
                                                            content_html = str(body) if body else html

    content = _clean_content(content_html)

    if not content.strip():
                        raise RuntimeError(
                            f"Page was fetched successfully but no readable text content could be "
                            f"extracted from {url}. Try linking to a specific article page instead of "
                            f"the homepage."
    )

    slug = re.sub(r"[^a-z0-9]+", "-", url.split("//")[-1].lower()).strip("-")
    return [{"id": 1, "slug": slug, "title": title, "content": content, "link": url}]


def _decode_response(resp) -> str:
                """Decode an HTTP response to a string, handling non-UTF-8 encodings."""
    # requests sets resp.encoding from the Content-Type header charset.
    # If it's explicitly set (not the default ISO-8859-1 guess), trust it.
    encoding = resp.encoding or "utf-8"

    # requests defaults to ISO-8859-1 for text/* with no charset header,
    # but most modern pages without a charset header are actually UTF-8.
    # Use apparent_encoding (chardet/charset-normalizer) as a smarter fallback.
    if encoding.lower() in ("iso-8859-1", "latin-1", "latin1"):
                        apparent = resp.apparent_encoding
        if apparent and apparent.lower() not in ("iso-8859-1", "latin-1", "latin1", "ascii"):
                                encoding = apparent

    return resp.content.decode(encoding, errors="replace")


def _strip_html(html: str) -> str:
                return BeautifulSoup(html, "html.parser").get_text()


def _clean_content(html: str) -> str:
                soup = BeautifulSoup(html, "html.parser")
    # Remove non-content elements
    for tag in soup(["script", "style", "figure", "img", "iframe",
                                          "nav", "header", "footer", "aside", "form", "button",
                                          "noscript", "svg", "canvas"]):
                                                              tag.decompose()
                                                          text = soup.get_text(separator="\n")
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
