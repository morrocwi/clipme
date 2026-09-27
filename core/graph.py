from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


CANONICAL_ORDER = {
    "project": 0,
    "act": 1,
    "chapter": 1,
    "sequence": 2,
    "scene": 3,
    "beat": 4,
    "shot": 5,
    "frame": 6,
    "audio_event": 6,
}


@dataclass(frozen=True)
class Unit:
    id: str
    kind: str
    parent: str | None = None
    children: tuple[str, ...] = ()
    refs: dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Unit":
        return cls(
            id=data["id"],
            kind=data["kind"],
            parent=data.get("parent"),
            children=tuple(data.get("children", [])),
            refs=dict(data.get("refs", {})),
        )


class UnitGraph:
    def __init__(self, units: Iterable[Unit]):
        materialized = list(units)
        self.units = {u.id: u for u in materialized}
        if len(self.units) != len(materialized):
            raise ValueError("duplicate unit id")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnitGraph":
        raw = data.get("units", [])
        ids = [u.get("id") for u in raw]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate unit id")
        return cls(Unit.from_dict(u) for u in raw)

    def get(self, unit_id: str) -> Unit:
        return self.units[unit_id]

    def roots(self) -> list[Unit]:
        return [u for u in self.units.values() if u.parent is None]

    def by_kind(self, kind: str) -> list[Unit]:
        return [u for u in self.units.values() if u.kind == kind]

    def ancestors(self, unit_id: str, include_self: bool = False) -> list[Unit]:
        out: list[Unit] = []
        current = self.units[unit_id]
        if include_self:
            out.append(current)
        seen = {unit_id}
        while current.parent:
            if current.parent in seen:
                raise ValueError(f"cycle detected at {current.parent}")
            seen.add(current.parent)
            current = self.units[current.parent]
            out.append(current)
        return out

    def descendants(self, unit_id: str) -> list[Unit]:
        out: list[Unit] = []
        stack = list(self.units[unit_id].children)
        seen: set[str] = set()
        while stack:
            uid = stack.pop()
            if uid in seen:
                continue
            seen.add(uid)
            unit = self.units[uid]
            out.append(unit)
            stack.extend(unit.children)
        return out

    def nearest_ancestor_of_kind(self, unit_id: str, kind: str) -> Unit | None:
        for unit in self.ancestors(unit_id, include_self=True):
            if unit.kind == kind:
                return unit
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "units": [
                {
                    "id": u.id,
                    "kind": u.kind,
                    "parent": u.parent,
                    "children": list(u.children),
                    "refs": u.refs,
                }
                for u in self.units.values()
            ]
        }
