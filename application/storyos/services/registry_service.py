"""GenericRegistryService — 8 registry 共用的基类（CRUD 模板）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityT = TypeVar("EntityT")


class GenericRegistryService(ABC, Generic[EntityT]):
    """registry service 的基类。子类实现 _to_dict / _from_dict 序列化。"""

    def __init__(self, repository: dict[str, EntityT] | None = None) -> None:
        self._repo: dict[str, EntityT] = repository if repository is not None else {}

    def create(self, entity: EntityT) -> EntityT:
        if entity.id in self._repo:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self._repo[entity.id] = entity
        return entity

    def get(self, asset_id: str) -> EntityT:
        if asset_id not in self._repo:
            raise KeyError(f"asset_id {asset_id!r} not found")
        return self._repo[asset_id]

    def update(self, asset_id: str, **kwargs) -> EntityT:
        old = self.get(asset_id)
        new = self._apply_update(old, **kwargs)
        self._repo[asset_id] = new
        return new

    def delete(self, asset_id: str) -> None:
        self._repo.pop(asset_id, None)

    def list(self) -> list[EntityT]:
        return list(self._repo.values())

    @abstractmethod
    def _apply_update(self, entity: EntityT, **kwargs) -> EntityT:
        """子类定义如何处理 kwargs（如 escalate=True → escalate()）。"""
        ...
