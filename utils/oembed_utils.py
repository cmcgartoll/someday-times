import requests, html
from urllib.parse import urlparse
import re
from bs4 import BeautifulSoup

OEMBED_PROVIDERS = {
    "open.spotify.com": "https://open.spotify.com/oembed?url={url}",
    "youtube.com": "https://www.youtube.com/oembed?url={url}&format=json",
    "youtu.be": "https://www.youtube.com/oembed?url={url}&format=json",
    "twitter.com": "https://publish.twitter.com/oembed?url={url}",
    "x.com": "https://publish.twitter.com/oembed?url={url}",
    "vimeo.com": "https://vimeo.com/api/oembed.json?url={url}",
    "soundcloud.com": "https://soundcloud.com/oembed?url={url}&format=json",
    "reddit.com": "https://www.reddit.com/oembed?url={url}&format=json",
}

def try_oembed(target_url: str, publisher: str, timeout=3):
    endpoint = icon_url = None
    for key, ep in OEMBED_PROVIDERS.items():
        if publisher.endswith(key):  
            endpoint = ep.format(url=target_url)
            break
    if not endpoint:
        return None, None, None

    try:
        r = requests.get(endpoint, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if publisher == "reddit.com":
            title = data.get("title")
            if title:
                title = html.unescape(title.strip())
        elif publisher == "x.com":
            author = data.get("author_name")
            raw_html = data.get("html", "")
            match = re.search(r"<p[^>]*>(.*?)</p>", raw_html, re.DOTALL)
            if match:
                inner_html = match.group(1)
                # Parse with BeautifulSoup to remove tags like <a>
                text = BeautifulSoup(inner_html, "html.parser").get_text(" ", strip=True)
                # Decode HTML entities (&amp; → &)
                text = html.unescape(text)
                 # Remove trailing t.co links or any trailing URL
                text = re.sub(r"https?://t\.co/\S+$", "", text).strip()
            else:
                text = None

            if text:
                title = f"{author}: {text}"
            else:
                title = author 
        elif publisher == "open.spotify.com":
            title = data.get("title")
            icon_url = data.get("thumbnail_url")

            if title:
                title = html.unescape(title.strip())
            if icon_url:
                icon_url = html.unescape(icon_url.strip())
            title = title
            publisher = "spotify.com"
        else:
            title = data.get("title")
            author = data.get("author_name")
            if title:
                title = html.unescape(title.strip())
            if author:
                author = html.unescape(author.strip())
            title = title + " by " + author
        return title, publisher, icon_url
    except Exception as e:
        return None, None, None
