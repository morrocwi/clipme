from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .graph import UnitGraph, Unit
from .registry import SkillRegistry, SkillManifest


ACTIVATION_RANK = {"skip": 0, "optional": 1, "inline": 2, "required": 3}


@dataclass(frozen=True)
class Task:
    id: str
    skill_id: str
    unit_id: str
    unit_kind: str
    mode: str
    requires: tuple[str, ...]
    produces: tuple[str, ...]
    gates: tuple[str, ...]
    assurance: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("requires", "produces", "gates"):
            data[key] = list(data[key])
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            skill_id=data["skill_id"],
            unit_id=data["unit_id"],
            unit_kind=data["unit_kind"],
            mode=data["mode"],
            requires=tuple(data.get("requires", [])),
            produces=tuple(data.get("produces", [])),
            gates=tuple(data.get("gates", [])),
            assurance=bool(data.get("assurance", False)),
        )


class FeatureDetector:
    @staticmethod
    def detect(project: dict[str, Any]) -> set[str]:
        features = {k for k, v in (project.get("features") or {}).items() if bool(v)}
        if project.get("source_refs"):
            features.add("factual")
        profile = project.get("profile")
        if profile in {"longform", "film"}:
            features.add("long_duration")
        if profile == "film":
            features.add("film_form")
        language = project.get("language")
        if language:
            features.add("language_content")
        return features


class Planner:
    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def activation_plan(self, project: dict[str, Any]) -> dict[str, str]:
        profile = project["profile"]
        features = FeatureDetector.detect(project)
        statuses = {
            skill.id: skill.activation_for(profile, features)
            for skill in self.registry.active()
        }
        overrides = project.get("skill_overrides") or {}
        forced_skip = set()
        for skill_id, status in overrides.items():
            if skill_id not in statuses:
                raise ValueError(f"skill override references unknown skill {skill_id}")
            if status not in ACTIVATION_RANK:
                raise ValueError(f"invalid skill override {skill_id}={status}")
            statuses[skill_id] = status
            if status == "skip":
                forced_skip.add(skill_id)
        changed = True
        while changed:
            changed = False
            for skill_id, status in list(statuses.items()):
                if status == "skip":
                    continue
                skill = self.registry.get(skill_id)
                for dep in skill.requires:
                    if dep not in statuses:
                        continue
                    if statuses[dep] == "skip":
                        if dep in forced_skip:
                            raise ValueError(f"skill {skill_id} requires {dep}, but {dep} is forced to skip")
                        statuses[dep] = "inline"
                        changed = True
        return statuses

    def _units_for_scope(self, graph: UnitGraph, scope: str) -> list[Unit]:
        if scope == "master":
            return [Unit(id="MASTER", kind="master", parent=None)]
        units = graph.by_kind(scope)
        if units:
            return units
        if scope == "project":
            return [u for u in graph.roots() if u.kind == "project"]
        return []

    def build_tasks(self, project: dict[str, Any], graph: UnitGraph) -> list[Task]:
        profile = project["profile"]
        activation = self.activation_plan(project)
        provisional: list[tuple[SkillManifest, Unit, str]] = []
        for skill in self.registry.active():
            mode = activation[skill.id]
            if mode not in {"required", "inline"}:
                continue
            for scope in skill.scopes_for(profile):
                for unit in self._units_for_scope(graph, scope):
                    provisional.append((skill, unit, mode))

        task_keys = {(s.id, u.id): f"{s.id}@{u.id}" for s, u, _ in provisional}
        by_skill: dict[str, list[tuple[Unit, str]]] = {}
        for skill, unit, _ in provisional:
            by_skill.setdefault(skill.id, []).append((unit, task_keys[(skill.id, unit.id)]))

        def dep_task_id(dep_skill: str, unit: Unit) -> str | None:
            candidates = by_skill.get(dep_skill, [])
            if not candidates:
                return None
            if unit.kind == "master":
                project_candidates = [tid for u, tid in candidates if u.kind == "project"]
                return project_candidates[0] if project_candidates else None
            ancestry = [unit.id]
            if unit.id in graph.units:
                ancestry += [a.id for a in graph.ancestors(unit.id)]
            for ancestor_id in ancestry:
                for dep_unit, tid in candidates:
                    if dep_unit.id == ancestor_id:
                        return tid
            return None

        tasks: list[Task] = []
        for skill, unit, mode in provisional:
            deps: list[str] = []
            dependency_skills = list(skill.requires) + [d for d in skill.after_if_active if d in by_skill]
            for dep in dependency_skills:
                direct = dep_task_id(dep, unit)
                if direct:
                    deps.append(direct)
                    continue
                candidates = by_skill.get(dep, [])
                if unit.kind == "master":
                    deps.extend(tid for _, tid in candidates)
                elif unit.id in graph.units:
                    descendant_ids = {d.id for d in graph.descendants(unit.id)}
                    deps.extend(tid for dep_unit, tid in candidates if dep_unit.id in descendant_ids)
            tasks.append(Task(
                id=task_keys[(skill.id, unit.id)],
                skill_id=skill.id,
                unit_id=unit.id,
                unit_kind=unit.kind,
                mode=mode,
                requires=tuple(sorted(set(deps))),
                produces=skill.produces,
                gates=skill.gates,
                assurance=skill.assurance,
            ))
        return tasks

    def plan(self, project: dict[str, Any], graph: UnitGraph) -> dict[str, Any]:
        features = sorted(FeatureDetector.detect(project))
        activation = self.activation_plan(project)
        tasks = self.build_tasks(project, graph)
        return {
            "project_id": project["id"],
            "profile": project["profile"],
            "features": features,
            "activation": activation,
            "tasks": [t.to_dict() for t in tasks],
        }
