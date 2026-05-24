from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Protocol

from models.DBRecording import DBRecording
from repositories.LocalRecordingsRepository import LocalRecordingsRepository
from repositories.SqliteDBRepository import SqliteDBRepository


class AudioTranscriptionService(Protocol):
    def transcribe(self, audio_path: str, mime_type: str = "audio/mpeg") -> str:
        ...


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}
TEXT_EXTENSIONS = {".txt", ".md"}
STRUCTURED_EXTENSIONS = {".json"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | TEXT_EXTENSIONS | STRUCTURED_EXTENSIONS

MIME_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
}

TRANSCRIPT_HINTS = {"transcript", "transcription", "trascrizione"}
SUMMARY_HINTS = {"summary", "summaries", "recap", "notes", "minutes", "sintesi", "riepilogo", "verbale"}
NAME_SUFFIXES = [
    "_transcript",
    "-transcript",
    " transcript",
    "_transcription",
    "-transcription",
    " transcription",
    "_summary",
    "-summary",
    " summary",
    "_recap",
    "-recap",
    " recap",
    "_notes",
    "-notes",
    " notes",
    "_minutes",
    "-minutes",
    " minutes",
]


class BulkImportService:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        local_recordings_repository: LocalRecordingsRepository,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._local_recordings_repository = local_recordings_repository

    def preview(self, folder_path: str, recursive: bool = False, transcribe_audio: bool = False) -> dict:
        root, error = self._validate_folder(folder_path)
        if error:
            return {"ok": False, "error": error}

        results = self._scan(root, recursive=recursive)
        return {
            "ok": True,
            "folder_path": str(root),
            "recursive": recursive,
            "transcribe_audio": transcribe_audio,
            **results,
        }

    def confirm(
        self,
        folder_path: str,
        recursive: bool = False,
        transcribe_audio: bool = False,
        selected_paths: list[str] | None = None,
        transcription_service: AudioTranscriptionService | None = None,
    ) -> dict:
        root, error = self._validate_folder(folder_path)
        if error:
            return {"ok": False, "error": error}

        selected = {str(Path(path).resolve()) for path in selected_paths or []}
        scanned = self._scan(root, recursive=recursive)
        importable = scanned["importable"]
        if selected:
            importable = [item for item in importable if item["path"] in selected]

        imported = []
        skipped = []
        errors = []

        for item in importable:
            try:
                if item["kind"] == "audio":
                    result = self._import_audio(item, transcribe_audio, transcription_service)
                else:
                    result = self._import_metadata(item)

                if result.get("ok"):
                    imported.append(result)
                else:
                    skipped.append({**item, "reason": result.get("reason", "Skipped")})
            except Exception as exc:
                errors.append({**item, "error": str(exc)})

        return {
            "ok": True,
            "counts": {
                "imported": len(imported),
                "skipped": len(skipped),
                "errors": len(errors),
            },
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "duplicates": scanned["duplicates"],
            "unsupported": scanned["unsupported"],
        }

    @staticmethod
    def _validate_folder(folder_path: str) -> tuple[Path | None, str | None]:
        if not folder_path or not folder_path.strip():
            return None, "Folder path is required"
        root = Path(folder_path).expanduser().resolve()
        if not root.exists():
            return None, f"Folder does not exist: {root}"
        if not root.is_dir():
            return None, f"Path is not a folder: {root}"
        return root, None

    def _scan(self, root: Path, recursive: bool) -> dict:
        importable = []
        duplicates = []
        unsupported = []
        errors = []

        paths = root.rglob("*") if recursive else root.iterdir()
        for path in sorted(paths):
            if path.is_dir():
                continue
            ext = path.suffix.lower()
            try:
                if ext not in SUPPORTED_EXTENSIONS:
                    unsupported.append(self._base_file_info(path, reason="Unsupported file type"))
                    continue

                if ext in AUDIO_EXTENSIONS:
                    item = self._preview_audio(path)
                elif ext in TEXT_EXTENSIONS:
                    item = self._preview_text(path)
                else:
                    item = self._preview_json(path)

                if item.get("duplicate"):
                    duplicates.append(item)
                elif item.get("importable", True):
                    importable.append(item)
                else:
                    unsupported.append(item)
            except Exception as exc:
                errors.append(self._base_file_info(path, error=str(exc)))

        return {
            "counts": {
                "importable": len(importable),
                "duplicates": len(duplicates),
                "unsupported": len(unsupported),
                "errors": len(errors),
            },
            "importable": importable,
            "duplicates": duplicates,
            "unsupported": unsupported,
            "errors": errors,
        }

    def _preview_audio(self, path: Path) -> dict:
        filename = path.name
        stem = path.stem
        file_hash = self._sha256(path)
        info = {
            **self._base_file_info(path),
            "kind": "audio",
            "recording_name": stem,
            "title": self._title_from_name(stem),
            "action": "add_recording",
            "sha256": file_hash,
        }

        duplicate_reason = self._audio_duplicate_reason(path, stem, file_hash)
        if duplicate_reason:
            return {**info, "duplicate": True, "reason": duplicate_reason}
        if self._local_recordings_repository.exists(filename):
            return {**info, "duplicate": True, "reason": "Local recording filename already exists"}
        return info

    def _preview_text(self, path: Path) -> dict:
        content = path.read_text(encoding="utf-8")
        target_name = self._target_name_from_stem(path.stem)
        content_kind = self._text_content_kind(path)
        title = self._title_from_name(target_name)
        info = {
            **self._base_file_info(path),
            "kind": "text",
            "content_kind": content_kind,
            "recording_name": target_name,
            "title": title,
            "action": f"import_{content_kind}",
        }
        duplicate_reason = self._metadata_duplicate_reason(target_name, content_kind, content)
        if duplicate_reason:
            return {**info, "duplicate": True, "reason": duplicate_reason}
        return info

    def _preview_json(self, path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8"))
        parsed = self._parse_json_metadata(path, data)
        if not parsed:
            return {
                **self._base_file_info(path),
                "kind": "structured",
                "importable": False,
                "reason": "JSON does not contain recognized transcript or summary fields",
            }

        duplicate_reasons = []
        if parsed.get("transcript"):
            reason = self._metadata_duplicate_reason(parsed["recording_name"], "transcript", parsed["transcript"])
            if reason:
                duplicate_reasons.append(reason)
        if parsed.get("summary"):
            reason = self._metadata_duplicate_reason(parsed["recording_name"], "summary", parsed["summary"])
            if reason:
                duplicate_reasons.append(reason)

        info = {
            **self._base_file_info(path),
            "kind": "structured",
            "content_kind": "metadata",
            "recording_name": parsed["recording_name"],
            "title": parsed["title"],
            "tags": parsed["tags"],
            "has_transcript": bool(parsed.get("transcript")),
            "has_summary": bool(parsed.get("summary")),
            "action": "import_json_metadata",
            "_parsed": parsed,
        }
        if duplicate_reasons and len(duplicate_reasons) == int(bool(parsed.get("transcript"))) + int(bool(parsed.get("summary"))):
            return {**info, "duplicate": True, "reason": "; ".join(duplicate_reasons)}
        return info

    def _import_audio(
        self,
        item: dict,
        transcribe_audio: bool,
        transcription_service: AudioTranscriptionService | None,
    ) -> dict:
        source = Path(item["path"])
        dest_path = self._local_recordings_repository.get_path(source.name)

        if self._sqlite_db_repository.get_recording_by_name(item["recording_name"]):
            return {"ok": False, "reason": "Recording already exists in database"}
        if os.path.exists(dest_path):
            return {"ok": False, "reason": "Local recording filename already exists"}

        shutil.copy2(source, dest_path)
        duration = self._get_audio_duration(dest_path)
        db_rec = DBRecording(
            id=None,
            name=item["recording_name"],
            label=item["title"],
            duration=duration,
            file_extension=source.suffix.lower().lstrip("."),
            created_at=datetime.now(),
            recorded_at=self._parse_recording_datetime(item["recording_name"]),
        )
        db_id = self._sqlite_db_repository.insert_recording(db_rec)

        transcript_status = "skipped"
        if transcribe_audio:
            if transcription_service is None:
                transcript_status = "not_configured"
            else:
                transcript = transcription_service.transcribe(
                    dest_path,
                    mime_type=MIME_TYPES.get(db_rec.file_extension, "audio/mpeg"),
                )
                self._sqlite_db_repository.save_transcript(item["recording_name"], transcript)
                transcript_status = "created"

        return {
            "ok": True,
            "path": item["path"],
            "kind": "audio",
            "recording_name": item["recording_name"],
            "db_id": db_id,
            "transcript": transcript_status,
        }

    def _import_metadata(self, item: dict) -> dict:
        if item["kind"] == "structured":
            parsed = item["_parsed"]
            return self._import_json_metadata(item, parsed)

        content = Path(item["path"]).read_text(encoding="utf-8")
        self._ensure_recording(item["recording_name"], item["title"], Path(item["path"]).suffix.lower().lstrip("."))
        if item["content_kind"] == "transcript":
            existing = self._sqlite_db_repository.get_transcript(item["recording_name"])
            if existing:
                return {"ok": False, "reason": "Recording already has a transcript"}
            self._sqlite_db_repository.save_transcript(item["recording_name"], content)
        else:
            if self._sqlite_db_repository.get_summary(item["recording_name"]):
                return {"ok": False, "reason": "Recording already has a summary"}
            self._sqlite_db_repository.save_summarization_result(
                item["recording_name"],
                summary=content,
                title=item["title"],
                tags="",
                prompt_id="bulk_import",
            )
        return {
            "ok": True,
            "path": item["path"],
            "kind": item["kind"],
            "content_kind": item["content_kind"],
            "recording_name": item["recording_name"],
        }

    def _import_json_metadata(self, item: dict, parsed: dict) -> dict:
        self._ensure_recording(parsed["recording_name"], parsed["title"], "json")
        imported_fields = []
        skipped_fields = []

        transcript = parsed.get("transcript")
        if transcript:
            if self._sqlite_db_repository.get_transcript(parsed["recording_name"]):
                skipped_fields.append("transcript")
            else:
                self._sqlite_db_repository.save_transcript(parsed["recording_name"], transcript)
                imported_fields.append("transcript")

        summary = parsed.get("summary")
        if summary:
            if self._sqlite_db_repository.get_summary(parsed["recording_name"]):
                skipped_fields.append("summary")
            else:
                self._sqlite_db_repository.save_summarization_result(
                    parsed["recording_name"],
                    summary=summary,
                    title=parsed["title"],
                    tags=",".join(parsed["tags"]),
                    prompt_id="bulk_import",
                )
                imported_fields.append("summary")

        if not imported_fields:
            return {"ok": False, "reason": f"All metadata already exists ({', '.join(skipped_fields)})"}

        return {
            "ok": True,
            "path": item["path"],
            "kind": "structured",
            "recording_name": parsed["recording_name"],
            "imported_fields": imported_fields,
            "skipped_fields": skipped_fields,
        }

    def _ensure_recording(self, name: str, title: str, file_extension: str) -> DBRecording:
        existing = self._sqlite_db_repository.get_recording_by_name(name)
        if existing:
            return existing
        db_rec = DBRecording(
            id=None,
            name=name,
            label=title or name,
            duration=0,
            file_extension=file_extension or "txt",
            created_at=datetime.now(),
            recorded_at=self._parse_recording_datetime(name),
        )
        db_rec.id = self._sqlite_db_repository.insert_recording(db_rec)
        return db_rec

    def _audio_duplicate_reason(self, path: Path, recording_name: str, source_hash: str) -> str | None:
        if self._sqlite_db_repository.get_recording_by_name(recording_name):
            return "Recording already exists in database"

        source_size = path.stat().st_size
        for local_filename in self._local_recordings_repository.get_all():
            local_path = Path(self._local_recordings_repository.get_path(local_filename))
            if local_filename == path.name:
                return "Local recording filename already exists"
            if local_path.exists() and local_path.stat().st_size == source_size and self._sha256(local_path) == source_hash:
                return f"Audio content already exists locally as {local_filename}"
        return None

    def _metadata_duplicate_reason(self, recording_name: str, content_kind: str, content: str) -> str | None:
        if content_kind == "transcript":
            existing = self._sqlite_db_repository.get_transcript(recording_name)
            if existing and existing.strip() == content.strip():
                return "Matching transcript already exists"
            if existing:
                return "Recording already has a transcript"
            return None

        existing_summary = self._sqlite_db_repository.get_summary(recording_name)
        if existing_summary and existing_summary.strip() == content.strip():
            return "Matching summary already exists"
        if existing_summary:
            return "Recording already has a summary"
        return None

    @staticmethod
    def _base_file_info(path: Path, **extra) -> dict:
        return {
            "path": str(path.resolve()),
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
            **extra,
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _title_from_name(name: str) -> str:
        return name.replace("_", " ").replace("-", " ").strip().title() or name

    @staticmethod
    def _target_name_from_stem(stem: str) -> str:
        lowered = stem.lower()
        for suffix in NAME_SUFFIXES:
            if lowered.endswith(suffix):
                return stem[: -len(suffix)].strip(" _-") or stem
        return stem

    @staticmethod
    def _text_content_kind(path: Path) -> str:
        tokens = set(path.stem.lower().replace("-", "_").split("_"))
        if tokens & TRANSCRIPT_HINTS:
            return "transcript"
        if tokens & SUMMARY_HINTS:
            return "summary"
        return "summary" if path.suffix.lower() == ".md" else "transcript"

    def _parse_json_metadata(self, path: Path, data) -> dict | None:
        if not isinstance(data, dict):
            return None

        transcript = self._first_text(data, ["transcript", "transcription", "text"])
        summary = self._first_text(data, ["summary", "summarization", "notes", "recap"])
        if not transcript and not summary:
            return None

        raw_name = self._first_text(data, ["name", "recording_name", "filename", "file_name"])
        recording_name = self._target_name_from_stem(Path(raw_name).stem if raw_name else path.stem)
        title = self._first_text(data, ["title", "label"]) or self._title_from_name(recording_name)
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        elif isinstance(tags, list):
            tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        else:
            tags = []

        return {
            "recording_name": recording_name,
            "title": title,
            "tags": tags,
            "transcript": transcript,
            "summary": summary,
        }

    @staticmethod
    def _first_text(data: dict, keys: list[str]) -> str:
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _get_audio_duration(file_path: str) -> int:
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(file_path)
            if audio and audio.info and audio.info.length:
                return int(audio.info.length)
        except Exception:
            pass
        return 0

    @staticmethod
    def _parse_recording_datetime(bare_name: str) -> str | None:
        try:
            parts = bare_name.split("-")
            if len(parts) >= 2:
                dt_str = f"{parts[0]}-{parts[1]}"
                dt = datetime.strptime(dt_str, "%Y%b%d-%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError):
            pass
        return None
