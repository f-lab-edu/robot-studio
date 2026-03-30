"""
ParquetWriter 유닛 테스트 — ROS2 없이 실행 가능.
pytest src/robot_ui/test/test_parquet_service.py
"""
import importlib.util
from pathlib import Path

import pyarrow.parquet as pq
import pytest

# ---------------------------------------------------------------------------
# 직접 import (utils/__init__ 체인 우회)
# ---------------------------------------------------------------------------
_root = Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location(
    "parquet_service",
    _root / "robot_ui/services/parquet_service.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ParquetWriter = _mod.ParquetWriter
SCHEMA        = _mod.SCHEMA
JOINT_NAMES   = _mod.JOINT_NAMES


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_joint_records(n: int, action_val=1.0, obs_val=2.0) -> list[dict]:
    return [{"action": [action_val] * 6, "obs_state": [obs_val] * 6} for _ in range(n)]


def _make_timestamps(n: int, start=0.0, step=1/30) -> list[float]:
    return [start + i * step for i in range(n)]


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

class TestParquetWriterSchema:
    def test_output_file_created(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(5), _make_timestamps(5), "test", True)
        assert out.exists()

    def test_schema_matches(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(3), _make_timestamps(3), "test", True)
        table = pq.read_table(out)
        assert table.schema.equals(SCHEMA)

    def test_all_expected_columns_present(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(2), _make_timestamps(2), "test", True)
        table = pq.read_table(out)
        expected = {f.name for f in SCHEMA}
        assert set(table.schema.names) == expected


class TestParquetWriterRows:
    def test_row_count_equals_min_of_records_and_timestamps(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        # joint_records가 더 많을 때 → timestamps 기준
        w.write(out, 0, _make_joint_records(10), _make_timestamps(7), "test", True)
        table = pq.read_table(out)
        assert len(table) == 7

    def test_frame_index_is_sequential(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(5), _make_timestamps(5), "test", True)
        table = pq.read_table(out)
        assert table["frame_index"].to_pylist() == list(range(5))

    def test_episode_index_constant(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 3, _make_joint_records(4), _make_timestamps(4), "test", True)
        table = pq.read_table(out)
        assert all(v == 3 for v in table["episode_index"].to_pylist())


class TestParquetWriterDoneReward:
    def test_next_done_only_last_frame(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(5), _make_timestamps(5), "test", True)
        table = pq.read_table(out)
        done = table["next.done"].to_pylist()
        assert done[-1] is True
        assert all(v is False for v in done[:-1])

    def test_next_success_true_only_on_last_frame_when_success(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(4), _make_timestamps(4), "test", success=True)
        table = pq.read_table(out)
        success_col = table["next.success"].to_pylist()
        assert success_col[-1] is True
        assert all(v is False for v in success_col[:-1])

    def test_next_success_false_when_failure(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(4), _make_timestamps(4), "test", success=False)
        table = pq.read_table(out)
        assert all(v is False for v in table["next.success"].to_pylist())

    def test_next_reward_1_on_last_frame_when_success(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(3), _make_timestamps(3), "test", success=True)
        table = pq.read_table(out)
        reward = table["next.reward"].to_pylist()
        assert reward[-1] == pytest.approx(1.0)
        assert all(v == pytest.approx(0.0) for v in reward[:-1])

    def test_next_reward_0_on_all_when_failure(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(3), _make_timestamps(3), "test", success=False)
        table = pq.read_table(out)
        assert all(v == pytest.approx(0.0) for v in table["next.reward"].to_pylist())


class TestParquetWriterGlobalOffset:
    def test_index_starts_at_offset(self, tmp_path):
        w = ParquetWriter(global_frame_offset=100)
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(5), _make_timestamps(5), "test", True)
        table = pq.read_table(out)
        assert table["index"].to_pylist() == list(range(100, 105))

    def test_offset_advances_after_write(self, tmp_path):
        w = ParquetWriter()
        w.write(tmp_path / "ep0.parquet", 0, _make_joint_records(10), _make_timestamps(10), "test", True)
        assert w.get_global_offset() == 10
        w.write(tmp_path / "ep1.parquet", 1, _make_joint_records(5), _make_timestamps(5), "test", True)
        assert w.get_global_offset() == 15

    def test_index_continuous_across_episodes(self, tmp_path):
        w = ParquetWriter()
        w.write(tmp_path / "ep0.parquet", 0, _make_joint_records(3), _make_timestamps(3), "test", True)
        w.write(tmp_path / "ep1.parquet", 1, _make_joint_records(3), _make_timestamps(3), "test", True)
        t0 = pq.read_table(tmp_path / "ep0.parquet")
        t1 = pq.read_table(tmp_path / "ep1.parquet")
        assert t0["index"].to_pylist() == [0, 1, 2]
        assert t1["index"].to_pylist() == [3, 4, 5]


class TestParquetWriterJointData:
    def test_action_values_stored(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        records = [{"action": [float(i)] * 6, "obs_state": [0.0] * 6} for i in range(3)]
        w.write(out, 0, records, _make_timestamps(3), "test", True)
        table = pq.read_table(out)
        action_col = table["action"].to_pylist()
        assert action_col[0] == pytest.approx([0.0] * 6)
        assert action_col[1] == pytest.approx([1.0] * 6)
        assert action_col[2] == pytest.approx([2.0] * 6)

    def test_observation_state_values_stored(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        records = [{"action": [0.0] * 6, "obs_state": [float(i)] * 6} for i in range(3)]
        w.write(out, 0, records, _make_timestamps(3), "test", True)
        table = pq.read_table(out)
        obs_col = table["observation.state"].to_pylist()
        assert obs_col[2] == pytest.approx([2.0] * 6)

    def test_language_instruction_stored(self, tmp_path):
        w = ParquetWriter()
        out = tmp_path / "ep.parquet"
        w.write(out, 0, _make_joint_records(2), _make_timestamps(2), "pick the red block", True)
        table = pq.read_table(out)
        assert all(v == "pick the red block" for v in table["language_instruction"].to_pylist())
