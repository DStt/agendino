import sqlite3

from models.dto.CostMetadata import CostMetadata


class CostTrackingRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def save(self, recording_id: int | None, cost: CostMetadata, estimated: bool = False) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO cost_tracking
                   (recording_id, operation, engine, model, input_units, output_units, cost_usd, estimated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (recording_id, cost.operation, cost.engine, cost.model,
                 cost.input_units, cost.output_units, cost.cost_usd, 1 if estimated else 0),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_by_recording(self, recording_id: int) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cost_tracking WHERE recording_id = ? ORDER BY created_at",
                (recording_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_by_date_range(self, start: str, end: str) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cost_tracking WHERE created_at >= ? AND created_at <= ? ORDER BY created_at",
                (start, end),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_totals(self) -> dict:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT
                     COUNT(*) as total_operations,
                     COALESCE(SUM(cost_usd), 0) as total_cost,
                     COALESCE(SUM(CASE WHEN operation='transcription' THEN cost_usd ELSE 0 END), 0) as transcription_cost,
                     COALESCE(SUM(CASE WHEN operation='summarization' THEN cost_usd ELSE 0 END), 0) as summarization_cost,
                     COALESCE(SUM(CASE WHEN operation='task_generation' THEN cost_usd ELSE 0 END), 0) as task_generation_cost,
                     COALESCE(SUM(CASE WHEN operation='comparison' THEN cost_usd ELSE 0 END), 0) as comparison_cost
                """
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def get_by_engine(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT engine, operation,
                     COUNT(*) as count,
                     COALESCE(SUM(cost_usd), 0) as total_cost
                   FROM cost_tracking
                   GROUP BY engine, operation
                   ORDER BY engine, operation"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_daily_totals(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT DATE(created_at) as date,
                     COALESCE(SUM(cost_usd), 0) as total_cost,
                     COUNT(*) as operations
                   FROM cost_tracking
                   GROUP BY DATE(created_at)
                   ORDER BY date"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_per_recording_costs(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT
                     r.id as recording_id, r.name, r.folder,
                     MIN(ct.created_at) as first_cost_at,
                     COALESCE(SUM(CASE WHEN ct.operation='transcription' THEN ct.cost_usd ELSE 0 END), 0) as transcription_cost,
                     COALESCE(SUM(CASE WHEN ct.operation='summarization' THEN ct.cost_usd ELSE 0 END), 0) as summarization_cost,
                     COALESCE(SUM(ct.cost_usd), 0) as total_cost,
                     MAX(ct.estimated) as has_estimates
                   FROM recording r
                   JOIN cost_tracking ct ON ct.recording_id = r.id
                   GROUP BY r.id
                   ORDER BY total_cost DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_usage_counts(self) -> dict:
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT
                     COUNT(DISTINCT CASE WHEN operation='transcription' THEN recording_id END) as transcriptions,
                     COUNT(DISTINCT CASE WHEN operation='summarization' THEN recording_id END) as summarizations,
                     COUNT(DISTINCT CASE WHEN operation='task_generation' THEN recording_id END) as task_generations,
                     COUNT(DISTINCT CASE WHEN operation='rag_query' THEN id END) as rag_queries,
                     COUNT(DISTINCT CASE WHEN operation='comparison' THEN id END) as comparisons
                   FROM cost_tracking"""
            ).fetchone()
            return dict(row)
        finally:
            conn.close()
