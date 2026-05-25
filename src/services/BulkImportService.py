from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from models.DBRecording import DBRecording
from repositories.LocalRecordingsRepository import LocalRecordingsRepository
from repositories.SqliteDBRepository import SqliteDBRepository


AUDIO_EXTENSIONS = {".mp3"}
TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | TEXT_EXTENSIONS
PAIR_MATCH_THRESHOLD = 0.58
SUMMARY_NEEDS_REVIEW = "Needs review: no clear summary section was detected in the imported text file."
PAIR_STATUS_MATCHED = "matched"
PAIR_STATUS_NEEDS_REVIEW = "needs review"
PAIR_STATUS_DUPLICATE = "skipped duplicate"

PAIRING_STOPWORDS = {
    "ai",
    "audio",
    "call",
    "meeting",
    "minutes",
    "note",
    "notes",
    "rec",
    "recording",
    "summary",
    "summaries",
    "transcript",
    "transcription",
}

SECTION_LABELS = {
    "transcript": {"transcript", "transcription", "full transcript", "trascrizione"},
    "summary": {"summary", "ai summary", "meeting summary", "recap", "sintesi", "riepilogo"},
}


class BulkImportService:
    def __init__(
        self,
        sqlite_db_repository: SqliteDBRepository,
        local_recordings_repository: LocalRecordingsRepository,
    ):
        self._sqlite_db_repository = sqlite_db_repository
        self._local_recordings_repository = local_recordings_repository

    def preview_folder(self, folder_path: str, recursive: bool = False) -> dict:
        root, error = self._validate_folder(folder_path)
        if error:
            return {"ok": False, "error": error}
        sources, unsupported, errors = self._sources_from_folder(root, recursive)
        return self._preview_sources(sources, unsupported=unsupported, errors=errors, mode="folder")

    def confirm_folder(
        self,
        folder_path: str,
        recursive: bool = False,
        selected_pair_ids: list[str] | None = None,
    ) -> dict:
        root, error = self._validate_folder(folder_path)
        if error:
            return {"ok": False, "error": error}
        sources, unsupported, errors = self._sources_from_folder(root, recursive)
        return self._confirm_sources(
            sources,
            selected_pair_ids=selected_pair_ids,
            unsupported=unsupported,
            errors=errors,
        )

    def preview_upload(self, files: list[tuple[str, bytes]]) -> dict:
        sources, unsupported = self._sources_from_upload(files)
        return self._preview_sources(sources, unsupported=unsupported, errors=[], mode="upload")

    def confirm_upload(
        self,
        files: list[tuple[str, bytes]],
        selected_pair_ids: list[str] | None = None,
    ) -> dict:
        sources, unsupported = self._sources_from_upload(files)
        return self._confirm_sources(sources, selected_pair_ids=selected_pair_ids, unsupported=unsupported, errors=[])

    def preview(self, folder_path: str, recursive: bool = False, transcribe_audio: bool = False) -> dict:
        return self.preview_folder(folder_path=folder_path, recursive=recursive)

    def confirm(
        self,
        folder_path: str,
        recursive: bool = False,
        selected_paths: list[str] | None = None,
        selected_pair_ids: list[str] | None = None,
        **_kwargs,
    ) -> dict:
        return self.confirm_folder(
            folder_path=folder_path,
            recursive=recursive,
            selected_pair_ids=selected_pair_ids or selected_paths,
        )

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

    def _sources_from_folder(self, root: Path, recursive: bool) -> tuple[list[dict], list[dict], list[dict]]:
        sources = []
        unsupported = []
        errors = []
        paths = root.rglob("*") if recursive else root.iterdir()

        for path in sorted(paths):
            if path.is_dir():
                continue
            ext = path.suffix.lower()
            try:
                info = self._base_file_info(path)
                if ext not in SUPPORTED_EXTENSIONS:
                    unsupported.append({**info, "reason": "Unsupported file type"})
                    continue
                sources.append({**info, "source_type": "path", "path": str(path.resolve())})
            except Exception as exc:
                errors.append({"path": str(path), "filename": path.name, "error": str(exc)})
        return sources, unsupported, errors

    @staticmethod
    def _sources_from_upload(files: list[tuple[str, bytes]]) -> tuple[list[dict], list[dict]]:
        sources = []
        unsupported = []
        for filename, data in files:
            path = Path(filename)
            ext = path.suffix.lower()
            item = {
                "source_type": "upload",
                "filename": path.name,
                "extension": ext,
                "size": len(data),
                "data": data,
            }
            if ext not in SUPPORTED_EXTENSIONS:
                public_item = {k: v for k, v in item.items() if k != "data"}
                unsupported.append({**public_item, "reason": "Unsupported file type"})
                continue
            sources.append(item)
        return sources, unsupported

    def _preview_sources(self, sources: list[dict], unsupported: list[dict], errors: list[dict], mode: str) -> dict:
        pairs, unmatched = self._build_pairs(sources)
        preview_pairs = [self._preview_pair(pair) for pair in pairs]
        duplicate_count = len([pair for pair in preview_pairs if pair["status"] == PAIR_STATUS_DUPLICATE])
        importable_count = len(preview_pairs) - duplicate_count

        return {
            "ok": True,
            "mode": mode,
            "counts": {
                "pairs": len(preview_pairs),
                "importable": importable_count,
                "duplicates": duplicate_count,
                "unmatched": len(unmatched),
                "unsupported": len(unsupported),
                "errors": len(errors),
            },
            "pairs": preview_pairs,
            "unmatched": unmatched,
            "unsupported": unsupported,
            "errors": errors,
        }

    def _confirm_sources(
        self,
        sources: list[dict],
        selected_pair_ids: list[str] | None,
        unsupported: list[dict],
        errors: list[dict],
    ) -> dict:
        selected = set(selected_pair_ids or [])
        pairs, unmatched = self._build_pairs(sources)
        previews = [self._preview_pair(pair, include_sources=True) for pair in pairs]
        if selected:
            previews = [pair for pair in previews if pair["pair_id"] in selected]

        imported = []
        skipped = []
        import_errors = list(errors)

        for pair in previews:
            if pair["status"] == PAIR_STATUS_DUPLICATE:
                skipped.append({**self._public_pair(pair), "status": PAIR_STATUS_DUPLICATE})
                continue
            try:
                imported.append(self._import_pair(pair))
            except Exception as exc:
                import_errors.append({**self._public_pair(pair), "error": str(exc)})

        return {
            "ok": True,
            "counts": {
                "imported": len(imported),
                "skipped_duplicate": len(skipped),
                "unmatched": len(unmatched),
                "unsupported": len(unsupported),
                "errors": len(import_errors),
            },
            "imported": imported,
            "skipped": skipped,
            "unmatched": unmatched,
            "unsupported": unsupported,
            "errors": import_errors,
        }

    def _build_pairs(self, sources: list[dict]) -> tuple[list[dict], list[dict]]:
        audio_files = [source for source in sources if source["extension"] in AUDIO_EXTENSIONS]
        text_files = [source for source in sources if source["extension"] in TEXT_EXTENSIONS]
        pairs = []
        used_text_refs = set()

        for audio in audio_files:
            match = self._best_text_match(audio, text_files, used_text_refs)
            if match:
                used_text_refs.add(self._source_ref(match))
                pairs.append({"audio": audio, "text": match})

        unmatched = []
        paired_audio_refs = {self._source_ref(pair["audio"]) for pair in pairs}
        for audio in audio_files:
            if self._source_ref(audio) not in paired_audio_refs:
                unmatched.append(self._public_source(audio, reason="No matching .txt file found"))
        for text in text_files:
            if self._source_ref(text) not in used_text_refs:
                unmatched.append(self._public_source(text, reason="No matching .mp3 file found"))
        return pairs, unmatched

    def _best_text_match(self, audio: dict, text_files: list[dict], used_text_refs: set[str]) -> dict | None:
        audio_key = self._normalized_pair_key(Path(audio["filename"]).stem)
        best = None
        best_score = 0.0

        for text in text_files:
            if self._source_ref(text) in used_text_refs:
                continue
            text_key = self._normalized_pair_key(Path(text["filename"]).stem)
            score = 1.0 if audio_key == text_key else difflib.SequenceMatcher(None, audio_key, text_key).ratio()
            if score > best_score:
                best = text
                best_score = score

        return best if best and best_score >= PAIR_MATCH_THRESHOLD else None

    def _preview_pair(self, pair: dict, include_sources: bool = False) -> dict:
        audio = pair["audio"]
        text = pair["text"]
        text_content = self._read_source_text(text)
        parsed = self._parse_text_sections(text_content)
        recording_name = Path(audio["filename"]).stem
        title = self._title_from_name(recording_name)
        audio_hash = self._source_hash(audio)
        duplicate_reason = self._audio_duplicate_reason(audio, recording_name, audio_hash)
        status = PAIR_STATUS_DUPLICATE if duplicate_reason else PAIR_STATUS_MATCHED
        if not duplicate_reason and parsed["summary_status"] == PAIR_STATUS_NEEDS_REVIEW:
            status = PAIR_STATUS_NEEDS_REVIEW

        preview = {
            "pair_id": self._pair_id(audio, text),
            "status": status,
            "audio_file": audio["filename"],
            "text_file": text["filename"],
            "recording_name": recording_name,
            "detected_title": title,
            "summary_status": parsed["summary_status"],
            "transcript_status": parsed["transcript_status"],
            "reason": duplicate_reason,
        }
        if include_sources:
            preview["_audio"] = audio
            preview["_text"] = text
            preview["_parsed"] = parsed
            preview["_audio_hash"] = audio_hash
        return preview

    def _import_pair(self, pair: dict) -> dict:
        audio = pair["_audio"]
        parsed = pair["_parsed"]
        recording_name = pair["recording_name"]
        dest_path = self._local_recordings_repository.get_path(audio["filename"])

        if self._sqlite_db_repository.get_recording_by_name(recording_name):
            return {**self._public_pair(pair), "status": PAIR_STATUS_DUPLICATE}
        if os.path.exists(dest_path):
            return {**self._public_pair(pair), "status": PAIR_STATUS_DUPLICATE}

        if audio["source_type"] == "path":
            shutil.copy2(audio["path"], dest_path)
        else:
            with open(dest_path, "wb") as f:
                f.write(audio["data"])

        db_rec = DBRecording(
            id=None,
            name=recording_name,
            label=pair["detected_title"],
            duration=self._get_audio_duration(dest_path),
            file_extension="mp3",
            created_at=datetime.now(),
            recorded_at=self._parse_recording_datetime(recording_name),
            transcript=parsed["transcript"],
        )
        db_id = self._sqlite_db_repository.insert_recording(db_rec)
        self._sqlite_db_repository.save_summarization_result(
            recording_name,
            summary=parsed["summary"] or SUMMARY_NEEDS_REVIEW,
            title=pair["detected_title"],
            tags="needs-review" if parsed["summary_status"] == PAIR_STATUS_NEEDS_REVIEW else "",
            prompt_id="bulk_import_needs_review"
            if parsed["summary_status"] == PAIR_STATUS_NEEDS_REVIEW
            else "bulk_import",
        )

        return {
            **self._public_pair(pair),
            "status": "imported",
            "db_id": db_id,
        }

    @staticmethod
    def _parse_text_sections(content: str) -> dict:
        text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        transcription_heading = BulkImportService._find_transcription_heading(text)
        if transcription_heading:
            summary = text[: transcription_heading["start"]].strip()
            transcript = text[transcription_heading["end"] :].strip()
            if transcript:
                return {
                    "transcript": transcript,
                    "summary": summary,
                    "transcript_status": "detected",
                    "summary_status": "detected" if summary else PAIR_STATUS_NEEDS_REVIEW,
                }

        headings = []
        for match in re.finditer(r"(?im)^\s{0,3}#{0,6}\s*\*{0,2}([^:\n#*][^:\n*]{1,80})\*{0,2}\s*:?\s*$", text):
            label = re.sub(r"[^a-zA-Z ]+", " ", match.group(1)).strip().lower()
            section = BulkImportService._section_kind(label)
            if section:
                headings.append({"kind": section, "start": match.start(), "end": match.end()})

        transcript = ""
        summary = ""
        if headings:
            for index, heading in enumerate(headings):
                next_start = headings[index + 1]["start"] if index + 1 < len(headings) else len(text)
                body = text[heading["end"] : next_start].strip()
                if heading["kind"] == "transcript" and not transcript:
                    transcript = body
                if heading["kind"] == "summary" and not summary:
                    summary = body

        if not transcript and summary:
            transcript = text[: text.find(summary)].strip() or text
        if not transcript:
            transcript = text

        return {
            "transcript": transcript,
            "summary": summary,
            "transcript_status": "detected" if transcript else PAIR_STATUS_NEEDS_REVIEW,
            "summary_status": "detected" if summary else PAIR_STATUS_NEEDS_REVIEW,
        }

    @staticmethod
    def _find_transcription_heading(text: str) -> dict | None:
        heading_re = re.compile(r"(?im)^\s{0,3}#{0,6}\s*\*{0,2}([^:\n#*][^:\n*]{1,80})\*{0,2}\s*:?\s*$")
        for match in heading_re.finditer(text):
            label = re.sub(r"[^a-zA-Z ]+", " ", match.group(1)).strip().lower()
            if " ".join(label.split()) in {"transcription", "trascrizione"}:
                return {"start": match.start(), "end": match.end()}
        return None

    @staticmethod
    def _section_kind(label: str) -> str | None:
        compact = " ".join(label.split())
        for kind, labels in SECTION_LABELS.items():
            if compact in labels:
                return kind
        return None

    def _audio_duplicate_reason(self, audio: dict, recording_name: str, source_hash: str) -> str | None:
        if self._sqlite_db_repository.get_recording_by_name(recording_name):
            return "Recording already exists in database"

        if self._local_recordings_repository.exists(audio["filename"]):
            return "Local recording filename already exists"

        source_size = audio["size"]
        for local_filename in self._local_recordings_repository.get_all():
            local_path = Path(self._local_recordings_repository.get_path(local_filename))
            same_size = local_path.exists() and local_path.stat().st_size == source_size
            if same_size and self._sha256_path(local_path) == source_hash:
                return f"Audio content already exists locally as {local_filename}"
        return None

    @staticmethod
    def _normalized_pair_key(name: str) -> str:
        tokens = re.findall(r"[a-z0-9]+", name.lower())
        filtered = [token for token in tokens if token not in PAIRING_STOPWORDS]
        return " ".join(filtered or tokens)

    @staticmethod
    def _pair_id(audio: dict, text: dict) -> str:
        raw = f"{BulkImportService._source_ref(audio)}|{BulkImportService._source_ref(text)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _source_ref(source: dict) -> str:
        if source["source_type"] == "path":
            return source["path"]
        return source["filename"]

    @staticmethod
    def _public_source(source: dict, **extra) -> dict:
        return {
            "filename": source["filename"],
            "extension": source["extension"],
            "size": source["size"],
            **({"path": source["path"]} if source["source_type"] == "path" else {}),
            **extra,
        }

    @staticmethod
    def _public_pair(pair: dict) -> dict:
        return {key: value for key, value in pair.items() if not key.startswith("_")}

    @staticmethod
    def _base_file_info(path: Path) -> dict:
        return {
            "path": str(path.resolve()),
            "filename": path.name,
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
        }

    @staticmethod
    def _read_source_text(source: dict) -> str:
        if source["source_type"] == "path":
            return Path(source["path"]).read_text(encoding="utf-8")
        return source["data"].decode("utf-8")

    @staticmethod
    def _source_hash(source: dict) -> str:
        if source["source_type"] == "path":
            return BulkImportService._sha256_path(Path(source["path"]))
        return hashlib.sha256(source["data"]).hexdigest()

    @staticmethod
    def _sha256_path(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _title_from_name(name: str) -> str:
        return name.replace("_", " ").replace("-", " ").strip().title() or name

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
