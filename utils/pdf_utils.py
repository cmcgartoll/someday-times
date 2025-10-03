from urllib.parse import urlparse
from pypdf import PdfReader
import io

def is_pdf_url(url: str) -> bool:
    p = urlparse(url)
    return (p.path or "").lower().endswith(".pdf") or "/pdf/" in (p.path or "")

def try_pdf_title(bytes_data: bytes) -> str | None:
    try:
        reader = PdfReader(io.BytesIO(bytes_data))
        docinfo = reader.metadata  # .title available on many PDFs
        if docinfo and docinfo.title:
            return str(docinfo.title).strip()
    except Exception:
        pass
    return None