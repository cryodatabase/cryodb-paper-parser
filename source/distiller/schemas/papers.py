from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class PaperStatus(str, Enum):

    PENDING = "PENDING"
    DOWNLOADED = "DOWNLOADED"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    NO_FULLTEXT = "NO_FULLTEXT"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class Paper(BaseModel):

    # Primary key & identifiers
    id: Optional[UUID] = Field(None, description="Primary key (UUID, generated by DB)")
    paper_id: Optional[str] = Field(None, description="External paper identifier, e.g. PMID:123")
    doi: Optional[str] = None
    source: str = Field(..., description="Source of the paper, e.g. PMC")

    # Bibliographic metadata
    title: Optional[str] = None
    journal: Optional[str] = None
    published_year: Optional[int] = None
    published_month: Optional[int] = None
    published_day: Optional[int] = None

    abstract: Optional[str] = None
    authors_json: Optional[Dict[str, Any]] = None
    authors_flat: Optional[str] = None

    # Links / access info
    paper_url: Optional[str] = None
    download_url: Optional[str] = None
    is_free_fulltext: Optional[bool] = None
    license: Optional[str] = None

    # File-related fields
    md5_hash: Optional[str] = Field(
        None, min_length=32, max_length=32, description="MD5 hash of the PDF/XML file"
    )
    file_size_bytes: Optional[int] = None
    file_s3_uri: Optional[str] = None
    fulltext_s3_uri: Optional[str] = None

    # Extraction results
    cpa_facts_json: Optional[Dict[str, Any]] = None

    # Status & timestamps
    status: PaperStatus = Field(PaperStatus.PENDING, description="Processing status")
    created_at: Optional[datetime] = None

    class Config:  # type: ignore[override]
        orm_mode = True  # Pydantic v1; accepted by v2 as well
        from_attributes = True  # Pydantic v2 equivalent

    # ───────────────────────── validators ────────────────────────
    @field_validator("md5_hash", mode="before")
    @classmethod
    def _strip_md5(cls, v: str | None) -> str | None:
        """Trim stray spaces/newlines around the MD5 string."""
        return v.strip() if isinstance(v, str) else v