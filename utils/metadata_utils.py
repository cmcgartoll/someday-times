from urllib.parse import urlparse, urljoin
import string, html, requests
from bs4 import BeautifulSoup
from utils.pdf_utils import is_pdf_url, try_pdf_title
from utils.doi_utils import extract_doi_from_url, fetch_doi_metadata
from utils.oembed_utils import try_oembed
from utils.icon_utils import resolve_best_icon

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

PARSEABLE_SLUGS = {
    "wsj.com",
    "washingtonpost.com",
    "facebook.com",
    "x.com"
}

def slug_to_title(url_path: str, publisher: str) -> str:
    candidate = url_path.strip("/").split("/")[-1]
    candidate = candidate.split("?")[0].split("#")[0]
    candidate = candidate.replace(".html", "").replace(".htm", "")
    candidate = candidate.replace("_", " ").replace("-", " ")

    if publisher in {"wsj.com", "medium.com"}:
        candidate = " ".join(candidate.split(" ")[:-1])
    candidate = " ".join(candidate.split())
    if not candidate:
        return ""
    small = {"a","an","and","as","at","but","by","for","in","of","on","or","to","via","vs"}
    words = candidate.split()
    out = []
    w_clean = ""
    for i, w in enumerate(words):
        w_clean = w.strip(string.punctuation)
        if i not in (0, len(words)-1) and w_clean.lower() in small:
            out.append(w_clean.lower())
        else:
            out.append(w_clean.capitalize())
    return " ".join(out)

def extract_title(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "og:title"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None

def fetch_metadata(target_url: str):
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    title = None
    p = urlparse(target_url)
    publisher = (p.hostname or "").replace("www.", "") or "—"
    favicon_url = f"{p.scheme or 'https'}://{p.hostname}/favicon.ico" if p.hostname else None

    # Try OEmbed API first
    oembed_title, oembed_publisher, oembed_icon_url = try_oembed(target_url, publisher)
    if oembed_title and not oembed_icon_url:
        try:
            resp = requests.get(target_url, headers=HEADERS, timeout=1)
            if resp and resp.status_code < 400 and resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                favicon_url = resolve_best_icon(resp, soup)
        except:
            pass
        return oembed_title, oembed_publisher, oembed_icon_url or favicon_url

    # Arxiv.org special case (to get the title from the abstract page)
    if publisher == "arxiv.org" and "/pdf/" in p.path:
        target_url = target_url.replace("/pdf/", "/abs/")
        try:
            resp = requests.get(target_url, headers=HEADERS, timeout=1)
            if resp and resp.status_code < 400 and resp.text:
                soup = BeautifulSoup(resp.text, "html.parser")
                found = extract_title(soup)
                if found:
                    title = html.unescape(" ".join(found.split()))
        except:
            pass
        if title:
            return title, publisher, favicon_url

    # DOI metadata (Science.org, etc.)
    doi = extract_doi_from_url(target_url)
    if doi:
        title = fetch_doi_metadata(doi)
        return (title or doi, publisher, favicon_url)

    # Generic HTTP(s) scraping
    if not any(slug in target_url for slug in PARSEABLE_SLUGS):
        try:
            resp = requests.get(target_url, headers=HEADERS, timeout=1)
        except:
            resp = None

        if resp and resp.status_code < 400:
            # PDF title scraping
            if publisher != "arxiv.org":
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if "application/pdf" in ctype or is_pdf_url(target_url):
                    t = try_pdf_title(resp.content or b"")
                    return (" ".join(t.split())) if t else (slug_to_title(p.path, publisher) or target_url),
                    publisher,
                    favicon_url

            soup = BeautifulSoup(resp.text, "html.parser")
            found = extract_title(soup)
            if found:
                title = html.unescape(" ".join(found.split()))
            favicon_url = resolve_best_icon(resp, soup)
            if title:
                return title, publisher, favicon_url

    # final fallback (slug-based title) or target URL
    if publisher in PARSEABLE_SLUGS:
        title = slug_to_title(p.path, publisher) or target_url
    else:
        title = target_url
    return title, publisher, favicon_url