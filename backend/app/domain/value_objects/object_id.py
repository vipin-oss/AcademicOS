"""Immutable, type-prefixed Object identifier.

Frozen reference: Object-Centric Knowledge Graph Blueprint §1.2
("Unique ID ... type-prefixed, immutable, resolvable handle").

An ObjectId looks like ``obj:publication:9QX4K7...``. It is a value object:
equality is by value, it is hashable, and it carries no behaviour beyond
construction and parsing. No database, no UUID library dependency — only stdlib.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.value_objects.enums import ObjectType


@dataclass(frozen=True)
class ObjectId:
    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ObjectId({self.value!r})"

    @classmethod
    def generate(cls, object_type: ObjectType) -> "ObjectId":
        suffix = uuid.uuid4().hex[:16].upper()
        return cls(f"obj:{object_type.value}:{suffix}")

    @classmethod
    def parse(cls, raw: str) -> "ObjectId":
        parts = raw.split(":")
        if len(parts) != 3 or parts[0] != "obj":
            raise ValueError(f"Invalid ObjectId: {raw!r}")
        return cls(raw)

    @property
    def type_code(self) -> str:
        return self.value.split(":", 2)[1]

    @property
    def type(self) -> ObjectType:
        return ObjectType(self.type_code)
