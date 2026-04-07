import os

ALLOWED_AUDIO_EXTENSIONS = {".hda", ".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac", ".aac", ".wma"}


class LocalRecordingsRepository:
    def __init__(self, local_recordings_path):
        self._local_recordings_path = local_recordings_path
        os.makedirs(self._local_recordings_path, exist_ok=True)

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
        return os.path.isfile(os.path.join(self._local_recordings_path, filename))

    def get_path(self, filename: str) -> str:
        return os.path.join(self._local_recordings_path, filename)

    def get_file_size(self, filename: str) -> int | None:
        """Return file size in bytes, or None if file doesn't exist."""
        path = os.path.join(self._local_recordings_path, filename)
        if os.path.isfile(path):
            return os.path.getsize(path)
        return None

    def save(self, filename: str, data: bytes) -> str:
        path = os.path.join(self._local_recordings_path, filename)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def delete(self, filename: str) -> bool:
        path = os.path.join(self._local_recordings_path, filename)
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False
