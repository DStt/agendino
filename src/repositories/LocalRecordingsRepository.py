import os

ALLOWED_AUDIO_EXTENSIONS = {".hda", ".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".aac", ".wma"}


class UnsafeFilenameError(ValueError):
    """Raised when a filename would escape the recordings directory."""


def is_safe_filename(filename: str) -> bool:
    """Return True when *filename* is a plain basename with no traversal."""
    if not isinstance(filename, str) or not filename or "\x00" in filename:
        return False
    if filename in (".", "..") or os.path.isabs(filename):
        return False
    if os.path.basename(filename) != filename or "/" in filename or "\\" in filename:
        return False
    return True


class LocalRecordingsRepository:
    def __init__(self, local_recordings_path):
        # realpath so the containment check below is not fooled by symlinks.
        self._local_recordings_path = os.path.realpath(local_recordings_path)
        os.makedirs(self._local_recordings_path, exist_ok=True)

    def _resolve(self, filename: str) -> str:
        """Resolve *filename* inside the recordings directory or raise."""
        if not is_safe_filename(filename):
            raise UnsafeFilenameError(f"Unsafe filename: {filename!r}")
        path = os.path.realpath(os.path.join(self._local_recordings_path, filename))
        if os.path.commonpath([self._local_recordings_path, path]) != self._local_recordings_path:
            raise UnsafeFilenameError(f"Unsafe filename: {filename!r}")
        return path

    def get_all(self, ext: str | None = None) -> list:
        """Return local recording filenames.

        If *ext* is given only files with that extension are returned.
        Otherwise all files with a known audio extension are returned.
        """
        files = []
        for file in os.listdir(self._local_recordings_path):
            if ext is not None:
                if file.endswith(ext):
                    files.append(file)
            else:
                _, file_ext = os.path.splitext(file)
                if file_ext.lower() in ALLOWED_AUDIO_EXTENSIONS:
                    files.append(file)
        return files

    def exists(self, filename: str) -> bool:
        try:
            return os.path.isfile(self._resolve(filename))
        except UnsafeFilenameError:
            return False

    def get_path(self, filename: str) -> str:
        return self._resolve(filename)

    def get_file_size(self, filename: str) -> int | None:
        """Return file size in bytes, or None if file doesn't exist."""
        try:
            path = self._resolve(filename)
        except UnsafeFilenameError:
            return None
        if os.path.isfile(path):
            return os.path.getsize(path)
        return None

    def save(self, filename: str, data: bytes) -> str:
        path = self._resolve(filename)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def delete(self, filename: str) -> bool:
        try:
            path = self._resolve(filename)
        except UnsafeFilenameError:
            return False
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False
