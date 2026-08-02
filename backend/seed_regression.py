"""Regression-suite seed: 15 courses + 1 publication + 1 document.

The Objects / Publications / Documents E2E harnesses expect a populated
directory (pagination, search, type coverage). Seeded through the real API.
"""
import json
import urllib.request

API = "http://localhost:8000/api/v1"


def post(path, payload):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        return res.status, json.loads(res.read())


created = 0
for i in range(1, 16):
    status, body = post(
        "/objects",
        {
            "object_type": "course",
            "title": f"Regression Seed Course {i:02d}",
            "created_by": "registrar:regression",
            "status": "active",
            "metadata": [
                {"key": "course_code", "value": f"RSC{100 + i}"},
                {"key": "credits", "value": str(3 + (i % 3))},
            ],
        },
    )
    assert status == 201, (status, body)
    created += 1
print(f"courses: {created}")

status, pub = post(
    "/publications",
    {
        "title": "Regression Seed Publication",
        "publication_type": "journal_article",
        "uploaded_by": "registrar:regression",
        "authors": [{"name": "Seed Author"}],
    },
)
assert status == 201, (status, pub)
print(f"publication: {pub['id']}")

import io

boundary = "----regression"
parts = []


def field(name, value):
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    )


field("title", "Regression Seed Document")
field("document_type", "pdf")
field("uploaded_by", "registrar:regression")
parts.append(
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"seed.txt\"\r\n"
    "Content-Type: text/plain\r\n\r\nregression seed file\r\n".encode()
)
parts.append(f"--{boundary}--\r\n".encode())
req = urllib.request.Request(
    f"{API}/documents",
    data=b"".join(parts),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
with urllib.request.urlopen(req) as res:
    doc = json.loads(res.read())
print(f"document: {doc['id']}")
print("seed complete")
