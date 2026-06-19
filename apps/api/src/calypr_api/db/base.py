"""Declarative base shared by all ORM models (and Alembic's target metadata)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
