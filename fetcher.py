import re
import requests
from bs4 import BeautifulSoup
import config


def get_posts(per_page: int = 20) -> list[dict]:
    """Fetch recent posts from WordPress REST API."""
    url = f"{config.WP_SITE_URL}/wp-json/wp/v2/posts"
    params = {"per_page": per_page, "orderby": "date", "status": "publish"}

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BlogToCarousel/1.0)",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch posts from {url}: {e}")

    posts = []
    for item in resp.json():
        posts.append({
            "id": item["id"],
            "slug": item["slug"],
            "title": _strip_html(item["title"]["rendered"]),
            "content": _clean_content(item["content"]["rendered"]),
            "link": item["link"],
        })
    return posts


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text()


def _clean_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # Remove non-content elements
    for tag in soup(["script", "style", "figure", "img", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
