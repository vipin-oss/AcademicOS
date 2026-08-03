"""Command: Import an exported settings document (PART 6)."""
from dataclasses import dataclass

from app.application.dtos.settings import ImportSettingsInput


@dataclass
class ImportSettingsCommand:
    input: ImportSettingsInput
