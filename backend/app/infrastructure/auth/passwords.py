"""Password hashing (infrastructure adapter).

bcrypt — the hashing library the approved roadmap adds to the frozen stack
("the frozen stack has no hashing lib — add one"). Salted, adaptive; the
cost factor (work factor 12) is the bcrypt default and can be raised
without breaking verification of existing hashes.
"""
from __future__ import annotations

import bcrypt

# bcrypt hard-caps inputs at 72 bytes; fail loudly on longer passwords
# rather than silently truncating (which would make two different long
# passwords verify as equal).
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a plaintext password. Returns the bcrypt hash string."""
    raw = password.encode("utf-8")
    if len(raw) > _MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 bytes.")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time comparison of a plaintext against a stored hash.

    Returns False (never raises) for malformed hashes, so a corrupt
    credential row degrades to a failed login — never a 500.
    """
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


class BcryptPasswordHasher:
    """Infrastructure adapter for the PasswordHasher port (bcrypt)."""

    def hash_password(self, password: str) -> str:
        return hash_password(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)
