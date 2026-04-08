from pydantic import BaseModel


class LoginRequestDTO(BaseModel):
    username: str
    password: str
