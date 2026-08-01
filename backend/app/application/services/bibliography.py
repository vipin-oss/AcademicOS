"""Bibliographic record exchange + citation formatting (reference-manager core).

Framework-free Application-layer service (stdlib ``re`` / ``csv`` / ``io``
only) operating on plain record dicts — the same primitive shape the
``MetadataLookup`` port returns and the API mapper produces. Supports:

  - BibTeX import/export          (FR-PUB-003)
  - RIS import/export             (FR-PUB-003)
  - CSV import/export             (FR-PUB-003)
  - Citation generation           (APA / IEEE / Vancouver / Chicago / Harvard)

A *record* is a dict with string keys mirroring the publication field names:
``publication_type``, ``title``, ``authors`` (list[str], canonical
"Family, Given"), ``doi``, ``journal``, ``conference``, ``publisher``,
``year`` (int | None), ``volume``, ``issue``, ``pages``, ``issn``, ``isbn``,
``publisher_url``, ``keywords`` (list[str]), ``abstract``, ``language`` ...
Unknown/empty fields are simply absent.
"""
from __future__ import annotations

import csv
import io
import re

# ---------------------------------------------------------------------------
# Field / type vocabularies
# ---------------------------------------------------------------------------

PUBLICATION_TYPES = (
    "journal_article",
    "conference_paper",
    "book_chapter",
    "book",
    "patent",
    "technical_report",
    "thesis",
    "preprint",
    "other",
)

CITATION_STYLES = ("apa", "ieee", "vancouver", "chicago", "harvard", "bibtex")

EXPORT_FORMATS = ("bibtex", "ris", "csv")

IMPORT_FORMATS = ("bibtex", "ris", "csv")

_BIBTEX_TYPE_FROM_PUB = {
    "journal_article": "article",
    "conference_paper": "inproceedings",
    "book_chapter": "incollection",
    "book": "book",
    "patent": "misc",
    "technical_report": "techreport",
    "thesis": "phdthesis",
    "preprint": "unpublished",
    "other": "misc",
}

_PUB_TYPE_FROM_BIBTEX = {
    "article": "journal_article",
    "inproceedings": "conference_paper",
    "conference": "conference_paper",
    "incollection": "book_chapter",
    "inbook": "book_chapter",
    "book": "book",
    "booklet": "book",
    "patent": "patent",
    "techreport": "technical_report",
    "report": "technical_report",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "unpublished": "preprint",
    "misc": "other",
}

_RIS_TYPE_FROM_PUB = {
    "journal_article": "JOUR",
    "conference_paper": "CPAPER",
    "book_chapter": "CHAP",
    "book": "BOOK",
    "patent": "PAT",
    "technical_report": "RPRT",
    "thesis": "THES",
    "preprint": "GEN",
    "other": "GEN",
}

_PUB_TYPE_FROM_RIS = {
    "JOUR": "journal_article",
    "JFULL": "journal_article",
    "CONF": "conference_paper",
    "CPAPER": "conference_paper",
    "CHAP": "book_chapter",
    "BOOK": "book",
    "PAT": "patent",
    "RPRT": "technical_report",
    "THES": "thesis",
    "GEN": "other",
}

# CSV export column order (round-trip safe — parse_csv reads headers by name).
CSV_COLUMNS = [
    "publication_type", "title", "authors", "corresponding_author",
    "affiliations", "abstract", "keywords", "doi", "isbn", "issn",
    "publisher", "journal", "conference", "volume", "issue", "pages",
    "year", "date", "language", "citation_count", "impact_factor",
    "quartile", "indexing", "publisher_url", "notes", "tags", "collections",
]

_LIST_FIELDS = {"authors", "keywords", "affiliations", "indexing", "tags", "collections"}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """Case-folded, whitespace-collapsed form used for duplicate detection."""
    return " ".join((title or "").casefold().split())


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def join_person_names(authors) -> str:
    """"Family, Given" entries joined the BibTeX way: ``A and B``."""
    return " and ".join(_as_list(authors))


def split_person_names(raw: str) -> list[str]:
    """Split a BibTeX ``and``-joined author string into names."""
    return [part.strip() for part in re.split(r"\s+and\s+", raw or "") if part.strip()]


def _strip_bibtex_markup(value: str) -> str:
    """Remove protective braces and collapse whitespace from a BibTeX value."""
    text = re.sub(r"[{}]", "", value or "")
    return " ".join(text.split())


def _braced(value: str) -> str:
    return "{" + (value or "") + "}"


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------

def to_bibtex(record: dict, cite_key: str | None = None) -> str:
    pub_type = str(record.get("publication_type") or "other")
    entry_type = _BIBTEX_TYPE_FROM_PUB.get(pub_type, "misc")
    key = cite_key or _bibtex_key(record)
    fields: list[tuple[str, str]] = []

    def add(name: str, value) -> None:
        if value is None or value == "" or value == []:
            return
        fields.append((name, str(value)))

    add("title", record.get("title"))
    authors = _as_list(record.get("authors"))
    if authors:
        add("author", join_person_names(authors))
    venue = record.get("journal") or record.get("conference")
    if entry_type in ("inproceedings", "incollection"):
        add("booktitle", record.get("conference") or venue)
        if entry_type == "incollection":
            add("booktitle", record.get("journal") or record.get("conference") or venue)
    else:
        add("journal", venue)
    add("publisher", record.get("publisher"))
    add("year", record.get("year"))
    add("volume", record.get("volume"))
    add("number", record.get("issue"))
    add("pages", record.get("pages"))
    add("doi", record.get("doi"))
    add("issn", record.get("issn"))
    add("isbn", record.get("isbn"))
    add("url", record.get("publisher_url"))
    add("abstract", record.get("abstract"))
    kw = _as_list(record.get("keywords"))
    if kw:
        add("keywords", ", ".join(kw))
    add("language", record.get("language"))
    if pub_type == "patent":
        add("note", "Patent")
    if pub_type == "preprint":
        add("note", "Preprint")

    body = ",\n".join(f"  {name} = {_braced(value)}" for name, value in fields)
    return f"@{entry_type}{{{key},\n{body}\n}}"


def _bibtex_key(record: dict) -> str:
    authors = _as_list(record.get("authors"))
    surname = (authors[0].split(",")[0] if authors else "anon").strip()
    surname = re.sub(r"[^A-Za-z]+", "", surname) or "anon"
    year = record.get("year") or ""
    return f"{surname}{year}"


def parse_bibtex(text: str) -> list[dict]:
    """Parse a BibTeX bibliography into record dicts (tolerant, stdlib-only)."""
    records: list[dict] = []
    for entry_type, body in _split_bibtex_entries(text):
        fields = _split_bibtex_fields(body)
        record: dict = {
            "publication_type": _PUB_TYPE_FROM_BIBTEX.get(entry_type, "other")
        }
        _map_bibtex_fields(record, fields)
        records.append(record)
    return records


def _split_bibtex_entries(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for match in re.finditer(r"@\s*([A-Za-z]+)\s*[({]", text or ""):
        entry_type = match.group(1).lower()
        if entry_type in ("comment", "preamble", "string"):
            continue
        depth = 1
        i = match.end()
        while i < len(text) and depth:
            if text[i] in "({":
                depth += 1
            elif text[i] in ")}":
                depth -= 1
            i += 1
        body = text[match.end():i - 1]
        # drop the cite key (everything up to the first top-level comma)
        key_end = body.find(",")
        entries.append((entry_type, body[key_end + 1:] if key_end != -1 else ""))
    return entries


def _split_bibtex_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pos = 0
    pattern = re.compile(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*")
    while pos < len(body):
        match = pattern.search(body, pos)
        if not match:
            break
        name = match.group(1).lower()
        i = match.end()
        if i < len(body) and body[i] == "{":
            depth, start, i = 1, i + 1, i + 1
            while i < len(body) and depth:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                i += 1
            value = body[start:i - 1]
        elif i < len(body) and body[i] == '"':
            end = body.find('"', i + 1)
            value = body[i + 1:end if end != -1 else len(body)]
            i = (end + 1) if end != -1 else len(body)
        else:
            end = body.find(",", i)
            value = body[i:end if end != -1 else len(body)].strip()
            i = end if end != -1 else len(body)
        fields[name] = value
        pos = i
    return fields


def _map_bibtex_fields(record: dict, fields: dict[str, str]) -> None:
    def take(*names: str) -> str | None:
        for name in names:
            if fields.get(name):
                return _strip_bibtex_markup(fields[name])
        return None

    record["title"] = take("title") or ""
    if fields.get("author"):
        record["authors"] = [
            _strip_bibtex_markup(name) for name in split_person_names(fields["author"])
        ]
    if journal := take("journal", "journaltitle"):
        record["journal"] = journal
    if booktitle := take("booktitle"):
        record["conference"] = booktitle
    if school := take("school", "institution"):
        record["publisher"] = school
    if publisher := take("publisher"):
        record["publisher"] = publisher
    if org := take("organization"):
        record["conference"] = record.get("conference") or org
    if year := take("year"):
        digits = re.search(r"\d{4}", year)
        if digits:
            record["year"] = int(digits.group(0))
    if date := take("date"):
        match = re.match(r"\d{4}(-\d{2})?(-\d{2})?", date)
        if match:
            record["date"] = match.group(0)
    if not record.get("year") and record.get("date", "")[:4].isdigit():
        record["year"] = int(record["date"][:4])
    for src, dest in (
        ("volume", "volume"), ("number", "issue"), ("pages", "pages"),
        ("doi", "doi"), ("issn", "issn"), ("isbn", "isbn"),
        ("abstract", "abstract"), ("language", "language"),
    ):
        if value := take(src):
            record[dest] = value
    if url := take("url"):
        record["publisher_url"] = url
    if keywords := take("keywords"):
        record["keywords"] = [kw.strip() for kw in keywords.split(",") if kw.strip()]
    note = (fields.get("note") or "").lower()
    if note == "preprint" and record["publication_type"] == "other":
        record["publication_type"] = "preprint"
    if note == "patent" and record["publication_type"] == "other":
        record["publication_type"] = "patent"


# ---------------------------------------------------------------------------
# RIS
# ---------------------------------------------------------------------------

_RIS_TAG_FROM_FIELD = {
    "title": "TI",
    "doi": "DO",
    "journal": "JO",
    "conference": "T2",
    "publisher": "PB",
    "volume": "VL",
    "issue": "IS",
    "issn": "SN",
    "isbn": "SN",
    "abstract": "AB",
    "language": "LA",
    "publisher_url": "UR",
}


def to_ris(record: dict) -> str:
    pub_type = str(record.get("publication_type") or "other")
    lines = [f"TY  - {_RIS_TYPE_FROM_PUB.get(pub_type, 'GEN')}"]

    def add(tag: str, value) -> None:
        if value is None or value == "":
            return
        lines.append(f"{tag}  - {value}")

    add(_RIS_TAG_FROM_FIELD["title"], record.get("title"))
    for author in _as_list(record.get("authors")):
        add("AU", author)
    venue = record.get("journal") or record.get("conference")
    if pub_type in ("conference_paper", "book_chapter"):
        add("T2", record.get("conference") or venue)
    else:
        add("JO", venue)
    add("PB", record.get("publisher"))
    if record.get("year"):
        add("PY", record["year"])
    add("D1", record.get("date"))
    add("VL", record.get("volume"))
    add("IS", record.get("issue"))
    pages = str(record.get("pages") or "")
    if "-" in pages:
        start, _, end = pages.partition("-")
        add("SP", start.strip())
        add("EP", end.strip())
    elif pages:
        add("SP", pages)
    add("SN", record.get("issn") or record.get("isbn"))
    add("DO", record.get("doi"))
    add("UR", record.get("publisher_url"))
    add("AB", record.get("abstract"))
    for kw in _as_list(record.get("keywords")):
        add("KW", kw)
    add("LA", record.get("language"))
    if pub_type == "patent":
        add("M1", "Patent")
    if pub_type == "preprint":
        add("M1", "Preprint")
    lines.append("ER  -")
    return "\n".join(lines)


def parse_ris(text: str) -> list[dict]:
    records: list[dict] = []
    current: dict | None = None
    for raw_line in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        match = re.match(r"^([A-Z][A-Z0-9])\s+-\s?(.*)$", line)
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "TY":
            current = {"publication_type": _PUB_TYPE_FROM_RIS.get(value.upper(), "other")}
        elif tag == "ER":
            if current is not None:
                _finalise_ris(current)
                records.append(current)
            current = None
        elif current is not None:
            _map_ris_tag(current, tag, value)
    if current is not None:  # tolerate a missing final ER
        _finalise_ris(current)
        records.append(current)
    return records


def _map_ris_tag(record: dict, tag: str, value: str) -> None:
    if tag in ("TI", "T1", "TT"):
        record["title"] = value
    elif tag in ("AU", "A1"):
        record.setdefault("authors", []).append(value)
    elif tag == "A2":
        record["corresponding_author"] = value
    elif tag in ("JO", "JF", "JA", "T3"):
        record.setdefault("journal", value)
        if not record.get("journal"):
            record["journal"] = value
    elif tag == "T2":
        record["journal" if record.get("publication_type") != "conference_paper" else "conference"] = value
    elif tag in ("BT", "T2"):
        record["conference"] = value
    elif tag == "CY":
        record.setdefault("conference", record.get("conference") or value)
    elif tag == "PB":
        record["publisher"] = value
    elif tag in ("PY", "Y1"):
        digits = re.search(r"\d{4}", value)
        if digits:
            record["year"] = int(digits.group(0))
    elif tag in ("D1", "DA"):
        match = re.match(r"\d{4}([/-]\d{2})?([/-]\d{2})?", value)
        if match:
            record["date"] = match.group(0).replace("/", "-")
    elif tag == "VL":
        record["volume"] = value
    elif tag == "IS":
        record["issue"] = value
    elif tag == "SP":
        record["_sp"] = value
    elif tag == "EP":
        record["_ep"] = value
    elif tag == "PG":
        record["_pg"] = value
    elif tag == "SN":
        if not record.get("issn"):
            record["issn"] = value
        else:
            record["isbn"] = value
    elif tag == "DO":
        record["doi"] = value
    elif tag == "UR":
        record["publisher_url"] = value
    elif tag == "AB":
        record["abstract"] = value
    elif tag == "KW":
        record.setdefault("keywords", []).append(value)
    elif tag == "LA":
        record["language"] = value
    elif tag in ("N1", "RN"):
        record.setdefault("notes", value)
    elif tag == "M1" and value.lower() in ("patent", "preprint"):
        record["publication_type"] = value.lower()


def _finalise_ris(record: dict) -> None:
    sp, ep, pg = record.pop("_sp", ""), record.pop("_ep", ""), record.pop("_pg", "")
    if sp and ep:
        record["pages"] = f"{sp}-{ep}"
    elif pg:
        record["pages"] = pg
    elif sp:
        record["pages"] = sp
    record.pop("_pg", None)
    # A conference paper's T2 is the conference, not a journal.
    if record.get("publication_type") == "conference_paper" and record.get("conference"):
        record.pop("journal", None)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def to_csv_csv(records: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        row = dict(record)
        for field in _LIST_FIELDS:
            row[field] = "; ".join(_as_list(row.get(field)))
        writer.writerow(row)
    return buffer.getvalue()


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text or ""))
    records: list[dict] = []
    for row in reader:
        record: dict = {}
        for key, value in row.items():
            if key is None or value is None or value == "":
                continue
            name = key.strip()
            value = value.strip()
            if name in _LIST_FIELDS:
                record[name] = [v.strip() for v in value.split(";") if v.strip()]
            elif name in ("year", "citation_count"):
                try:
                    record[name] = int(value)
                except ValueError:
                    continue
            elif name == "impact_factor":
                try:
                    record[name] = float(value)
                except ValueError:
                    continue
            else:
                record[name] = value
        if record:
            records.append(record)
    return records


# ---------------------------------------------------------------------------
# Format dispatch
# ---------------------------------------------------------------------------

def serialize_records(records: list[dict], fmt: str) -> str:
    if fmt == "bibtex":
        return "\n\n".join(to_bibtex(record) for record in records) + "\n"
    if fmt == "ris":
        return "\n\n".join(to_ris(record) for record in records) + "\n"
    if fmt == "csv":
        return to_csv_csv(records)
    raise ValueError(f"Unsupported export format: {fmt!r}")


def parse_records(text: str, fmt: str) -> list[dict]:
    if fmt == "bibtex":
        return parse_bibtex(text)
    if fmt == "ris":
        return parse_ris(text)
    if fmt == "csv":
        return parse_csv(text)
    raise ValueError(f"Unsupported import format: {fmt!r}")


# ---------------------------------------------------------------------------
# Citation generation
# ---------------------------------------------------------------------------

def _person_parts(name: str) -> tuple[str, str]:
    """Return (family, given) for "Family, Given" or "Given Family"."""
    name = " ".join((name or "").split())
    if not name:
        return "", ""
    if "," in name:
        family, _, given = name.partition(",")
        return family.strip(), given.strip()
    tokens = name.split(" ")
    return tokens[-1], " ".join(tokens[:-1])


def _initials(given: str, *, spaced: bool = True) -> str:
    parts = [p for p in re.split(r"[\s\-.]+", given) if p and p[0].isalpha()]
    sep = ". " if spaced else ". "
    return sep.join(p[0].upper() for p in parts) + ("." if parts else "")


def _apa_names(authors: list[str]) -> str:
    names = [f"{fam}, {_initials(giv)}" if (fam := _person_parts(a)[0]) else a
             for a in authors for giv in [_person_parts(a)[1]]]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", … " + names[-1]


def _ieee_names(authors: list[str]) -> str:
    names = []
    for author in authors:
        fam, giv = _person_parts(author)
        names.append(f"{_initials(giv)} {fam}".strip() if fam else author)
    if len(names) > 6:
        return names[0] + " et al."
    if len(names) > 1:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return names[0] if names else ""


def _vancouver_names(authors: list[str]) -> str:
    names = []
    for author in authors:
        fam, giv = _person_parts(author)
        initials = "".join(p[0].upper() for p in re.split(r"[\s\-.]+", giv) if p and p[0].isalpha())
        names.append(f"{fam} {initials}".strip() if fam else author)
    if len(names) > 6:
        names = names[:6] + ["et al."]
    return ", ".join(names)


def _doi_suffix(record: dict, *, apa_style: bool = True) -> str:
    doi = (record.get("doi") or "").strip()
    if not doi or doi == "None":
        doi = ""
    if not doi:
        return ""
    return f"https://doi.org/{doi}" if apa_style else f"doi: {doi}."


def format_citation(record: dict, style: str = "apa") -> str:
    style = (style or "apa").lower()
    if style == "bibtex":
        return to_bibtex(record)

    title = (record.get("title") or "").strip().rstrip(".")
    venue = (record.get("journal") or record.get("conference") or "").strip()
    publisher = (record.get("publisher") or "").strip()
    year = record.get("year") or "n.d."
    volume = (record.get("volume") or "").strip()
    issue = (record.get("issue") or "").strip()
    pages = (record.get("pages") or "").strip()

    authors = _as_list(record.get("authors"))
    if style == "apa":
        outlet = venue or publisher
        vip = volume + (f"({issue})" if issue else "")
        bits = [b for b in (vip, pages) if b]
        tail = f", {', '.join(bits)}" if bits else ""
        pub_line = f"*{outlet}*{tail}." if outlet else f"{tail.lstrip(', ')}." if tail else ""
        doi = _doi_suffix(record)
        return f"{_apa_names(authors)} ({year}). {title}. {pub_line} {doi}".replace("  ", " ").strip()
    if style == "ieee":
        loc = venue or publisher
        details = ", ".join(
            part for part in (
                f"vol. {volume}" if volume else "",
                f"no. {issue}" if issue else "",
                f"pp. {pages}" if pages else "",
                str(year),
            ) if part
        )
        doi = ((" " + _doi_suffix(record, apa_style=False)) if record.get("doi") else ".")
        return (f'{_ieee_names(authors)}, "{title}," *{loc}*, {details}{doi}').replace("  ", " ").strip()
    if style == "vancouver":
        loc = venue or publisher
        vi = f"{volume}({issue})" if volume and issue else volume
        tail = f":{pages}" if pages else ""
        return f"{_vancouver_names(authors)}. {title}. {loc}. {year};{vi}{tail}.".replace(";;", ";").replace("  ", " ").strip()
    if style == "chicago":
        loc = venue or publisher
        vi = f"{volume}, no. {issue} " if volume and issue else (f"{volume} " if volume else "")
        pp = f": {pages}" if pages else ""
        doi = (" " + _doi_suffix(record) + ".") if record.get("doi") else ""
        apa = _apa_names(authors)
        return f'{apa}. "{title}." *{loc}* {vi}({year}){pp}.{doi}'.replace("  ", " ").strip()
    if style == "harvard":
        loc = venue or publisher
        vi = f"{volume}({issue})" if volume and issue else volume
        pp = f", pp. {pages}" if pages else ""
        return f"{_apa_names(authors)} ({year}) '{title}', *{loc}*, {vi}{pp}.".replace("  ", " ").strip()
    raise ValueError(f"Unsupported citation style: {style!r}")
