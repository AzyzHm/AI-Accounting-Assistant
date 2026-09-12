from pydantic import BaseModel, Field

from schemas.roles import Role


class RoleUpdateRequest(BaseModel):
    role: Role


class LimitsUpdateRequest(BaseModel):
    """Full set of per-user quota overrides, always sent and saved together
    so a partial update can never leave one field pointing at a stale
    value."""

    daily_token_limit: int = Field(ge=0)
    daily_search_limit: int = Field(ge=0)
    monthly_token_limit: int = Field(ge=0)
    monthly_search_limit: int = Field(ge=0)
