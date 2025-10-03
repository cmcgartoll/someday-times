import requests
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

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