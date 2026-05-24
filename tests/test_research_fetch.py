"""
Tests for the standalone URL fetcher (``agent/research/fetch.py``) and
its ``fetch_url_to_inbox`` library entry point.

Strategy: hermetic — the network boundary (``fetch_html``) is
monkeypatched to canned HTML, so no test touches the network. This
mirrors ``test_research_inbox.py``: exercise the library functions
directly (no CLI subprocess, no flywheel-loop import, no live LLM).
The CLI handler is thin glue over ``fetch_url_to_inbox``, which IS
tested end-to-end here against a tmp home.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import agent.research.fetch as fetchmod
from agent.research.fetch import (
    FetchError,
    FetchedSource,
    detect_source_type,
    fetch_url,
    html_author,
    html_description,
    html_title,
    html_to_text,
)
from agent.research.inbox import (
    InboxRecord,
    default_inbox_path,
    fetch_url_to_inbox,
)


NOW = datetime(2026, 5, 24, 12, 0, 0, tzinfo=timezone.utc)


_BLOG_HTML = """
<html><head>
<title>Raw Title</title>
<meta property="og:title" content="OG Title &amp; Friends" />
<meta name="author" content="Jane Researcher" />
<meta name="description" content="A short description." />
<style>.x{color:red}</style>
</head>
<body>
<script>console.log('noise')</script>
<h1>Heading</h1>
<p>First paragraph about distribution.</p>
<p>Second paragraph about attention.</p>
</body></html>
"""


# ---------------------------------------------------------------------------
# Source-type detection
# ---------------------------------------------------------------------------


class TestDetectSourceType:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=abc123", "youtube"),
            ("https://youtu.be/abc123", "youtube"),
            ("https://m.youtube.com/watch?v=x", "youtube"),
            ("https://twitter.com/user/status/1", "twitter"),
            ("https://x.com/user/status/1", "twitter"),
            ("https://example.com/paper.pdf", "pdf"),
            ("https://example.com/paper.pdf?token=1", "pdf"),
            ("https://example.com/blog/post", "blog"),
            ("https://news.ycombinator.com/item?id=1", "blog"),
        ],
    )
    def test_detection(self, url, expected):
        assert detect_source_type(url) == expected


# ---------------------------------------------------------------------------
# HTML reducer
# ---------------------------------------------------------------------------


class TestHtmlReducer:
    def test_strips_script_and_style(self):
        text = html_to_text(_BLOG_HTML)
        assert "console.log" not in text
        assert "color:red" not in text
        assert "First paragraph about distribution." in text
        assert "Second paragraph about attention." in text

    def test_decodes_entities(self):
        assert html_to_text("<p>A &amp; B &lt; C</p>") == "A & B < C"

    def test_numeric_entities(self):
        assert "'" in html_to_text("<p>it&#39;s</p>")

    def test_title_prefers_og(self):
        assert html_title(_BLOG_HTML) == "OG Title & Friends"

    def test_title_falls_back_to_title_tag(self):
        assert html_title("<title>Just Title</title>") == "Just Title"

    def test_author_from_meta(self):
        assert html_author(_BLOG_HTML) == "Jane Researcher"

    def test_description_from_meta(self):
        assert html_description(_BLOG_HTML) == "A short description."

    def test_missing_metadata_returns_none(self):
        assert html_title("<p>no title</p>") is None
        assert html_author("<p>no author</p>") is None
        assert html_description("<p>no desc</p>") is None


# ---------------------------------------------------------------------------
# YouTube video-id parsing
# ---------------------------------------------------------------------------


class TestYoutubeId:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ],
    )
    def test_extract_id(self, url, expected):
        assert fetchmod._youtube_video_id(url) == expected

    def test_no_id_returns_none(self):
        assert fetchmod._youtube_video_id("https://example.com/page") is None


# ---------------------------------------------------------------------------
# FetchedSource model
# ---------------------------------------------------------------------------


class TestFetchedSourceModel:
    def test_is_frozen(self):
        fs = FetchedSource(
            url="https://x.com/a",
            source_type="blog",
            title="t",
            extracted_text="body",
        )
        with pytest.raises(Exception):
            fs.title = "mutated"  # type: ignore[misc]

    def test_rejects_empty_text(self):
        with pytest.raises(Exception):
            FetchedSource(
                url="https://x.com/a", source_type="blog", title="t",
                extracted_text="",
            )

    def test_rejects_bad_source_type(self):
        with pytest.raises(Exception):
            FetchedSource(
                url="https://x.com/a", source_type="pdf",  # not fetchable
                title="t", extracted_text="body",
            )

    def test_fields_satisfy_inbox_record(self):
        """A valid FetchedSource must always yield a valid InboxRecord —
        bounds are intentionally aligned. If this breaks, the two schemas
        have drifted."""
        fs = FetchedSource(
            url="https://x.com/a", source_type="blog", title="t",
            author="me", extracted_text="body text",
        )
        rec = InboxRecord(
            url=fs.url,
            source_type=fs.source_type,
            title=fs.title,
            author=fs.author,
            extracted_text=fs.extracted_text,
            extracted_at=NOW,
        )
        assert rec.source_type == "blog"
        assert rec.extracted_text == "body text"


# ---------------------------------------------------------------------------
# fetch_url (network monkeypatched)
# ---------------------------------------------------------------------------


class TestFetchUrl:
    def test_blog_fetch(self, monkeypatch):
        monkeypatch.setattr(fetchmod, "fetch_html", lambda url, **kw: _BLOG_HTML)
        fs = fetch_url("https://example.com/blog/post")
        assert isinstance(fs, FetchedSource)
        assert fs.source_type == "blog"
        assert fs.title == "OG Title & Friends"
        assert fs.author == "Jane Researcher"
        assert "First paragraph about distribution." in fs.extracted_text
        assert "console.log" not in fs.extracted_text

    def test_explicit_source_type_override(self, monkeypatch):
        """Forcing blog parsing on a youtube-host URL must skip the
        transcript path and just reduce the HTML."""
        monkeypatch.setattr(fetchmod, "fetch_html", lambda url, **kw: _BLOG_HTML)
        fs = fetch_url("https://youtube.com/watch?v=abc", source_type="blog")
        assert fs.source_type == "blog"
        assert fs.title == "OG Title & Friends"

    def test_pdf_raises_fetch_error(self):
        with pytest.raises(FetchError) as ei:
            fetch_url("https://example.com/paper.pdf")
        assert "not fetchable" in str(ei.value)

    def test_email_body_raises_fetch_error(self):
        with pytest.raises(FetchError):
            fetch_url("https://example.com/x", source_type="email-body")

    def test_empty_url_raises(self):
        with pytest.raises(FetchError):
            fetch_url("   ")

    def test_network_failure_wrapped(self, monkeypatch):
        import urllib.error

        def _boom(url, **kw):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(fetchmod, "fetch_html", _boom)
        with pytest.raises(FetchError) as ei:
            fetch_url("https://example.com/post")
        assert "fetch failed" in str(ei.value)

    def test_empty_body_raises(self, monkeypatch):
        monkeypatch.setattr(
            fetchmod, "fetch_html",
            lambda url, **kw: "<html><body></body></html>",
        )
        with pytest.raises(FetchError) as ei:
            fetch_url("https://example.com/empty")
        assert "no extractable text" in str(ei.value)

    def test_oversize_text_is_truncated(self, monkeypatch):
        big = "<p>" + ("word " * 200_000) + "</p>"  # > 400k chars
        monkeypatch.setattr(fetchmod, "fetch_html", lambda url, **kw: big)
        fs = fetch_url("https://example.com/huge")
        assert len(fs.extracted_text) <= 400_000


# ---------------------------------------------------------------------------
# fetch_url_to_inbox (full standalone path against a tmp home)
# ---------------------------------------------------------------------------


class TestFetchUrlToInbox:
    def test_appends_one_record(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fetchmod, "fetch_html", lambda url, **kw: _BLOG_HTML)
        offset, record = fetch_url_to_inbox(
            "https://example.com/blog/post",
            home=tmp_path,
            urge_tag="novelty",
            topic_tags=["distribution"],
            now=NOW,
        )
        assert offset == 0
        assert isinstance(record, InboxRecord)
        assert record.source_type == "blog"
        assert record.title == "OG Title & Friends"
        assert record.urge_tag == "novelty"
        assert record.topic_tags == ["distribution"]

        # The record landed in the inbox JSONL under the tmp home.
        inbox = default_inbox_path(tmp_path)
        lines = inbox.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["url"] == "https://example.com/blog/post"
        assert payload["source_type"] == "blog"
        assert payload["extracted_text"].startswith("Heading") or \
            "distribution" in payload["extracted_text"]

    def test_overrides_win(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fetchmod, "fetch_html", lambda url, **kw: _BLOG_HTML)
        _, record = fetch_url_to_inbox(
            "https://example.com/blog/post",
            home=tmp_path,
            stored_url="https://canonical.example.com/post",
            title="My Override Title",
            author="Override Author",
            now=NOW,
        )
        assert record.url == "https://canonical.example.com/post"
        assert record.title == "My Override Title"
        assert record.author == "Override Author"

    def test_pdf_propagates_fetch_error(self, tmp_path):
        with pytest.raises(FetchError):
            fetch_url_to_inbox(
                "https://example.com/paper.pdf", home=tmp_path, now=NOW,
            )
