"""Unit tests for the bibliography service: round-trips + citation styles."""
from __future__ import annotations

from app.application.services.bibliography import (
    format_citation,
    normalize_title,
    parse_bibtex,
    parse_csv,
    parse_ris,
    serialize_records,
    to_bibtex,
)


def _record(**overrides):
    record = {
        "publication_type": "journal_article",
        "title": "Deep Learning for Catalysis",
        "authors": ["Gupta, Vipin", "Sharma, Asha"],
        "journal": "Nature Catalysis",
        "doi": "10.1038/s41929-024-00001",
        "year": 2025,
        "volume": "7",
        "issue": "3",
        "pages": "201-214",
        "publisher": "Springer Nature",
        "keywords": ["catalysis", "deep learning"],
        "issn": "2520-1158",
        "publisher_url": "https://doi.org/10.1038/s41929-024-00001",
        "language": "en",
    }
    record.update(overrides)
    return record


def test_bibtex_round_trip():
    text = to_bibtex(_record())
    assert text.startswith("@article{Gupta2025")
    parsed = parse_bibtex(text)
    assert len(parsed) == 1
    got = parsed[0]
    assert got["publication_type"] == "journal_article"
    assert got["title"] == "Deep Learning for Catalysis"
    assert got["authors"] == ["Gupta, Vipin", "Sharma, Asha"]
    assert got["journal"] == "Nature Catalysis"
    assert got["doi"] == "10.1038/s41929-024-00001"
    assert got["year"] == 2025
    assert got["volume"] == "7" and got["issue"] == "3" and got["pages"] == "201-214"
    assert got["keywords"] == ["catalysis", "deep learning"]


def test_bibtex_parse_typical_zotero_export():
    text = r"""@article{vaswani2017attention,
	title = {Attention Is All You Need},
	author = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
	journal = {Advances in Neural Information Processing Systems},
	volume = {30},
	year = {2017},
	url = {https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html}
}
@book{sutton2018reinforcement,
	title = {Reinforcement Learning: An Introduction},
	author = {Sutton, Richard S. and Barto, Andrew G.},
	publisher = {MIT Press},
	year = {2018},
	isbn = {9780262039246}
}
@phdthesis{kingma2014adam,
	title = {Adam: A Method for Stochastic Optimization},
	author = {Kingma, Diederik P. and Ba, Jimmy},
	school = {arXiv},
	year = {2014}
}
"""
    records = parse_bibtex(text)
    assert len(records) == 3
    assert records[0]["authors"][0] == "Vaswani, Ashish"
    assert records[0]["publisher_url"].startswith("https://proceedings")
    assert records[1]["publication_type"] == "book"
    assert records[1]["publisher"] == "MIT Press"
    assert records[1]["isbn"] == "9780262039246"
    assert records[2]["publication_type"] == "thesis"
    assert records[2]["publisher"] == "arXiv"


def test_ris_round_trip():
    text = serialize_records([_record()], "ris")
    assert text.startswith("TY  - JOUR")
    assert "ER  -" in text
    parsed = parse_ris(text)
    assert len(parsed) == 1
    got = parsed[0]
    assert got["title"] == "Deep Learning for Catalysis"
    assert got["authors"] == ["Gupta, Vipin", "Sharma, Asha"]
    assert got["journal"] == "Nature Catalysis"
    assert got["pages"] == "201-214"
    assert got["doi"] == "10.1038/s41929-024-00001"
    assert got["year"] == 2025


def test_csv_round_trip_full_field_set():
    original = _record(tags=["ml"], collections=["Papers"], indexing=["SCOPUS"],
                       citation_count=12, impact_factor=37.8, quartile="Q1")
    text = serialize_records([original], "csv")
    assert text.splitlines()[0].startswith("publication_type,title,authors")
    parsed = parse_csv(text)
    got = parsed[0]
    assert got["title"] == "Deep Learning for Catalysis"
    assert got["authors"] == ["Gupta, Vipin", "Sharma, Asha"]
    assert got["keywords"] == ["catalysis", "deep learning"]
    assert got["indexing"] == ["SCOPUS"]
    assert got["collections"] == ["Papers"]
    assert got["citation_count"] == 12
    assert got["impact_factor"] == 37.8


def test_citation_styles():
    record = _record()
    apa = format_citation(record, "apa")
    assert apa.startswith("Gupta, V., & Sharma, A. (2025).")
    assert "Deep Learning for Catalysis." in apa
    assert "*Nature Catalysis*" in apa
    assert "7(3), 201-214" in apa
    assert "https://doi.org/10.1038/s41929-024-00001" in apa

    ieee = format_citation(record, "ieee")
    assert ieee.startswith("V. Gupta and A. Sharma,")
    assert '"Deep Learning for Catalysis,"' in ieee
    assert "vol. 7" in ieee and "no. 3" in ieee and "pp. 201-214" in ieee
    assert "doi: 10.1038/s41929-024-00001" in ieee

    vancouver = format_citation(record, "vancouver")
    assert vancouver.startswith("Gupta V, Sharma A.")
    assert "Nature Catalysis. 2025;7(3):201-214." in vancouver

    chicago = format_citation(record, "chicago")
    assert '"Deep Learning for Catalysis."' in chicago
    assert "7, no. 3 (2025): 201-214" in chicago

    harvard = format_citation(record, "harvard")
    assert harvard.startswith("Gupta, V., & Sharma, A. (2025)")
    assert "'Deep Learning for Catalysis'" in harvard

    bib = format_citation(record, "bibtex")
    assert bib.startswith("@article{")


def test_citation_no_doi_and_missing_venue():
    record = _record(doi=None, journal=None, conference=None, publisher=None)
    for style in ("apa", "ieee", "vancouver", "chicago", "harvard"):
        text = format_citation(record, style)
        assert "doi" not in text.lower()
        assert "Deep Learning for Catalysis" in text


def test_normalize_title_for_duplicates():
    assert normalize_title("  Deep   Learning  ") == "deep learning"
    assert normalize_title("Catalysis") == normalize_title("  CATALYSIS ")
