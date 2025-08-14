from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, validator


class TranscriptRequest(BaseModel):
    url: HttpUrl = Field(..., description="The full YouTube video URL.")
    language: Optional[str] = Field(
        default=None,
        description="Optional ISO 639-1 language code.",
        min_length=2,
        max_length=10,
    )
    include_timestamps: Optional[bool] = Field(
        default=False, description="Include [MM:SS] timestamps."
    )

    @validator("language")
    def _normalize_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            return None
        return v


class LanguageInfo(BaseModel):
    language: str
    language_code: str
    is_generated: bool


class TranscriptResponse(BaseModel):
    transcript: str
    language_used: str = Field(..., description="Language code actually used.")
    available_languages: List[LanguageInfo] = Field(default_factory=list)
    video_title: Optional[str] = Field(
        default=None, description="Best-effort YouTube video title."
    )


class BulkTranscriptRequest(BaseModel):
    """Request model for bulk transcript downloads."""
    inputs: str = Field(..., description="Links or identifier(s).")
    mode: Literal["auto", "links", "playlist", "channel"] = "auto"
    language: Optional[str] = Field(default=None, min_length=2, max_length=10)
    include_timestamps: Optional[bool] = False
    limit: Optional[int] = Field(default=400, description="Max videos to fetch in bulk.")

    @validator("language")
    def _norm_lang(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            return None
        return v
