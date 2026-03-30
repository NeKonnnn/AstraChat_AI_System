"""Фильтры по метаданным документа при векторном поиске."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DocumentVectorSearchFilters:
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    filename_contains: Optional[str] = None

    def active(self) -> bool:
        return bool(self.date_from or self.date_to or (self.filename_contains and self.filename_contains.strip()))
