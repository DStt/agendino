import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class ObsidianExportService:
    def __init__(self, vault_path: str):
        self._vault_path = Path(vault_path)

    @property
    def is_configured(self) -> bool:
        return bool(self._vault_path) and self._vault_path.exists()

    def publish_summary(
        self,
        title: str,
        summary_markdown: str,
        tags: list[str] | None = None,
        recording_name: str | None = None,
        folder: str = "/",
        duration_seconds: int | None = None,
        cost_data: list[dict] | None = None,
        tasks: list[dict] | None = None,
    ) -> dict:
        if not self.is_configured:
            return {"ok": False, "error": f"Obsidian vault path does not exist: {self._vault_path}"}

        # Build output directory
        base_dir = self._vault_path / "AgenDino"
        if folder and folder != "/":
            folder_clean = folder.strip("/")
            base_dir = base_dir / folder_clean

        base_dir.mkdir(parents=True, exist_ok=True)

        # Build filename
        filename = self._sanitize_filename(title or recording_name or "untitled") + ".md"
        file_path = base_dir / filename

        # Build frontmatter
        frontmatter = self._build_frontmatter(
            title=title,
            tags=tags,
            recording_name=recording_name,
            folder=folder,
            duration_seconds=duration_seconds,
            cost_data=cost_data,
        )

        # Build content
        content = f"---\n{frontmatter}---\n\n{summary_markdown}"

        # Append tasks as Obsidian checkboxes
        if tasks:
            content += "\n\n## Tasks\n\n"
            content += self._format_tasks(tasks)

        file_path.write_text(content, encoding="utf-8")

        logger.info("Exported summary to Obsidian: %s", file_path)
        return {"ok": True, "url": str(file_path)}

    @staticmethod
    def _format_tasks(tasks: list[dict]) -> str:
        """Format tasks as Obsidian checkbox list with subtask indentation."""
        lines = []
        # Separate parent tasks and subtasks
        parents = [t for t in tasks if not t.get("parent_task_id")]
        subtask_map: dict[int, list[dict]] = {}
        for t in tasks:
            pid = t.get("parent_task_id")
            if pid:
                subtask_map.setdefault(pid, []).append(t)

        for t in parents:
            checkbox = "x" if t.get("status") == "done" else " "
            lines.append(f"- [{checkbox}] {t['title']}")
            if t.get("description"):
                lines.append(f"  {t['description']}")
            for sub in subtask_map.get(t["id"], []):
                sub_checkbox = "x" if sub.get("status") == "done" else " "
                lines.append(f"  - [{sub_checkbox}] {sub['title']}")
                if sub.get("description"):
                    lines.append(f"    {sub['description']}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as a filename."""
        sanitized = re.sub(r'[<>:"/\\|?*]', "", name)
        sanitized = sanitized.strip(". ")
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip(". ")
        return sanitized or "untitled"

    @staticmethod
    def _build_frontmatter(
        title: str,
        tags: list[str] | None,
        recording_name: str | None,
        folder: str,
        duration_seconds: int | None,
        cost_data: list[dict] | None,
    ) -> str:
        lines = []
        lines.append(f"title: {title or 'Untitled'}")

        if tags:
            lines.append("tags:")
            for tag in tags:
                clean = tag.strip()
                if clean:
                    lines.append(f"  - {clean}")

        lines.append(f"source: agendino")

        if recording_name:
            lines.append(f"recording: {recording_name}")

        if folder and folder != "/":
            lines.append(f"folder: {folder}")

        if duration_seconds is not None:
            lines.append(f"duration_seconds: {duration_seconds}")

        if cost_data:
            total_cost = sum(c.get("cost_usd", 0) for c in cost_data)
            for c in cost_data:
                op = c.get("operation", "unknown")
                lines.append(f"{op}:")
                lines.append(f"  engine: {c.get('engine', 'unknown')}")
                if c.get("model"):
                    lines.append(f"  model: {c['model']}")
                lines.append(f"  cost_usd: {c.get('cost_usd', 0)}")
                if c.get("input_units"):
                    lines.append(f"  input_units: {c['input_units']}")
                if c.get("output_units"):
                    lines.append(f"  output_units: {c['output_units']}")
            lines.append(f"total_cost_usd: {round(total_cost, 6)}")

        return "\n".join(lines) + "\n"
