"""Command: Set the profile photo (stored via the FileStorage port)."""
from dataclasses import dataclass

from app.application.dtos.settings import SetProfilePhotoInput


@dataclass
class SetProfilePhotoCommand:
    input: SetProfilePhotoInput
