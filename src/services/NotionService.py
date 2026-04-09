import re
import httpx


class NotionService:
    API_BASE = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, api_key: str, parent_page_id: str):
        self._api_key = api_key
        self._parent_page_id = self._normalize_id(parent_page_id)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._parent_page_id)

    @staticmethod
    def _normalize_id(raw: str) -> str:
        if not raw:
            return ""
        raw = raw.split("?")[0].strip().rstrip("/")
        cleaned = raw.replace("-", "").lower()
        m = re.search(r"[0-9a-f]{32}", cleaned)
        if m:
            return m.group()
        parts = raw.split("-")
        candidate = parts[-1]
        if re.fullmatch(r"[0-9a-f]{32}", candidate):
            return candidate
        return raw

    def publish_summary(
        self,
        title: str,
        summary_markdown: str,
        tags: list[str] | None = None,
        recording_name: str | None = None,
    ) -> dict:
        if not self.is_configured:
            return {"ok": False, "error": "Notion is not configured (missing API key or page ID)"}

        children: list[dict] = []

        meta_parts: list[str] = []
        if recording_name:
            meta_parts.append(f"📁 {recording_name}")
        if tags:
            clean = [t.strip() for t in tags if t.strip()]
            if clean:
                meta_parts.append(f"🏷️ {', '.join(clean)}")
        if meta_parts:
            children.append(self._callout_block(" - ".join(meta_parts)))
            children.append(self._divider_block())

        children.extend(self._markdown_to_blocks(summary_markdown))

        payload = {
            "parent": {"page_id": self._parent_page_id},
            "properties": {
                "title": [{"text": {"content": title or "Untitled summary"}}],
            },
            "children": children[:100],
        }

        try:
            resp = httpx.post(
                f"{self.API_BASE}/pages",
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                page_url = data.get("url", "")
                page_id = data.get("id", "")

                if len(children) > 100:
                    self._append_blocks(page_id, children[100:])

                return {"ok": True, "url": page_url}
            else:
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                msg = body.get("message", resp.text[:300])
                return {"ok": False, "error": f"Notion API {resp.status_code}: {msg}"}
        except httpx.HTTPError as exc:
            return {"ok": False, "error": f"Notion request failed: {exc}"}

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _append_blocks(self, page_id: str, blocks: list[dict]) -> None:
        for i in range(0, len(blocks), 100):
            chunk = blocks[i : i + 100]
            try:
                httpx.patch(
                    f"{self.API_BASE}/blocks/{page_id}/children",
                    json={"children": chunk},
                    headers=self._headers(),
                    timeout=30,
                )
            except httpx.HTTPError:
                pass

    @staticmethod
    def _callout_block(text: str) -> dict:
        return {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": text}}],
                "icon": {"type": "emoji", "emoji": "📋"},
            },
        }

    @staticmethod
    def _divider_block() -> dict:
        return {"object": "block", "type": "divider", "divider": {}}

    @staticmethod
    def _rich_text(text: str, bold: bool = False, italic: bool = False) -> dict:
        annotations = {}
        if bold:
            annotations["bold"] = True
        if italic:
            annotations["italic"] = True
        rt: dict = {"type": "text", "text": {"content": text}}
        if annotations:
            rt["annotations"] = annotations
        return rt

    @classmethod
    def _parse_inline(cls, line: str) -> list[dict]:
        segments: list[dict] = []
        pattern = re.compile(r"(\*\*(.+?)\*\*|\*(.+?)\*|([^*]+))")
        for m in pattern.finditer(line):
            if m.group(2) is not None:
                segments.append(cls._rich_text(m.group(2), bold=True))
            elif m.group(3) is not None:
                segments.append(cls._rich_text(m.group(3), italic=True))
            elif m.group(4) is not None:
                segments.append(cls._rich_text(m.group(4)))
        return segments or [cls._rich_text(line)]

    @classmethod
    def _markdown_to_blocks(cls, md: str) -> list[dict]:
        blocks: list[dict] = []
        lines = md.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            if stripped.startswith("### "):
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {"rich_text": cls._parse_inline(stripped[4:])},
                    }
                )
            elif stripped.startswith("## "):
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {"rich_text": cls._parse_inline(stripped[3:])},
                    }
                )
            elif stripped.startswith("# "):
                blocks.append(
                    {
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {"rich_text": cls._parse_inline(stripped[2:])},
                    }
                )
            elif stripped.startswith("- ") or stripped.startswith("* "):
                blocks.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": cls._parse_inline(stripped[2:])},
                    }
                )
            elif re.match(r"^\d+\.\s", stripped):
                text = re.sub(r"^\d+\.\s", "", stripped)
                blocks.append(
                    {
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {"rich_text": cls._parse_inline(text)},
                    }
                )
            else:
                blocks.append(
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": cls._parse_inline(stripped)},
                    }
                )

            i += 1

        return blocks
