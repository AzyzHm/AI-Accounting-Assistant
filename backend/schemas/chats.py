from pydantic import BaseModel


class MessageRequest(BaseModel):
    query: str


class RenameRequest(BaseModel):
    title: str
