import re, requests
def extract_doi_from_url(url: str) -> str | None:
    m = re.search(r'/doi/(?:abs/|full/|pdf/|suppl/)?(10\.\d{4,9}/[^\s/]+)', url)
    if m:
        return m.group(1)
    return None

def fetch_doi_metadata(doi: str) -> str | None:
    api_url = f"https://api.crossref.org/works/{doi}"
    try:
        r = requests.get(api_url, headers={"Accept": "application/json"}, timeout=1)
        if r.status_code == 200:
            data = r.json()
            title_list = data.get("message", {}).get("title", [])
            if title_list:
                return title_list[0].strip()
    except:
        pass
    return None