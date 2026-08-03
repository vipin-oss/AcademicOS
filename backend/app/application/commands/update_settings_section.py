"""Command: Update one section of the settings document."""
from dataclasses import dataclass

from app.application.dtos.settings import SectionUpdateInput


@dataclass
class UpdateSettingsSectionCommand:
    input: SectionUpdateInput
