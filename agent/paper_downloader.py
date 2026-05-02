"""
Paper Downloader + Parser (Minimal)

Downloads PDFs or HTML and converts to text.
This is intentionally simple and deterministic.
"""

import requests
from pathlib import Path


def download(url: str, out_path: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    Path(out_path).write_bytes(r.content)


def html_to_text(html_bytes: bytes) -> str:
    text = html_bytes.decode("utf-8", errors="ignore")
    # naive strip
    return text[:20000]


if __name__ == "__main__":
    url = "https://example.com"
    download(url, "sources/raw/example.html")
