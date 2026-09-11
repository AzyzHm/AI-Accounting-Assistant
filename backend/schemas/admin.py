from pydantic import BaseModel

from schemas.roles import Role


class RoleUpdateRequest(BaseModel):
    role: Role
