"""Command: Remove the profile photo."""
from dataclasses import dataclass


@dataclass
class DeleteProfilePhotoCommand:
    updated_by: str = "system"
