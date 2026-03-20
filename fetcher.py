import re
import requests
from bs4 import BeautifulSoup
import config

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_CONTENT_SELECTORS = [
    "article", "main", '[role="main"]',
    "#bodytext", "#body-text", "#main-content", "#page-content", "#article-content",
    ".post-content", ".entry-content", ".article-body", ".article-content",
    ".content-body", ".content", "#content", ".container",
]


def get_posts(per_page: int = 20) -> list[dict]:
    base_url = config.WP_SITE_URL.rstrip("/")
    wp_posts = _try_wordpress_api(base_url, per_page)
    if wp_posts is not None:
        return wp_posts
    return _scrape_page(base_url)


def _try_wordpress_api(base_url: str, per_page: int):
    url = f"{base_url}/wp-json/wp/v2/posts"
    params = {"per_page": per_page, "orderby": "date", "status": "publish"}
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
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
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20, verify=True)
        resp.raise_for_status()
    except requests.exceptions.SSLError:
        resp = requests.get(url, headers=_HEADERS, timeout=20, verify=False)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Could not fetch {url}: {e}")

    html = _decode_response(resp)
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else url

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
            f"Page fetched OK but no readable text found at {url}. "
            "Try a specific article URL instead of the homepage."
        )

    slug = re.sub(r"[^a-z0-9]+", "-", url.split("//")[-1].lower()).strip("-")
    return [{"id": 1, "slug": slug, "title": title, "content": content, "link": url}]


def _decode_response(resp) -> str:
    encoding = resp.encoding or "utf-8"
    if encoding.lower() in ("iso-8859-1", "latin-1", "latin1"):
        apparent = resp.apparent_encoding
        if apparent and apparent.lower() not in ("iso-8859-1", "latin-1", "latin1", "ascii"):
            encoding = apparent
    return resp.content.decode(encoding, errors="replace")


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text()


def _clean_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "figure", "img", "iframe",
                     "nav", "header", "footer", "aside", "form", "button",
                     "noscript", "svg", "canvas"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
