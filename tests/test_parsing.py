from worker.workflows.veille import (
    _matches_keywords,
    _parse_date,
    _parse_feed,
    _parse_html_links,
    _clean_text,
)


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Test</title>
<item>
  <title>Decret relatif au teletravail dans la fonction publique</title>
  <link>https://example.gouv.fr/decret-1</link>
  <pubDate>Mon, 09 Nov 2026 10:00:00 +0100</pubDate>
  <description>&lt;p&gt;Un decret important&lt;/p&gt;</description>
</item>
<item>
  <title>Item sans date</title>
  <link>https://example.gouv.fr/item-2</link>
</item>
</channel></rss>"""


def test_parse_feed_extracts_items():
    entries = _parse_feed(RSS_SAMPLE)
    assert len(entries) == 2
    title, link, published, summary = entries[0]
    assert "teletravail" in title
    assert link == "https://example.gouv.fr/decret-1"
    assert published == "Mon, 09 Nov 2026 10:00:00 +0100"
    assert "decret" in summary


def test_parse_date_rfc822():
    parsed = _parse_date("Mon, 09 Nov 2026 10:00:00 +0100")
    assert parsed is not None
    assert parsed.year == 2026 and parsed.month == 11


def test_parse_date_iso():
    assert _parse_date("2026-11-09") is not None
    assert _parse_date("2026-11-09T10:00:00Z") is not None
    assert _parse_date("09/11/2026") is not None
    assert _parse_date("n'importe quoi") is None
    assert _parse_date(None) is None


def test_clean_text_strips_html():
    assert _clean_text("<p>Bonjour &agrave; tous</p>") == "Bonjour à tous"


def test_keywords_filter():
    assert _matches_keywords("Reforme de l'assurance chomage", None, ["chomage"])
    assert not _matches_keywords("Agriculture bio", None, ["chomage"])
    assert _matches_keywords("Titre neutre", None, [])


HTML_SAMPLE = """
<html><body>
<h2>BO du 13 mars 2026</h2>
<a href="/document/nor-SFHS2606322J">Circulaire du 13 mars 2026 -organisation</a>
<a href="https://autre.site.fr/page">Lien externe sans date</a>
</body></html>"""


def test_parse_html_links():
    entries = _parse_html_links(HTML_SAMPLE, "https://bulletins-officiels.social.gouv.fr/x")
    assert entries[0][0].startswith("Circulaire du 13 mars 2026")
    assert entries[0][1] == "https://bulletins-officiels.social.gouv.fr/document/nor-SFHS2606322J"
    assert entries[0][2] == "2026-03-13"
    assert entries[1][2] is None
