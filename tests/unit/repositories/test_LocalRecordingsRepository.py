import os
import tempfile

import pytest

from repositories.LocalRecordingsRepository import LocalRecordingsRepository


class TestLocalRecordingsRepository:
    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return str(tmp_path / "recordings")

    @pytest.fixture
    def repo(self, tmp_dir):
        return LocalRecordingsRepository(tmp_dir)

    def test_creates_directory_on_init(self, tmp_dir):
        assert not os.path.exists(tmp_dir)
        LocalRecordingsRepository(tmp_dir)
        assert os.path.isdir(tmp_dir)

    def test_get_all_empty(self, repo):
        assert repo.get_all() == []

    def test_save_and_get_all(self, repo):
        repo.save("test1.hda", b"data1")
        repo.save("test2.hda", b"data2")
        repo.save("notes.txt", b"text")

        result = repo.get_all()
        assert sorted(result) == ["test1.hda", "test2.hda"]

    def test_get_all_custom_extension(self, repo):
        repo.save("notes.txt", b"text")
        repo.save("audio.hda", b"audio")

        assert repo.get_all(ext=".txt") == ["notes.txt"]

    def test_exists_true(self, repo):
        repo.save("file.hda", b"content")
        assert repo.exists("file.hda") is True

    def test_exists_false(self, repo):
        assert repo.exists("nonexistent.hda") is False

    def test_get_path(self, repo, tmp_dir):
        expected = os.path.join(tmp_dir, "test.hda")
        assert repo.get_path("test.hda") == expected

    def test_save_returns_path(self, repo, tmp_dir):
        path = repo.save("recording.hda", b"\x00\x01\x02")
        assert path == os.path.join(tmp_dir, "recording.hda")
        assert os.path.isfile(path)

    def test_save_binary_content(self, repo):
        data = bytes(range(256))
        repo.save("binary.hda", data)
        path = repo.get_path("binary.hda")
        with open(path, "rb") as f:
            assert f.read() == data

    def test_delete_existing_file(self, repo):
        repo.save("to_delete.hda", b"data")
        assert repo.exists("to_delete.hda")

        result = repo.delete("to_delete.hda")
        assert result is True
        assert repo.exists("to_delete.hda") is False

    def test_delete_nonexistent_file(self, repo):
        result = repo.delete("ghost.hda")
        assert result is False

    def test_rejects_path_traversal_read(self, repo, tmp_dir):
        outside = os.path.join(os.path.dirname(tmp_dir), "secret.mp3")
        with open(outside, "wb") as f:
            f.write(b"secret")

        assert repo.exists("../secret.mp3") is False
        assert repo.get_file_size("../secret.mp3") is None
        assert repo.delete("../secret.mp3") is False
        assert os.path.isfile(outside)

    @pytest.mark.parametrize("unsafe", ["../evil.mp3", "../../etc/passwd", "/etc/passwd", "a/b.mp3", "..\\evil.mp3"])
    def test_get_path_rejects_unsafe_names(self, repo, unsafe):
        with pytest.raises(ValueError):
            repo.get_path(unsafe)

    def test_save_rejects_traversal(self, repo):
        with pytest.raises(ValueError):
            repo.save("../evil.mp3", b"x")

    def test_rejects_absolute_path(self, repo):
        assert repo.exists("/etc/passwd") is False
