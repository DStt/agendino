from datetime import datetime


class DBRecording:
    def __init__(
        self,
        id: int,
        name: str,
        label: str,
        duration: int,
        created_at: datetime,
        transcript: str | None = None,
        file_extension: str = "hda",
        recorded_at: str | None = None,
        folder: str = "/",
        summary: str | None = None,
        title: str | None = None,
        tags: str | None = None,
        notion_url: str | None = None,
    ):
        self.id = id
        self.name = name
        self.label = label
        self.duration = duration
        self.created_at = created_at
        self.transcript = transcript
        self.file_extension = file_extension
        self.recorded_at = recorded_at
        self.folder = folder
        # Compatibility fields: populated from latest summary when available.
        self.summary = summary
        self.title = title
        self.tags = tags
        self.notion_url = notion_url

    @staticmethod
    def from_dict(data):
        keys = data.keys()
        return DBRecording(
            id=data["id"],
            name=data["name"],
            label=data["label"],
            duration=data["duration"],
            created_at=datetime.fromisoformat(data["created_at"]),
            transcript=data["transcript"] if "transcript" in keys else None,
            file_extension=data["file_extension"] if "file_extension" in keys else "hda",
            recorded_at=data["recorded_at"] if "recorded_at" in keys else None,
            folder=data["folder"] if "folder" in keys else "/",
            summary=data["summary"] if "summary" in keys else None,
            title=data["title"] if "title" in keys else None,
            tags=data["tags"] if "tags" in keys else None,
            notion_url=data["notion_url"] if "notion_url" in keys else None,
        )
