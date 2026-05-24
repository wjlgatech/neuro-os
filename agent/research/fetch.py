"""Standalone URL → text fetcher for the research inbox.

This is the one place in neuro-os that reaches out to the network to
turn a raw link into inbox text **without** an external producer
(Hermes / browser share-target / Gmail watcher). It lets the loop run
fully standalone:

    neuro-os research inbox append --fetch-url https://example.com/post
    neuro-os research inbox ingest

Design constraints:

* **stdlib-only HTML path.** Blog / generic pages go through ``urllib``
  + a regex HTML→text reducer (no BeautifulSoup dependency). YouTube
  gets an optional fast-path via ``youtube_transcript_api`` when it's
  installed, and falls back to page title + description when it isn't.
* **best-effort, never fatal to the loop.** A thin page returns
  whatever text we could pull; the human reviewer is the gate
  (``research review --cli``), not this fetcher. The only hard failures
  are an unreachable URL or a source type we deliberately don't fetch
  (PDF / email-body — those still belong to a producer).
* **Law 1 / Law 5.** The result is a frozen :class:`FetchedSource`
  model, range-validated, not a dict. It maps 1:1 into the fields an
  :class:`~agent.research.inbox.InboxRecord` needs.

The extraction heuristics are intentionally kept in parity with the
Hermes ``url-to-inbox`` skill's ``extract_url.py`` so the standalone
path and the producer path agree on what "the text of this URL" means.
If you improve one, port the change to the other.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Source types this fetcher can actually pull over the wire. A subset of
# ``InboxSourceType`` — "pdf" and "email-body" are deliberately excluded
# (they need a producer / OCR step) and raise :class:`FetchError`.
FetchedSourceType = Literal["youtube", "blog", "twitter", "other"]

USER_AGENT = (
    "Mozilla/5.0 (neuro-os research inbox fetcher; "
    "+https://github.com/wjlgatech/neuro-os)"
)
HTTP_TIMEOUT = 20

# Hard caps so a pathological page can never produce a record that
# fails InboxRecord validation downstream. Mirrors the InboxRecord
# field bounds (text 400k, title 400, author 200).
_MAX_TEXT = 400_000
_MAX_TITLE = 400
_MAX_AUTHOR = 200


class FetchError(Exception):
    """Raised when a URL can't be fetched or its source type is one this
    module deliberately doesn't handle (PDF / email-body)."""


class FetchedSource(BaseModel):
    """A URL the fetcher pulled into plain text + best-effort metadata.

    Frozen (Law 5): the network result is an immutable value the CLI
    maps straight into an :class:`InboxRecord`. Field bounds match the
    InboxRecord schema so a valid ``FetchedSource`` always yields a
    valid ``InboxRecord``.
    """

    model_config = ConfigDict(frozen=True)

    url: str = Field(min_length=1, max_length=2000)
    source_type: FetchedSourceType
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    author: str = Field(default="unknown", min_length=1, max_length=_MAX_AUTHOR)
    extracted_text: str = Field(min_length=1, max_length=_MAX_TEXT)


# --------------------------------------------------------------------------
# Source-type detection
# --------------------------------------------------------------------------


_YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "m.youtube.com", "www.youtube.com")
_TWITTER_HOSTS = ("twitter.com", "x.com", "mobile.twitter.com")


def detect_source_type(url: str) -> str:
    """Best-effort source-type guess from the URL host / suffix.

    Returns one of youtube / twitter / pdf / blog. ``pdf`` is detectable
    but not fetchable here — :func:`fetch_url` turns it into a
    :class:`FetchError` with a pointer to the producer path.
    """
    host = ""
    m = re.match(r"https?://([^/]+)", url)
    if m:
        host = m.group(1).lower()
    if any(host == h or host.endswith("." + h) for h in _YOUTUBE_HOSTS):
        return "youtube"
    if any(host == h or host.endswith("." + h) for h in _TWITTER_HOSTS):
        return "twitter"
    if url.lower().split("?", 1)[0].endswith(".pdf"):
        return "pdf"
    return "blog"


# --------------------------------------------------------------------------
# HTML reducer (stdlib only) — kept in parity with Hermes extract_url.py
# --------------------------------------------------------------------------


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_AUTHOR_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"'](?:author|article:author)[\"'][^>]*"
    r"content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_META_DESC_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"']"
    r"(?:description|og:description|twitter:description)[\"'][^>]*"
    r"content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_OG_TITLE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:title[\"'][^>]*content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
    "&#39;": "'", "&nbsp;": " ", "&apos;": "'",
}


def _decode_entities(s: str) -> str:
    for k, v in _HTML_ENTITIES.items():
        s = s.replace(k, v)

    def _num(match: re.Match) -> str:
        code = match.group(1)
        try:
            if code.lower().startswith("x"):
                return chr(int(code[1:], 16))
            return chr(int(code))
        except ValueError:
            return match.group(0)

    return re.sub(r"&#(x?[0-9a-fA-F]+);", _num, s)


def html_to_text(html: str) -> str:
    """Reduce an HTML document to readable plain text (stdlib only)."""
    cleaned = _SCRIPT_RE.sub(" ", html)
    cleaned = _STYLE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"</(p|div|li|h[1-6]|br)\s*>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _decode_entities(cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def html_title(html: str) -> Optional[str]:
    m = _OG_TITLE_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    m = _TITLE_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    return None


def html_author(html: str) -> Optional[str]:
    m = _META_AUTHOR_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    return None


def html_description(html: str) -> Optional[str]:
    m = _META_DESC_RE.search(html)
    if m:
        return _decode_entities(m.group(1)).strip()
    return None


# --------------------------------------------------------------------------
# Fetchers
# --------------------------------------------------------------------------


def fetch_html(url: str, *, timeout: int = HTTP_TIMEOUT) -> str:
    """Fetch a URL and decode to text. Network failures raise
    ``urllib.error.URLError`` (wrapped into :class:`FetchError` by
    :func:`fetch_url`)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — explicit http(s) only
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read()
    return raw.decode(charset, errors="replace")


def _youtube_video_id(url_or_id: str) -> Optional[str]:
    s = url_or_id.strip()
    for pat in (
        r"(?:v=|youtu\.be/|shorts/|embed/|live/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ):
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


_PREFERRED_TRANSCRIPT_LANGS = ("en", "en-US", "en-GB")


def _youtube_transcript_text(video_id: str) -> Optional[str]:
    """Return the transcript text for ``video_id`` or None.

    Supports both youtube_transcript_api flavours:
      * legacy (<1.0): ``YouTubeTranscriptApi.get_transcript`` (classmethod,
        returns list[dict] with a ``text`` key);
      * modern (>=1.0): instance ``YouTubeTranscriptApi().fetch`` /
        ``.list`` (returns a ``FetchedTranscript`` of snippet objects
        with a ``.text`` attribute).

    Tries English first, then falls back to whatever transcript the video
    has (auto-generated / non-English are fine — the downstream LLM reads
    any language).
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
    except ImportError:
        return None

    # Legacy classmethod API.
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            try:
                segs = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=list(_PREFERRED_TRANSCRIPT_LANGS)
                )
            except Exception:  # noqa: BLE001 — any language
                segs = YouTubeTranscriptApi.get_transcript(video_id)
            text = "\n".join(s["text"] for s in segs if s.get("text"))
            return text.strip() or None
        except Exception:  # noqa: BLE001 — no transcript available
            return None

    # Modern instance API.
    try:
        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=list(_PREFERRED_TRANSCRIPT_LANGS))
        except Exception:  # noqa: BLE001 — preferred langs absent; take any
            transcript = next(iter(api.list(video_id)), None)
            if transcript is None:
                return None
            fetched = transcript.fetch()
        text = "\n".join(
            getattr(s, "text", "") for s in fetched if getattr(s, "text", "")
        )
        return text.strip() or None
    except Exception:  # noqa: BLE001 — no transcript available
        return None


def _extract_youtube(url: str, *, timeout: int) -> dict:
    """YouTube transcript via youtube_transcript_api when installed;
    fall back to page title + description otherwise."""
    video_id = _youtube_video_id(url) or url
    title: Optional[str] = None
    author: Optional[str] = None
    html = ""
    try:
        html = fetch_html(
            f"https://www.youtube.com/watch?v={video_id}", timeout=timeout
        )
        title = html_title(html)
        m = re.search(r'"author":"([^"]+)"', html)
        if m:
            author = m.group(1)
    except Exception:  # noqa: BLE001 — metadata is best-effort
        pass

    transcript = _youtube_transcript_text(video_id)
    if transcript:
        return {
            "title": title or f"YouTube video {video_id}",
            "author": author or "unknown",
            "extracted_text": transcript,
        }

    # No transcript (library missing, or none published) — description fallback.
    desc = html_description(html) if html else None
    return {
        "title": title or f"YouTube video {video_id}",
        "author": author or "unknown",
        "extracted_text": (
            (desc or "")
            + "\n\n(no transcript available — install `youtube-transcript-api` "
            "for full transcripts, or the video may have captions disabled)"
        ),
    }


def _extract_blog(url: str, *, timeout: int) -> dict:
    html = fetch_html(url, timeout=timeout)
    return {
        "title": html_title(html) or url,
        "author": html_author(html) or "unknown",
        "extracted_text": html_to_text(html),
    }


def _extract_twitter(url: str, *, timeout: int) -> dict:
    """X/Twitter is client-rendered; static HTML gives us the meta
    description + a hint. Full threads still want a producer upstream."""
    html = fetch_html(url, timeout=timeout)
    desc = html_description(html) or ""
    return {
        "title": html_title(html) or url,
        "author": "unknown",
        "extracted_text": desc + (
            "\n\n(X/Twitter renders threads client-side; for full thread text, "
            "prefer a producer skill upstream and `append --text-file`.)"
        ),
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def fetch_url(
    url: str,
    *,
    source_type: str = "auto",
    timeout: int = HTTP_TIMEOUT,
) -> FetchedSource:
    """Fetch ``url`` and return a frozen :class:`FetchedSource`.

    ``source_type="auto"`` (default) detects from the URL host. Pass an
    explicit value to override detection (e.g. force ``blog`` parsing of
    a page on a YouTube domain).

    Raises :class:`FetchError` for an unreachable URL, an empty page, or
    a source type this module doesn't fetch (``pdf`` / ``email-body``).
    """
    if not url or not url.strip():
        raise FetchError("empty url")
    url = url.strip()

    st = source_type if source_type and source_type != "auto" else detect_source_type(url)

    if st in ("pdf", "email-body"):
        raise FetchError(
            f"source_type {st!r} is not fetchable standalone — feed the "
            f"extracted text via `--text-file` (use a producer / OCR step "
            f"to get the text first)."
        )

    try:
        if st == "youtube":
            payload = _extract_youtube(url, timeout=timeout)
        elif st == "twitter":
            payload = _extract_twitter(url, timeout=timeout)
        else:  # blog / other / anything else → generic HTML
            st = st if st in ("blog", "other") else "blog"
            payload = _extract_blog(url, timeout=timeout)
    except urllib.error.URLError as e:
        raise FetchError(f"fetch failed for {url}: {e}") from e
    except FetchError:
        raise
    except Exception as e:  # noqa: BLE001 — surface any parse failure cleanly
        raise FetchError(f"extraction failed for {url}: {e}") from e

    text = (payload.get("extracted_text") or "").strip()
    if not text:
        raise FetchError(
            f"no extractable text at {url} (page may be empty or "
            f"client-rendered)"
        )

    title = (payload.get("title") or url).strip()[:_MAX_TITLE] or url[:_MAX_TITLE]
    author = (payload.get("author") or "unknown").strip()[:_MAX_AUTHOR] or "unknown"

    return FetchedSource(
        url=url[:2000],
        source_type=st,  # type: ignore[arg-type]
        title=title,
        author=author,
        extracted_text=text[:_MAX_TEXT],
    )


__all__ = [
    "FetchError",
    "FetchedSource",
    "FetchedSourceType",
    "detect_source_type",
    "fetch_html",
    "fetch_url",
    "html_author",
    "html_description",
    "html_title",
    "html_to_text",
]
