from pathlib import Path


class SystemPromptsRepository:
    def __init__(self, prompts_path: str):
        self._prompts_dir = Path(prompts_path)

    def get_all(self) -> list[dict]:
        results = []
        if not self._prompts_dir.exists():
            return results

        for lang_dir in sorted(self._prompts_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            for category_dir in sorted(lang_dir.iterdir()):
                if not category_dir.is_dir():
                    continue
                results.extend(self._collect_prompts(lang_dir, category_dir))
        return results

    @staticmethod
    def _collect_prompts(lang_dir: Path, category_dir: Path) -> list[dict]:
        prompts = []
        for prompt_file in sorted(category_dir.iterdir()):
            if prompt_file.is_file() and prompt_file.suffix in (".txt", ".md"):
                prompt_id = f"{lang_dir.name}/{category_dir.name}/{prompt_file.stem}"
                label = f"{category_dir.name} / {prompt_file.stem}"
                prompts.append(
                    {
                        "id": prompt_id,
                        "label": label,
                        "language": lang_dir.name,
                        "category": category_dir.name,
                    }
                )
        return prompts

    def get_prompt_content(self, prompt_id: str) -> str | None:
        # Try .txt first, then .md
        for ext in (".txt", ".md"):
            prompt_path = self._prompts_dir / f"{prompt_id}{ext}"
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
        return None
