"""Integration tests for the Publications API (reference-manager slice).

Skipped automatically when FastAPI / SQLAlchemy / pydantic-settings are not
installed. Uses an in-memory SQLite database plus a temporary local storage
root so the slice is verifiable end-to-end in CI without PostgreSQL, disk
state, or network — mirrors ``test_documents_api.py``. The external metadata
provider (Crossref) is replaced with a fake via dependency override, so no
HTTP leaves the test process.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("pydantic_settings")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.publications import get_metadata_lookup, get_storage
from app.infrastructure.db.models.object_model import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.local import LocalFileStorage
from app.main import app


class FakeMetadataLookup:
    """Deterministic stand-in for the Crossref adapter (no network in tests)."""

    def lookup(self, doi: str):
        if doi == "10.1038/found":
            return {
                "title": "A Found Paper",
                "publication_type": "journal_article",
                "authors": ["Curie, Marie", "Einstein, Albert"],
                "journal": "Nature",
                "doi": doi,
                "year": 2020,
                "date": "2020-04-01",
            }
        return None


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    storage = LocalFileStorage(str(tmp_path / "storage"))

    def _override_db():
        yield session

    def _override_storage():
        return storage

    def _override_lookup():
        return FakeMetadataLookup()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_storage] = _override_storage
    app.dependency_overrides[get_metadata_lookup] = _override_lookup
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)


def _create_object(client, **kwargs):
    defaults = {
        "object_type": "research_project",
        "title": "Project X",
        "created_by": "faculty:1",
    }
    defaults.update(kwargs)
    return client.post("/api/v1/objects", json=defaults)


def _create(client, **kwargs):
    payload = {
        "title": "Deep Learning for Catalysis",
        "publication_type": "journal_article",
        "uploaded_by": "faculty:1",
        "authors": [
            {"name": "Gupta, Vipin", "orcid": "0000-0002-1825-0097",
             "corresponding": True},
            {"name": "Sharma, Asha"},
        ],
        "journal": "Nature Catalysis",
        "doi": "10.1038/s41929-024-00001",
        "year": 2025,
        "volume": "7",
        "issue": "3",
        "pages": "201-214",
        "publisher": "Springer Nature",
        "keywords": ["catalysis", "deep learning"],
        "quartile": "Q1",
        "citation_count": 12,
        "impact_factor": 37.8,
        "indexing": ["SCOPUS", "WOS"],
        "publisher_url": "https://doi.org/10.1038/s41929-024-00001",
        "tags": ["ml"],
        "collections": ["Catalysis Papers"],
        "pipeline_stage": "published",
    }
    payload.update(kwargs)
    return client.post("/api/v1/publications", json=payload)


def test_create_then_get_publication(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("obj:publication:")
    assert body["title"] == "Deep Learning for Catalysis"
    assert body["publication_type"] == "journal_article"
    assert body["pipeline_stage"] == "published"
    assert body["authors"][0]["name"] == "Gupta, Vipin"
    assert body["authors"][0]["corresponding"] is True
    assert body["authors"][0]["orcid"] == "0000-0002-1825-0097"
    assert body["doi"] == "10.1038/s41929-024-00001"
    assert body["journal"] == "Nature Catalysis"
    assert body["year"] == 2025
    assert body["volume"] == "7" and body["issue"] == "3" and body["pages"] == "201-214"
    assert body["keywords"] == ["catalysis", "deep learning"]
    assert body["quartile"] == "Q1"
    assert body["citation_count"] == 12
    assert body["impact_factor"] == 37.8
    assert body["indexing"] == ["SCOPUS", "WOS"]
    assert body["tags"] == ["ml"]
    assert body["collections"] == ["Catalysis Papers"]
    assert body["status"] == "draft"
    assert body["pdf_url"] is None  # nothing attached yet
    for group in ("projects", "grants", "students", "faculty",
                  "departments", "events", "committees"):
        assert body["links"][group] == []

    got = client.get(f"/api/v1/publications/{body['id']}")
    assert got.status_code == 200
    assert got.json()["doi"] == "10.1038/s41929-024-00001"

    # Object-centric model: a Publication IS an Object (frozen behaviour).
    objects = client.get("/api/v1/objects", params={"page_size": 100}).json()
    pub_rows = [item for item in objects["items"] if item["id"] == body["id"]]
    assert len(pub_rows) == 1
    assert pub_rows[0]["object_type"] == "publication"


def test_create_with_object_links(client):
    project = _create_object(client).json()
    grant = _create_object(client, object_type="grant", title="Grant G1").json()
    student = _create_object(client, object_type="student", title="Student Y").json()
    event = _create_object(client, object_type="event", title="ICML 24").json()

    resp = _create(
        client,
        links={
            "projects": [project["id"]],
            "grants": [grant["id"]],
            "students": [student["id"]],
            "events": [event["id"]],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["links"]["projects"][0]["id"] == project["id"]
    assert body["links"]["projects"][0]["title"] == "Project X"
    assert body["links"]["projects"][0]["kind"] == "reports"
    assert body["links"]["grants"][0]["title"] == "Grant G1"
    assert body["links"]["students"][0]["kind"] == "authored_by"
    assert body["links"]["events"][0]["kind"] == "presented_at"

    # The object lens: GET /publications?object_id=... ("papers funded by Grant X").
    lens = client.get(
        "/api/v1/publications",
        params={"object_id": grant["id"], "page_size": 100},
    )
    assert lens.status_code == 200
    ids = [item["id"] for item in lens.json()["items"]]
    assert ids == [body["id"]]


def test_create_validation_errors(client):
    # invalid publication_type -> 422
    assert _create(client, publication_type="bogus").status_code == 422
    # invalid quartile -> 422
    assert _create(client, quartile="Q7").status_code == 422
    # invalid DOI -> 422
    assert _create(client, doi="not-a-doi").status_code == 422
    # invalid ORCID -> 422
    assert _create(client, authors=[{"name": "X", "orcid": "123"}]).status_code == 422
    # empty author name -> 422
    assert _create(client, authors=[{"name": " "}]).status_code == 422
    # unknown links group -> 422
    assert _create(client, links={"bogus_group": []}).status_code == 422
    # link to a non-existent object -> 422
    assert _create(
        client, links={"projects": ["obj:research_project:NOPE"]}
    ).status_code == 422
    # missing title -> 422 (FastAPI request validation)
    resp = client.post(
        "/api/v1/publications",
        json={"publication_type": "journal_article", "uploaded_by": "faculty:1"},
    )
    assert resp.status_code == 422


def test_create_rejects_duplicates(client):
    assert _create(client).status_code == 201
    # same DOI, different title -> 409
    assert _create(client, title="Another Paper Entirely").status_code == 409
    # same title, no DOI -> 409
    assert _create(client, doi=None).status_code == 409
    # different DOI AND different title -> created
    assert _create(
        client, title="A Different Study", doi="10.1000/other-001"
    ).status_code == 201


def test_list_filters_and_pagination(client):
    first = _create(client).json()
    _create(
        client,
        title="Graph Neural Sensors",
        doi=None,
        publication_type="conference_paper",
        journal=None,
        conference="ICML",
        year=2024,
        quartile="Q2",
        citations=None,
        pipeline_stage="under_review",
        authors=[{"name": "Verma, Rohan"}],
        keywords=["sensors", "graph networks"],
        tags=["edge"],
        collections=[],
    )

    all_resp = client.get("/api/v1/publications", params={"page_size": 100})
    assert all_resp.status_code == 200
    assert all_resp.json()["total_count"] == 2

    by_q = client.get("/api/v1/publications", params={"q": "catalysis gupta"})
    assert by_q.json()["total_count"] == 1
    assert by_q.json()["items"][0]["id"] == first["id"]

    by_doi = client.get("/api/v1/publications", params={"q": "10.1038"})
    assert by_doi.json()["total_count"] == 1

    assert client.get(
        "/api/v1/publications", params={"publication_type": "conference_paper"}
    ).json()["total_count"] == 1
    assert client.get(
        "/api/v1/publications", params={"year": 2025}
    ).json()["total_count"] == 1
    assert client.get(
        "/api/v1/publications", params={"quartile": "Q2"}
    ).json()["total_count"] == 1
    assert client.get(
        "/api/v1/publications", params={"pipeline_stage": "under_review"}
    ).json()["total_count"] == 1
    assert client.get(
        "/api/v1/publications", params={"publication_type": "bogus"}
    ).status_code == 422
    assert client.get(
        "/api/v1/publications", params={"year": 199}
    ).status_code == 422

    # pagination
    page1 = client.get("/api/v1/publications", params={"page": 1, "page_size": 1})
    assert page1.json()["total_count"] == 2
    assert len(page1.json()["items"]) == 1
    page3 = client.get("/api/v1/publications", params={"page": 3, "page_size": 1})
    assert page3.json()["items"] == []
    assert client.get(
        "/api/v1/publications", params={"page": 0}
    ).status_code == 422


def test_update_put_patch_and_link_merge(client):
    project = _create_object(client).json()
    grant = _create_object(client, object_type="grant", title="Grant G1").json()
    body = _create(client, links={"projects": [project["id"]]}).json()

    # PATCH: scalars + one link group. Unmentioned groups are untouched.
    resp = client.patch(
        f"/api/v1/publications/{body['id']}",
        json={
            "title": "Deep Learning for Catalysis v2",
            "pipeline_stage": "accepted",
            "links": {"grants": [grant["id"]]},
        },
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["title"] == "Deep Learning for Catalysis v2"
    assert updated["pipeline_stage"] == "accepted"
    assert updated["links"]["projects"][0]["id"] == project["id"]  # untouched
    assert updated["links"]["grants"][0]["id"] == grant["id"]      # merged in
    assert updated["version"] > body["version"]

    # PUT replaces the group when the key is present with an empty list.
    resp = client.put(
        f"/api/v1/publications/{body['id']}", json={"links": {"projects": []}}
    )
    assert resp.status_code == 200
    assert resp.json()["links"]["projects"] == []
    assert resp.json()["links"]["grants"][0]["id"] == grant["id"]  # still there

    # Linking to a non-existent object -> 422.
    bad = client.put(
        f"/api/v1/publications/{body['id']}",
        json={"links": {"grants": ["obj:grant:NOPE"]}},
    )
    assert bad.status_code == 422

    # Status transition rules still come from the (frozen) domain lifecycle.
    client.put(f"/api/v1/publications/{body['id']}", json={"status": "active"})
    assert client.get(f"/api/v1/publications/{body['id']}").json()["status"] == "active"


def test_update_missing_and_non_publication(client):
    resp = client.put("/api/v1/publications/obj:publication:NOPE", json={"title": "X"})
    assert resp.status_code == 404
    project = _create_object(client).json()
    # an existing non-publication Object is not a Publication
    assert client.get(f"/api/v1/publications/{project['id']}").status_code == 404
    assert client.patch(
        f"/api/v1/publications/{project['id']}", json={"title": "X"}
    ).status_code == 404


def test_pdf_attach_download_replace_and_delete(client):
    body = _create(client).json()

    # attach
    resp = client.put(
        f"/api/v1/publications/{body['id']}/pdf",
        files={"file": ("paper.pdf", b"%PDF-one", "application/pdf")},
    )
    assert resp.status_code == 200
    attached = resp.json()
    assert attached["pdf_file_name"] == "paper.pdf"
    assert attached["pdf_file_size"] == len(b"%PDF-one")
    assert attached["pdf_url"] is not None

    # download round trip (byte-for-byte)
    dl = client.get(f"/api/v1/publications/{body['id']}/pdf")
    assert dl.status_code == 200
    assert dl.content == b"%PDF-one"
    assert dl.headers["content-type"].startswith("application/pdf")
    assert "paper.pdf" in dl.headers["content-disposition"]

    # replace (second attach overwrites)
    resp = client.put(
        f"/api/v1/publications/{body['id']}/pdf",
        files={"file": ("paper-v2.pdf", b"%PDF-two-longer", "application/pdf")},
    )
    assert resp.status_code == 200
    assert resp.json()["pdf_file_name"] == "paper-v2.pdf"
    dl = client.get(f"/api/v1/publications/{body['id']}/pdf")
    assert dl.content == b"%PDF-two-longer"

    # delete removes the object; its PDF endpoint then 404s
    assert client.delete(f"/api/v1/publications/{body['id']}").status_code == 204
    assert client.get(f"/api/v1/publications/{body['id']}").status_code == 404
    assert client.get(f"/api/v1/publications/{body['id']}/pdf").status_code == 404
    assert client.delete(f"/api/v1/publications/{body['id']}").status_code == 404


def test_pdf_endpoints_404_without_attachment(client):
    body = _create(client).json()
    assert client.get(f"/api/v1/publications/{body['id']}/pdf").status_code == 404
    assert client.put(
        "/api/v1/publications/obj:publication:NOPE/pdf",
        files={"file": ("x.pdf", b"x", "application/pdf")},
    ).status_code == 404


def test_export_bibtex_ris_csv(client):
    _create(client)
    _create(client, title="Second Study", doi="10.1000/other-002", year=2024)

    bib = client.get("/api/v1/publications/export", params={"fmt": "bibtex"})
    assert bib.status_code == 200
    assert bib.headers["content-type"].startswith("application/x-bibtex")
    assert "@article{" in bib.text
    assert "Deep Learning for Catalysis" in bib.text
    assert "Second Study" in bib.text
    assert "attachment" in bib.headers["content-disposition"]

    ris = client.get("/api/v1/publications/export", params={"fmt": "ris"})
    assert ris.status_code == 200
    assert "TY  - JOUR" in ris.text
    assert "TI  - Deep Learning for Catalysis" in ris.text
    assert "ER  -" in ris.text

    csv_resp = client.get("/api/v1/publications/export", params={"fmt": "csv"})
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    lines = [ln for ln in csv_resp.text.strip().splitlines() if ln]
    assert len(lines) == 3  # header + 2 rows
    assert "title" in lines[0]

    # filtered export: only the 2024 paper
    bib24 = client.get(
        "/api/v1/publications/export", params={"fmt": "bibtex", "year": 2024}
    )
    assert "Second Study" in bib24.text
    assert "Deep Learning for Catalysis" not in bib24.text

    assert client.get(
        "/api/v1/publications/export", params={"fmt": "docx"}
    ).status_code == 422


def test_citation_styles(client):
    body = _create(client).json()

    apa = client.get(f"/api/v1/publications/{body['id']}/citation")
    assert apa.status_code == 200
    assert apa.json()["style"] == "apa"
    assert "Gupta" in apa.json()["citation"]
    assert "2025" in apa.json()["citation"]
    assert "Nature Catalysis" in apa.json()["citation"]

    ieee = client.get(
        f"/api/v1/publications/{body['id']}/citation", params={"style": "ieee"}
    )
    assert ieee.status_code == 200
    assert "Deep Learning for Catalysis" in ieee.json()["citation"]

    bibtex = client.get(
        f"/api/v1/publications/{body['id']}/citation", params={"style": "bibtex"}
    )
    assert "@article{" in bibtex.json()["citation"]

    assert client.get(
        f"/api/v1/publications/{body['id']}/citation", params={"style": "mla"}
    ).status_code == 422
    assert client.get(
        "/api/v1/publications/obj:publication:NOPE/citation"
    ).status_code == 404


def test_import_bibtex_with_duplicate_report(client):
    existing = _create(client).json()
    text = (
        "@article{newone,\n"
        "  title = {Imported From BibTeX},\n"
        "  author = {Rao, Anil},\n"
        "  journal = {PLOS ONE},\n"
        "  year = {2023},\n"
        "  doi = {10.1371/import-001},\n"
        "}\n"
        "@article{ dupe,\n"
        "  title = {Different Title But Same DOI},\n"
        "  author = {Someone, Else},\n"
        "  year = {2024},\n"
        "  doi = {10.1038/s41929-024-00001},\n"
        "}\n"
    )
    resp = client.post(
        "/api/v1/publications/import",
        json={"fmt": "bibtex", "text": text, "uploaded_by": "faculty:1"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["created"]) == 1
    assert len(result["duplicates"]) == 1
    assert result["duplicates"][0]["existing_id"] == existing["id"]
    assert result["errors"] == []

    imported = client.get(f"/api/v1/publications/{result['created'][0]}")
    assert imported.json()["title"] == "Imported From BibTeX"
    assert imported.json()["authors"][0]["name"] == "Rao, Anil"
    assert imported.json()["journal"] == "PLOS ONE"

    # invalid format / empty text -> 422
    assert client.post(
        "/api/v1/publications/import",
        json={"fmt": "docx", "text": "x", "uploaded_by": "faculty:1"},
    ).status_code == 422
    assert client.post(
        "/api/v1/publications/import",
        json={"fmt": "bibtex", "text": "   ", "uploaded_by": "faculty:1"},
    ).status_code == 422


def test_import_ris(client):
    text = (
        "TY  - JOUR\n"
        "TI  - RIS Imported Paper\n"
        "AU  - Rao, Anil\n"
        "JO  - Sensors\n"
        "PY  - 2022\n"
        "DO  - 10.3390/ris-001\n"
        "ER  -\n"
    )
    resp = client.post(
        "/api/v1/publications/import",
        json={"fmt": "ris", "text": text, "uploaded_by": "faculty:1"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert len(result["created"]) == 1
    imported = client.get(f"/api/v1/publications/{result['created'][0]}").json()
    assert imported["title"] == "RIS Imported Paper"
    assert imported["year"] == 2022
    assert imported["doi"] == "10.3390/ris-001"


def test_doi_lookup_with_fake_provider(client):
    ok = client.get("/api/v1/publications/doi-lookup/10.1038/found")
    assert ok.status_code == 200
    record = ok.json()
    assert record["title"] == "A Found Paper"
    assert record["authors"] == ["Curie, Marie", "Einstein, Albert"]
    assert record["year"] == 2020

    missing = client.get("/api/v1/publications/doi-lookup/10.0000/unknown")
    assert missing.status_code == 404


def test_static_routes_not_captured_as_ids(client):
    # /export declared before /{publication_id}: wrong fmt -> 422, not 404-as-id
    resp = client.get("/api/v1/publications/export", params={"fmt": "nope"})
    assert resp.status_code == 422
    assert "fmt" in resp.json()["detail"]
