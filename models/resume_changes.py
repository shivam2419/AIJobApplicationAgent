from pydantic import BaseModel, Field, model_validator


class ResumeChange(BaseModel):
    section: str
    original_text: str
    proposed_text: str
    reason: str
    supporting_evidence: str


class ResumeChangeProposal(BaseModel):
    changes: list[ResumeChange] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_and_original_text(self) -> "ResumeChangeProposal":
        for change in self.changes:
            if not change.original_text.strip():
                raise ValueError("Each proposed change must identify existing text.")
            if not change.supporting_evidence.strip():
                raise ValueError("Each proposed change must cite resume evidence.")
        return self
