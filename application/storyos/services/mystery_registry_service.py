"""Mystery Registry Service（含 Clue 投影到 RevealedClueItem，sub-spec §3.6 锁定）。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.mystery import Clue, Mystery


class MysteryRegistryService(GenericRegistryService[Mystery]):
    def _apply_update(self, entity: Mystery, **kwargs) -> Mystery:
        new = entity
        if "status" in kwargs:
            new = replace(new, status=kwargs["status"])
        return new

    def add_clue(self, mystery_id: str, clue: Clue) -> Mystery:
        m = self.get(mystery_id)
        m2 = m.add_clue(clue)
        self._repo[mystery_id] = m2
        return m2

    def discover_clue(self, mystery_id: str, clue_id: str, chapter: int) -> "tuple[Mystery, RevealedClueItem]":
        """discover Clue → 同时投影到 RevealedClueItem（sub-spec §3.6 修正）。"""
        m = self.get(mystery_id)
        new_clues = tuple(
            c.discover(chapter) if c.id == clue_id else c for c in m.clues
        )
        m2 = replace(m, clues=new_clues)
        self._repo[mystery_id] = m2
        # 投影
        clue = next(c for c in m2.clues if c.id == clue_id)
        projected = self._project_to_revealed(clue)
        return m2, projected

    @staticmethod
    def _project_to_revealed(clue: Clue) -> "RevealedClueItem":
        from application.engine.services.memory_engine import RevealedClueItem
        return RevealedClueItem(
            clue_id=clue.id,
            content=clue.description,
            revealed_at_chapter=clue.discovered_in_chapter or clue.source_chapter,
            category=clue.category.value,
            is_still_valid=clue.status.value != "dead",
        )
