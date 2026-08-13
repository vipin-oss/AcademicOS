"""L2 bounded-resource limits (security / performance, SCALE_LAW).

Central, explicit caps for extraction so oversized or malicious inputs cannot
exhaust memory/CPU. These are enforced before allocation by the engines and the
container expander.
"""

from __future__ import annotations

#: Maximum number of structural elements one document may produce.
MAX_ELEMENTS = 50_000

#: Maximum number of pages in one PDF/document.
MAX_PAGES = 5_000

#: Maximum number of slides in one PPTX.
MAX_SLIDES = 2_000

#: Maximum number of worksheets in one XLSX.
MAX_SHEETS = 500

#: Maximum number of cells in one spreadsheet (all sheets).
MAX_CELLS = 1_000_000

#: Maximum number of images extracted from one document.
MAX_IMAGES = 2_000

#: Maximum image decode dimension (guard against huge-image decompression).
MAX_IMAGE_DIMENSION = 40_000

#: Maximum total uncompressed bytes across a container.
MAX_PACKAGE_TOTAL_BYTES = 512 * 1024 * 1024

#: Maximum number of members in one container.
MAX_MEMBERS = 10_000

#: Maximum bytes of a single member.
MAX_MEMBER_BYTES = 512 * 1024 * 1024

#: Maximum compression ratio (uncompressed/compressed) before "zip bomb".
MAX_COMPRESSION_RATIO = 1_000

#: Maximum nesting depth for nested containers.
MAX_CONTAINER_DEPTH = 8

#: Maximum characters of normalized text retained for search/display.
MAX_TEXT_CHARS = 8_000_000
