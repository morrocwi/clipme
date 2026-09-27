from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .graph import UnitGraph, CANONICAL_ORDER
from .planner import Task
from .registry import SkillRegistry


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"


class GraphValidator:
    def validate(self, graph: UnitGraph, profile: dict[str, Any] | None = None) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        roots = graph.roots()
        project_roots = [u for u in roots if u.kind == "project"]
        if len(project_roots) != 1:
            issues.append(ValidationIssue("ROOT_COUNT", f"expected exactly one project root, found {len(project_roots)}"))

        for unit in graph.units.values():
            if unit.kind not in CANONICAL_ORDER:
                issues.append(ValidationIssue("UNKNOWN_KIND", f"{unit.id}: unknown kind {unit.kind}"))
                continue
            if unit.parent:
                if unit.parent not in graph.units:
                    issues.append(ValidationIssue("MISSING_PARENT", f"{unit.id}: missing parent {unit.parent}"))
                else:
                    parent = graph.units[unit.parent]
                    if unit.id not in parent.children:
                        issues.append(ValidationIssue("PARENT_CHILD_MISMATCH", f"{unit.id}: parent {unit.parent} does not list child"))
                    if parent.kind in CANONICAL_ORDER and CANONICAL_ORDER[unit.kind] <= CANONICAL_ORDER[parent.kind]:
                        issues.append(ValidationIssue("INVALID_HIERARCHY", f"{unit.id}: {unit.kind} cannot be child of {parent.kind}"))
            for child_id in unit.children:
                if child_id not in graph.units:
                    issues.append(ValidationIssue("MISSING_CHILD", f"{unit.id}: missing child {child_id}"))
                elif graph.units[child_id].parent != unit.id:
                    issues.append(ValidationIssue("CHILD_PARENT_MISMATCH", f"{unit.id}: child {child_id} points to {graph.units[child_id].parent}"))

        for unit_id in graph.units:
            try:
                graph.ancestors(unit_id)
            except (ValueError, KeyError) as exc:
                issues.append(ValidationIssue("CYCLE_OR_BROKEN_CHAIN", f"{unit_id}: {exc}"))

        if profile:
            allowed = set(profile.get("planning", {}).get("allowed_hierarchy", []))
            if allowed:
                for unit in graph.units.values():
                    if unit.kind not in allowed:
                        issues.append(ValidationIssue("PROFILE_KIND", f"{unit.id}: kind {unit.kind} not allowed by profile"))
            primary = profile.get("planning", {}).get("primary_unit")
            if primary and allowed and primary not in allowed:
                issues.append(ValidationIssue("PROFILE_PRIMARY", f"primary_unit {primary} is not in allowed_hierarchy"))
        return issues


class TaskGraphValidator:
    def validate(self, tasks: list[Task], registry: SkillRegistry) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        ids = [t.id for t in tasks]
        if len(ids) != len(set(ids)):
            issues.append(ValidationIssue("DUP_TASK", "duplicate task ids"))
        idset = set(ids)
        for task in tasks:
            if task.skill_id not in registry.manifests:
                issues.append(ValidationIssue("UNKNOWN_SKILL", f"{task.id}: unknown skill {task.skill_id}"))
            for dep in task.requires:
                if dep not in idset:
                    issues.append(ValidationIssue("MISSING_TASK_DEP", f"{task.id}: missing dependency task {dep}"))
                if dep == task.id:
                    issues.append(ValidationIssue("SELF_DEP", f"{task.id}: task depends on itself"))

        adjacency = {t.id: list(t.requires) for t in tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                issues.append(ValidationIssue("TASK_CYCLE", f"task cycle includes {node}"))
                return
            visiting.add(node)
            for dep in adjacency.get(node, []):
                visit(dep)
            visiting.remove(node)
            visited.add(node)

        for node in adjacency:
            visit(node)
        return issues


class ReferenceValidator:
    """Validate cross-artifact IDs that JSON Schema alone cannot prove."""

    def validate_documents(
        self,
        graph: UnitGraph,
        sequences: list[dict[str, Any]],
        scenes: list[dict[str, Any]],
        shots: list[dict[str, Any]],
        timeline: dict[str, Any] | None = None,
        facts: set[str] | None = None,
        assets: set[str] | None = None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        unit_ids = set(graph.units)
        fact_index_available = facts is not None
        asset_index_available = assets is not None
        facts = facts or set()
        assets = assets or set()

        def require(ref: str, kind: str, owner: str) -> None:
            if ref not in unit_ids:
                issues.append(ValidationIssue("BROKEN_REF", f"{owner}: {kind} ref {ref} does not exist in unit graph"))

        for seq in sequences:
            require(seq["id"], "sequence", seq["id"])
            for ref in seq.get("scenes", []):
                require(ref, "scene", seq["id"])
        for scene in scenes:
            require(scene["id"], "scene", scene["id"])
            require(scene["sequence_id"], "sequence", scene["id"])
            for ref in scene.get("beats", []):
                require(ref, "beat", scene["id"])
            for ref in scene.get("shot_refs", []):
                require(ref, "shot", scene["id"])
        for shot in shots:
            require(shot["id"], "shot", shot["id"])
            require(shot["scene_id"], "scene", shot["id"])
            for ref in shot.get("fact_refs", []):
                if fact_index_available and ref not in facts:
                    issues.append(ValidationIssue("BROKEN_FACT_REF", f"{shot['id']}: fact {ref} not found"))
            for ref in shot.get("asset_refs", []):
                if asset_index_available and ref not in assets:
                    issues.append(ValidationIssue("BROKEN_ASSET_REF", f"{shot['id']}: asset {ref} not found"))
        if timeline:
            for event in timeline.get("events", []):
                ref = event.get("ref")
                if ref and ref not in unit_ids and ref not in assets:
                    issues.append(ValidationIssue("BROKEN_TIMELINE_REF", f"timeline event {event.get('id')}: ref {ref} not found"))
        return issues


class ProfileValidator:
    def validate(self, project: dict[str, Any], profile: dict[str, Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if profile.get("id") and project.get("profile") != profile.get("id"):
            issues.append(ValidationIssue("PROFILE_ID", f"project profile {project.get('profile')} does not match profile file {profile.get('id')}"))
        target = (project.get("duration") or {}).get("target_seconds")
        bounds = profile.get("duration") or {}
        if target is not None:
            lo = bounds.get("min_seconds")
            hi = bounds.get("max_seconds")
            if lo is not None and target < lo:
                issues.append(ValidationIssue("PROFILE_DURATION", f"target_seconds {target} is below profile minimum {lo}"))
            if hi is not None and target > hi:
                issues.append(ValidationIssue("PROFILE_DURATION", f"target_seconds {target} exceeds profile maximum {hi}"))
        return issues
