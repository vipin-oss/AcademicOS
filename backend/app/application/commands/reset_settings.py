"""Command: Reset settings sections to factory defaults (PART 6)."""
from dataclasses import dataclass

from app.application.dtos.settings import ResetSettingsInput


@dataclass
class ResetSettingsCommand:
    input: ResetSettingsInput
