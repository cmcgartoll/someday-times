from urllib.parse import urlparse, urlunparse

def is_reddit_post(url: str) -> bool:
    p = urlparse(url)
    host = (p.hostname or "").lower()
    return host.endswith("reddit.com") and "/comments/" in (p.path or "")

def old_reddit_url(url: str) -> str:
    p = urlparse(url)
    host = (p.hostname or "")
    if host.startswith("www."):
        host = host[4:]
    return urlunparse((p.scheme or "https", "old." + host, p.path, p.params, p.query, p.fragment))