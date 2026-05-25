import os
import uuid
from datetime import datetime
from random import randint

import pytest

from models.DBRecording import DBRecording
from repositories.SqliteDBRepository import SqliteDBRepository


class TestSqliteDBRepository:

    @pytest.fixture
    def init_path(self):
        path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(path, "../../../settings/db_init.sql")

    @pytest.fixture
    def db(self, tmp_path, init_path):
        return SqliteDBRepository("test_unit.db", str(tmp_path), init_path)

    @pytest.fixture
    def sample_recording(self):
        return DBRecording(
            id=None,
            name=f"2026Mar27-094938-Wip{randint(1, 99):02d}",
            label="Test Recording",
            duration=120,
            created_at=datetime(2026, 3, 27, 9, 49, 38),
        )

    def test_insert_and_get_recordings(self, db, sample_recording):
        row_id = db.insert_recording(sample_recording)
        assert row_id is not None

        recordings = db.get_recordings()
        assert len(recordings) == 1
        assert recordings[0].name == sample_recording.name
        assert recordings[0].label == sample_recording.label
        assert recordings[0].duration == sample_recording.duration

    def test_get_recording_by_name(self, db, sample_recording):
        db.insert_recording(sample_recording)

        found = db.get_recording_by_name(sample_recording.name)
        assert found is not None
        assert found.name == sample_recording.name

    def test_get_recording_by_name_not_found(self, db):
        result = db.get_recording_by_name("nonexistent")
        assert result is None

    def test_save_and_get_transcript(self, db, sample_recording):
        db.insert_recording(sample_recording)
        assert db.get_transcript(sample_recording.name) is None

        db.save_transcript(sample_recording.name, "Hello, this is a transcript.")
        transcript = db.get_transcript(sample_recording.name)
        assert transcript == "Hello, this is a transcript."

    def test_update_transcript(self, db, sample_recording):
        db.insert_recording(sample_recording)
        db.save_transcript(sample_recording.name, "Before")

        updated = db.update_transcript(sample_recording.name, "After")
        assert updated is True
        assert db.get_transcript(sample_recording.name) == "After"

    def test_update_transcript_not_found(self, db):
        updated = db.update_transcript("ghost", "text")
        assert updated is False

    def test_get_transcript_not_found(self, db):
        result = db.get_transcript("nonexistent")
        assert result is None

    def test_save_and_get_summary(self, db, sample_recording):
        db.insert_recording(sample_recording)
        assert db.get_summary(sample_recording.name) is None

        db.save_summary(sample_recording.name, "# Summary\nThis is a test.")
        summary = db.get_summary(sample_recording.name)
        assert summary == "# Summary\nThis is a test."

    def test_get_summary_not_found(self, db):
        result = db.get_summary("nonexistent")
        assert result is None

    def test_save_summarization_result(self, db, sample_recording):
        db.insert_recording(sample_recording)

        db.save_summarization_result(
            sample_recording.name,
            summary="Full summary text",
            title="Meeting Notes",
            tags="meeting,notes,work",
        )

        rec = db.get_recording_by_name(sample_recording.name)
        assert rec.summary == "Full summary text"
        assert rec.title == "Meeting Notes"
        assert rec.tags == "meeting,notes,work"
        # label should also be updated to the title
        assert rec.label == "Meeting Notes"

    def test_update_title_and_tags(self, db, sample_recording):
        db.insert_recording(sample_recording)

        db.update_title_and_tags(sample_recording.name, "New Title", "tag1,tag2")

        rec = db.get_recording_by_name(sample_recording.name)
        assert rec.title == "New Title"
        assert rec.tags == "tag1,tag2"
        assert rec.label == "New Title"

    def test_update_summary_content(self, db, sample_recording):
        db.insert_recording(sample_recording)
        saved = db.save_summarization_result(
            sample_recording.name,
            summary="Old summary",
            title="Meeting Notes",
            tags="meeting,notes,work",
        )

        updated = db.update_summary_content(saved.id, "New summary")
        assert updated is not None
        assert updated.summary == "New summary"

    def test_update_summary_content_not_found(self, db):
        updated = db.update_summary_content(999999, "New summary")
        assert updated is None

    def test_delete_recording(self, db, sample_recording):
        db.insert_recording(sample_recording)
        assert db.get_recording_by_name(sample_recording.name) is not None

        result = db.delete_recording(sample_recording.name)
        assert result is True
        assert db.get_recording_by_name(sample_recording.name) is None

    def test_delete_recording_not_found(self, db):
        result = db.delete_recording("nonexistent")
        assert result is False

    def test_save_notion_url(self, db, sample_recording):
        db.insert_recording(sample_recording)

        db.save_notion_url(sample_recording.name, "https://notion.so/page123")

        rec = db.get_recording_by_name(sample_recording.name)
        assert rec.notion_url == "https://notion.so/page123"

    def test_multiple_recordings(self, db):
        for i in range(5):
            rec = DBRecording(
                id=None,
                name=f"rec_{i}",
                label=f"Recording {i}",
                duration=i * 60,
                created_at=datetime(2026, 4, 1),
            )
            db.insert_recording(rec)

        all_recs = db.get_recordings()
        assert len(all_recs) == 5

    def test_migration_on_existing_db(self, tmp_path, init_path):
        """Creating a repo twice on the same db should trigger migration path without error."""
        db1 = SqliteDBRepository("migrate_test.db", str(tmp_path), init_path)
        rec = DBRecording(id=None, name="test", label="Test", duration=10, created_at=datetime.now())
        db1.insert_recording(rec)

        # Second instantiation triggers _migrate_db instead of _initialize_db
        db2 = SqliteDBRepository("migrate_test.db", str(tmp_path), init_path)
        recordings = db2.get_recordings()
        assert len(recordings) == 1

    def test_create_collection(self, db):
        collection = db.create_collection("AI Strategy", "Strategic AI conversations")

        assert collection["id"] is not None
        assert collection["name"] == "AI Strategy"
        assert collection["description"] == "Strategic AI conversations"
        assert collection["count"] == 0

    def test_create_collection_reuses_existing_name_case_insensitive(self, db):
        first = db.create_collection("Features")
        second = db.create_collection("features")

        assert second["id"] == first["id"]
        assert second["created"] is False

    def test_add_and_remove_recording_collection(self, db, sample_recording):
        db.insert_recording(sample_recording)
        collection = db.create_collection("Catch-Up")

        added = db.add_recording_to_collection(sample_recording.name, collection["id"])
        assert added is True

        collections = db.get_recording_collections(sample_recording.name)
        assert [c["name"] for c in collections] == ["Catch-Up"]

        counts = db.get_collections_with_counts()
        assert counts[0]["count"] == 1

        removed = db.remove_recording_from_collection(sample_recording.name, collection["id"])
        assert removed is True
        assert db.get_recording_collections(sample_recording.name) == []

    def test_many_to_many_collection_membership(self, db):
        rec_a = DBRecording(id=None, name="rec-a", label="Rec A", duration=10, created_at=datetime.now())
        rec_b = DBRecording(id=None, name="rec-b", label="Rec B", duration=20, created_at=datetime.now())
        db.insert_recording(rec_a)
        db.insert_recording(rec_b)
        strategy = db.create_collection("AI Strategy")
        podcast = db.create_collection("Podcast Ideas")

        db.add_recording_to_collection("rec-a", strategy["id"])
        db.add_recording_to_collection("rec-a", podcast["id"])
        db.add_recording_to_collection("rec-b", strategy["id"])

        rec_a_collections = db.get_recording_collections("rec-a")
        assert {c["name"] for c in rec_a_collections} == {"AI Strategy", "Podcast Ideas"}

        counts = {c["name"]: c["count"] for c in db.get_collections_with_counts()}
        assert counts["AI Strategy"] == 2
        assert counts["Podcast Ideas"] == 1

    def test_set_recording_collections_replaces_membership(self, db, sample_recording):
        db.insert_recording(sample_recording)
        first = db.create_collection("Leadership")
        second = db.create_collection("Audience Strategy")

        updated = db.set_recording_collections(sample_recording.name, [first["id"], second["id"]])
        assert updated is True
        assert {c["name"] for c in db.get_recording_collections(sample_recording.name)} == {
            "Leadership",
            "Audience Strategy",
        }

        db.set_recording_collections(sample_recording.name, [second["id"]])
        assert [c["name"] for c in db.get_recording_collections(sample_recording.name)] == ["Audience Strategy"]

    def test_recording_collections_map(self, db, sample_recording):
        db.insert_recording(sample_recording)
        collection = db.create_collection("Editorial Workflows")
        db.add_recording_to_collection(sample_recording.name, collection["id"])

        mapping = db.get_recording_collections_map()
        assert mapping[sample_recording.name][0]["name"] == "Editorial Workflows"
