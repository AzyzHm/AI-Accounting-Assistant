from pydantic import BaseModel


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    email: str | None = None
