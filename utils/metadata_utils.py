from urllib.parse import urlparse, urljoin
import string, html, requests
from bs4 import BeautifulSoup
from utils.pdf_utils import is_pdf_url, try_pdf_title
from utils.reddit_utils import is_reddit_post, old_reddit_url
from utils.doi_utils import extract_doi_from_url, fetch_doi_metadata

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

def pick_largest_icon(icons, base):
    best = None
    best_area = -1
    for href, sizes in icons:
        areas = []
        if sizes:
            for s in sizes.split():
                if "x" in s:
                    try:
                        w, h = s.lower().split("x")
                        areas.append(int(w) * int(h))
                    except:
                        pass
        if not areas:
            areas = [64 * 64]
        area = max(areas)
        if area > best_area:
            best_area = area
            best = urljoin(base, href)
    return best

def resolve_best_icon(resp, soup):
    parsed = urlparse(resp.url)
    base = f"{parsed.scheme}://{parsed.hostname}"
    link_svg = soup.find("link", rel=lambda v: v and "icon" in v.lower(),
                         type=lambda t: t and "svg" in (t or "").lower())
    if link_svg and link_svg.get("href"):
        return urljoin(base, link_svg["href"])
    apple_links = soup.find_all("link", rel=lambda v: v and "apple-touch-icon" in v.lower())
    apple_icons = [(l.get("href"), l.get("sizes")) for l in apple_links if l.get("href")]
    if apple_icons:
        best = pick_largest_icon(apple_icons, base)
        if best:
            return best
    icon_links = soup.find_all("link", rel=lambda v: v and "icon" in v.lower())
    icon_icons = [(l.get("href"), l.get("sizes")) for l in icon_links if l.get("href")]
    if icon_icons:
        best = pick_largest_icon(icon_icons, base)
        if best:
            return best
    manifest_link = soup.find("link", rel=lambda v: v and "manifest" in v.lower())
    if manifest_link and manifest_link.get("href"):
        murl = urljoin(base, manifest_link["href"])
        try:
            m = requests.get(murl, timeout=0.5)
            if m.status_code < 400:
                data = m.json()
                icons = [(ic.get("src"), ic.get("sizes")) for ic in data.get("icons", []) if ic.get("src")]
                best = pick_largest_icon(icons, base)
                if best:
                    return best
        except:
            pass
    return f"{base}/favicon.ico"

def slug_to_title(url_path: str, publisher: str) -> str:
    candidate = url_path.strip("/").split("/")[-1]
    candidate = candidate.split("?")[0].split("#")[0]
    candidate = candidate.replace(".html", "").replace(".htm", "")
    candidate = candidate.replace("_", " ").replace("-", " ")

    if publisher == "x.com":
        author = url_path.strip("/").split("/")[0]
        candidate = author + ": Post #" + candidate

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
        if publisher != "x.com":
            w_clean = w.strip(string.punctuation)
        else:
            w_clean = w
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

    fetch_url = target_url
    force_publisher = None
    if is_reddit_post(target_url):
        fetch_url = old_reddit_url(target_url)
        force_publisher = "reddit.com"

    title = publisher = favicon_url = None

    if not any(slug in target_url for slug in PARSEABLE_SLUGS):
        try:
            resp = requests.get(fetch_url, headers=HEADERS, timeout=1)
        except:
            resp = None
    else:
        resp = None
    # HTTP(S) scraping
    if resp and resp.status_code < 400:
        ctype = (resp.headers.get("Content-Type") or "").lower()

        # PDF title scraping
        if "application/pdf" in ctype or is_pdf_url(target_url):
            t = try_pdf_title(resp.content or b"")
            p = urlparse(target_url)
            publisher = force_publisher or (p.hostname or "").replace("www.", "") or "—"
            favicon_url = f"{p.scheme or 'https'}://{p.hostname}/favicon.ico" if p.hostname else None
            return ((" ".join(t.split())) if t else (slug_to_title(p.path, publisher) or target_url),
                    publisher,
                    favicon_url)
        if resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            found = extract_title(soup)
            if found:
                title = html.unescape(" ".join(found.split()))
            p = urlparse(target_url)
            hostname = (p.hostname or "").replace("www.", "")
            publisher = force_publisher or hostname or "—"
            favicon_url = resolve_best_icon(resp, soup)
            if not title or len(title) < 4:
                if publisher in PARSEABLE_SLUGS:
                    title = slug_to_title(p.path, publisher) or target_url
                else:
                    title = target_url
            return title, publisher, favicon_url

    # fallback → DOI metadata
    doi = extract_doi_from_url(target_url)
    if doi:
        title = fetch_doi_metadata(doi)
        p = urlparse(target_url)
        publisher = force_publisher or (p.hostname or "").replace("www.", "") or "—"
        favicon_url = f"{p.scheme or 'https'}://{p.hostname}/favicon.ico" if p.hostname else None
        return (title or doi, publisher, favicon_url)

    # final fallback
    p = urlparse(target_url)
    hostname = (p.hostname or "").replace("www.", "")
    publisher = force_publisher or hostname or "—"
    if publisher in PARSEABLE_SLUGS:
        title = slug_to_title(p.path, publisher) or target_url
    else:
        title = target_url
    favicon_url = f"{p.scheme or 'https'}://{p.hostname}/favicon.ico" if p.hostname else None
    return title, publisher, favicon_url