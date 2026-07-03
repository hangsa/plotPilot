"""Mystery mapper — entity ↔ ORM row.

Clues are persisted as a JSON list of dicts; each Clue's enums (category, status)
are stored as their `.value` strings and reconstructed on read.
"""
from __future__ import annotations

from typing import Any

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.mystery import Clue, ClueCategory, Mystery
from infrastructure.persistence.storyos.schemas.mystery_schema import MysterySchema


def serialize_clue(clue: Clue) -> dict:
    """Serialize a Clue to a JSON-safe dict."""
    return {
        "id": clue.id,
        "mystery_id": clue.mystery_id,
        "description": clue.description,
        "source_chapter": clue.source_chapter,
        "source_location": clue.source_location,
        "category": clue.category.value,
        "status": clue.status.value,
        "discovered_in_chapter": clue.discovered_in_chapter,
        "invalidated_in_chapter": clue.invalidated_in_chapter,
    }


def deserialize_clue(data: dict) -> Clue:
    """Reconstruct a Clue from a JSON-stored dict."""
    return Clue(
        id=data["id"],
        mystery_id=data["mystery_id"],
        description=data["description"],
        source_chapter=data["source_chapter"],
        source_location=data["source_location"],
        category=ClueCategory(data["category"]),
        status=AssetStatus(data["status"]),
        discovered_in_chapter=data.get("discovered_in_chapter"),
        invalidated_in_chapter=data.get("invalidated_in_chapter"),
    )


class MysteryMapper:
    @staticmethod
    def to_orm(m: Mystery) -> MysterySchema:
        return MysterySchema(
            id=m.id,
            project_id=m.novel_id,
            created_chapter=m.created_chapter,
            status=m.status.value,
            description=m.description,
            linked_assets={},
            clues=[serialize_clue(c) for c in m.clues],
            related_mystery=m.related_mystery,
        )

    @staticmethod
    def to_domain(row: MysterySchema) -> Mystery:
        raw_clues = row.clues or []
        clues = tuple(deserialize_clue(c) for c in raw_clues)
        return Mystery(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            status=AssetStatus(row.status),
            created_chapter=row.created_chapter,
            clues=clues,
            related_mystery=row.related_mystery,
        )