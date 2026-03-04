"""PageIndex — hierarchical navigation tree (Stage 4)."""
from pydantic import BaseModel, Field


class PageIndexSection(BaseModel):
    """One node in the PageIndex tree."""
    title: str = Field("", description="Section title")
    page_start: int = Field(1, ge=1)
    page_end: int = Field(1, ge=1)
    child_sections: list["PageIndexSection"] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list, description="Extracted named entities")
    summary: str = Field("", description="LLM-generated 2–3 sentence summary")
    data_types_present: list[str] = Field(default_factory=list, description="e.g. tables, figures, equations")


PageIndexSection.model_rebuild()


class PageIndex(BaseModel):
    """Root of the document's PageIndex tree."""
    document_id: str = Field("")
    sections: list[PageIndexSection] = Field(default_factory=list)
