import os
import uuid
from datetime import datetime
from random import randint

import pytest

from models.DBRecording import DBRecording
from repositories.SqliteDBRepository import SqliteDBRepository


class TestIntegrationSqliteDBRepository:

    @pytest.fixture
    def init_path(self):
        path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(path, "../../../settings/db_init.sql")

    @pytest.fixture
    def db_path(self):
        path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(path, "../../../settings/")

    @pytest.fixture
    def db(self, db_path, init_path):
        return SqliteDBRepository("test.db", db_path, init_path)

    @pytest.fixture(autouse=True)
    def reset_db(self, db, init_path):
        conn = db._connect()
        try:
            # Disable FK enforcement while tearing down tables to avoid dependency-order issues.
            conn.execute("PRAGMA foreign_keys = OFF")
            result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = result.fetchall()

            for (table_name,) in tables:
                if table_name == "sqlite_sequence":
                    continue
                conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')

            conn.commit()
        finally:
            conn.close()

        db._initialize_db(init_path)
        db._ensure_recording_columns()
        db._ensure_recording_indexes()

    def test_it_can_add_a_file(self, db, init_path):
        db_file = DBRecording(
            id=randint(1, 100),
            name=f"file_{randint(1, 100)}.hda",
            label=f"Label {uuid.uuid4()}",
            duration=randint(1, 100),
            created_at=datetime.now(),
        )
        id = db.insert_recording(db_file)

        db_files = db.get_recordings()
        assert len(db_files) == 1
        assert db_files[0].name == db_file.name
        assert db_files[0].label == db_file.label
        assert db_files[0].duration == db_file.duration
        assert db_files[0].created_at == db_file.created_at
        assert db_files[0].id == id
