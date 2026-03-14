from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    name: str
    org: str
    role: str  # "admin" | "user"


@dataclass(frozen=True, slots=True)
class ModelRoute:
    name: str
    upstream: str
    description: str = ""
