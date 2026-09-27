from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .state import ACTIVATION_RANK


VALID_ACTIVATION = {"required", "inline", "optional", "skip"}


@dataclass(frozen=True)
class ActivationRule:
    status: str
    when_any: tuple[str, ...] = ()
    when_all: tuple[str, ...] = ()
    force: bool = False

    def matches(self, features: set[str]) -> bool:
        if self.when_any and not any(f in features for f in self.when_any):
            return False
        if self.when_all and not all(f in features for f in self.when_all):
            return False
        return bool(self.when_any or self.when_all)


@dataclass(frozen=True)
class SkillManifest:
    id: str
    layer: str
    scopes: tuple[str, ...]
    task_scope: dict[str, Any]
    requires: tuple[str, ...] = ()
    after_if_active: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    consumes: tuple[str, ...] = ()
    gates: tuple[str, ...] = ()
    assurance: bool = False
    orchestration_only: bool = False
    default_activation: str = "optional"
    profile_activation: dict[str, str] = field(default_factory=dict)
    activation_rules: tuple[ActivationRule, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillManifest":
        activation = data.get("activation", {})
        rules = []
        for item in activation.get("rules", []):
            rules.append(ActivationRule(
                status=item["status"],
                when_any=tuple(item.get("when_any", [])),
                when_all=tuple(item.get("when_all", [])),
                force=bool(item.get("force", False)),
            ))
        return cls(
            id=data["id"],
            layer=data.get("layer", "creator"),
            scopes=tuple(data.get("scopes", ["project"])),
            task_scope=dict(data.get("task_scope", {})),
            requires=tuple(data.get("requires", [])),
            after_if_active=tuple(data.get("after_if_active", [])),
            produces=tuple(data.get("produces", [])),
            consumes=tuple(data.get("consumes", [])),
            gates=tuple(data.get("gates", [])),
            assurance=bool(data.get("assurance", False)),
            orchestration_only=bool(data.get("orchestration_only", False)),
            default_activation=activation.get("default", "optional"),
            profile_activation=dict(activation.get("profiles", {})),
            activation_rules=tuple(rules),
        )

    def activation_for(self, profile: str, features: set[str]) -> str:
        status = self.profile_activation.get(profile, self.default_activation)
        if status not in VALID_ACTIVATION:
            raise ValueError(f"invalid activation status {status} in {self.id}")
        for rule in self.activation_rules:
            if rule.status not in VALID_ACTIVATION:
                raise ValueError(f"invalid rule activation {rule.status} in {self.id}")
            if rule.matches(features):
                if rule.force or ACTIVATION_RANK[rule.status] > ACTIVATION_RANK[status]:
                    status = rule.status
        return status

    def scopes_for(self, profile: str) -> tuple[str, ...]:
        value = self.task_scope.get(profile, self.task_scope.get("default", self.scopes[0] if self.scopes else "project"))
        if isinstance(value, str):
            return (value,)
        return tuple(value)


class SkillRegistry:
    def __init__(self, manifests: dict[str, SkillManifest]):
        self.manifests = manifests
        self._validate()

    @classmethod
    def load(cls, skills_dir: Path) -> "SkillRegistry":
        manifests: dict[str, SkillManifest] = {}
        for path in sorted(skills_dir.glob("*/skill.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            manifest = SkillManifest.from_dict(data)
            if manifest.id in manifests:
                raise ValueError(f"duplicate skill id: {manifest.id}")
            manifests[manifest.id] = manifest
        if not manifests:
            raise ValueError(f"no skill manifests found under {skills_dir}")
        return cls(manifests)

    def _validate(self) -> None:
        for skill in self.manifests.values():
            for dep in skill.requires + skill.after_if_active:
                if dep not in self.manifests:
                    raise ValueError(f"skill {skill.id} references unknown skill {dep}")

    def get(self, skill_id: str) -> SkillManifest:
        return self.manifests[skill_id]

    def active(self) -> list[SkillManifest]:
        return [m for m in self.manifests.values() if not m.orchestration_only]
