"""Frozen capability taxonomy and evaluation schema (L0).

DATA only — not a router. Production question parsing must not import this
package, and this package must not import intents / rules-v1.
"""

from app.application.capabilities.eval_schema import (
    ALLOWED_GATE_LEVELS,
    ALLOWED_LANGUAGES,
    CapabilityCase,
    CapabilityCaseResult,
    CapabilityCheck,
)
from app.application.capabilities.registry import (
    CAPABILITIES,
    CapabilitySpec,
    is_frozen_capability,
)

__all__ = [
    "ALLOWED_GATE_LEVELS",
    "ALLOWED_LANGUAGES",
    "CAPABILITIES",
    "CapabilityCase",
    "CapabilityCaseResult",
    "CapabilityCheck",
    "CapabilitySpec",
    "is_frozen_capability",
]
