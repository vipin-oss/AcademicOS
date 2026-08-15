"""Prompt registry — versioned prompt assets (Sprint-7 M1, AI doc §A7.1).

``Prompts are versioned assets in a registry, not strings in code. Each
has an ID, semantic version, owner, eval-set binding, and A/B
configuration.`` — this is the smallest registry satisfying that doctrine:

- ``PromptAsset`` — one versioned prompt (id, semantic version, owner,
  system text). ``version`` is a monotone integer; ``version_label`` is the
  human-facing semantic version (e.g. "1.0").
- ``PromptRegistry`` — register / get by id (latest or pinned version) /
  all. Duplicate (id, version) registrations are rejected; unknown ids
  raise ``KeyError``; pinning a missing version raises ``KeyError``.
- The default asset ``assistant.default`` v1 carries the existing
  ``SYSTEM_INSTRUCTIONS`` text, so the Prompt Builder's behavior is
  unchanged when the registry is wired with the default.

Prompt construction itself stays in the Prompt Builder (the single owner);
the registry only stores and version-identifies the system text.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptAsset:
    id: str
    version: int  # monotone integer version
    version_label: str  # human-facing semantic version
    owner: str  # owning team/module
    system_text: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Prompt id must not be empty.")
        if self.version < 1:
            raise ValueError("Prompt version must be >= 1.")
        if not self.system_text.strip():
            raise ValueError("Prompt text must not be empty.")


DEFAULT_PROMPT_ID = "assistant.default"
DEFAULT_PROMPT_OWNER = "assistant"


class PromptRegistry:
    """Named, versioned prompt assets with deterministic lookup."""

    def __init__(self) -> None:
        self._assets: dict[str, dict[int, PromptAsset]] = {}

    def register(self, asset: PromptAsset) -> PromptAsset:
        """Register one version; duplicate (id, version) is rejected."""
        versions = self._assets.setdefault(asset.id, {})
        if asset.version in versions:
            raise ValueError(
                f"Prompt {asset.id} version {asset.version} already registered."
            )
        versions[asset.version] = asset
        return asset

    def get(self, prompt_id: str, version: int | None = None) -> PromptAsset:
        """The pinned version, or the LATEST when ``version`` is None."""
        versions = self._assets.get(prompt_id)
        if not versions:
            raise KeyError(f"Unknown prompt: {prompt_id}")
        if version is not None:
            if version not in versions:
                raise KeyError(f"Prompt {prompt_id} has no version {version}.")
            return versions[version]
        return versions[max(versions)]

    def latest_version(self, prompt_id: str) -> int:
        return self.get(prompt_id).version

    def all(self) -> list[PromptAsset]:
        out: list[PromptAsset] = []
        for prompt_id in sorted(self._assets):
            out.extend(
                self._assets[prompt_id][version]
                for version in sorted(self._assets[prompt_id])
            )
        return out
