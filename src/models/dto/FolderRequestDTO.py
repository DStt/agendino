from pydantic import BaseModel


class CreateFolderRequestDTO(BaseModel):
    path: str


class RenameFolderRequestDTO(BaseModel):
    old_path: str
    new_path: str


class DeleteFolderRequestDTO(BaseModel):
    path: str
    move_to: str = "/"

