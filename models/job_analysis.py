from pydantic import BaseModel, Field


class JobAnalysis(BaseModel):
    job_title: str = ""
    company_name: str = ""
    required_technical_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    required_experience: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    important_keywords: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    relevant_projects_and_achievements: list[str] = Field(default_factory=list)
    unsupported_skills_to_avoid_claiming: list[str] = Field(default_factory=list)
    tailoring_recommendations: list[str] = Field(default_factory=list)
