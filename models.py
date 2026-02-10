from __future__ import annotations

from enum import Enum
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field, AnyUrl, field_validator, model_validator


class DebateSide(str, Enum):
    pro = "pro"
    con = "con"


class OutputFormat(str, Enum):
    points = "points"
    rebuttal_paragraphs = "rebuttal_paragraphs"
    referenced_paragraphs = "referenced_paragraphs"


class StudentSubmission(BaseModel):
    motion: str = Field(..., description="The debate motion/topic, phrased as a statement.")
    student_side: DebateSide = Field(..., description="Which side the student is arguing: pro or con.")
    argument_text: str = Field(..., description="The student's argument text supporting their side.")
    requested_format: OutputFormat = Field(..., description="Desired output format for the counter-argument.")


class UnderstoodArguments(BaseModel):
    summary: str
    key_points: List[str]
    detected_claims: List[str]


class CounterPoint(BaseModel):
    point: str
    support: Optional[str] = None

class PointsResponse(BaseModel):
    points: List[CounterPoint]


class RebuttalParagraphs(BaseModel):
    paragraphs: List[str]


class Reference(BaseModel):
    title: Optional[str] = None
    url: AnyUrl

    @field_validator("url")
    @classmethod
    def validate_url_returns_200(cls, v: AnyUrl) -> AnyUrl:
        """Ensure the URL returns a 200 status code."""
        url_str = str(v)
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            response = httpx.head(
                url_str,
                timeout=10.0,
                follow_redirects=True,
                headers=headers,
            )
            if response.status_code >= 400:
                response = httpx.get(
                    url_str,
                    timeout=10.0,
                    follow_redirects=True,
                    headers=headers,
                )

            # Many authoritative sources block non-browser clients and return 401/403.
            # Treat those as "reachable" but still reject missing resources.
            if response.status_code in (404, 410):
                raise ValueError(f"URL '{url_str}' returned status {response.status_code}")
            if response.status_code >= 400 and response.status_code not in (401, 403):
                raise ValueError(f"URL '{url_str}' returned status {response.status_code}")
        except httpx.RequestError as e:
            raise ValueError(f"Failed to reach URL '{url_str}': {e}") from e
        return v


class ReferencedParagraph(BaseModel):
    text: str
    references: List[Reference] = Field(default_factory=list)


class ReferencedParagraphs(BaseModel):
    paragraphs: List[ReferencedParagraph]

    @model_validator(mode="after")
    def ensure_unique_urls_across_paragraphs(self) -> "ReferencedParagraphs":
        seen: set[str] = set()
        for idx, p in enumerate(self.paragraphs):
            if not p.references:
                raise ValueError(f"paragraphs.{idx}.references must not be empty")
            for r in p.references:
                url_str = str(r.url)
                if url_str in seen:
                    raise ValueError(
                        f"Duplicate reference URL across paragraphs is not allowed: {url_str}"
                    )
                seen.add(url_str)
        return self


class EvidenceBasedReference(BaseModel):
    """A reference that comes from verified web search results."""
    url: str = Field(description="The exact URL from the gathered evidence")
    title: Optional[str] = None
    supporting_claim: str = Field(description="The specific claim from this source used in the paragraph")


class EvidenceBasedParagraph(BaseModel):
    """A paragraph built from verified evidence sources."""
    text: str = Field(description="The argument paragraph text")
    references: List[EvidenceBasedReference] = Field(
        min_length=1,
        description="References from the gathered evidence supporting this paragraph"
    )


class EvidenceBasedResponse(BaseModel):
    """Response built entirely from verified evidence sources."""
    paragraphs: List[EvidenceBasedParagraph]

    @model_validator(mode="after")
    def ensure_unique_urls_across_paragraphs(self) -> "EvidenceBasedResponse":
        seen: set[str] = set()
        for p in self.paragraphs:
            for r in p.references:
                if r.url in seen:
                    raise ValueError(
                        f"Duplicate reference URL across paragraphs: {r.url}"
                    )
                seen.add(r.url)
        return self
