"""
MetadataService 유닛 테스트 — ROS2 없이 실행 가능.
pytest src/robot_ui/test/test_metadata_service.py
"""
import importlib.util
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 직접 import (utils/__init__ 체인 우회)
# ---------------------------------------------------------------------------
_root = Path(__file__).parents[1]


def _load_module(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, _root / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# parquet_service가 JOINT_NAMES를 export하므로 먼저 로드
_parquet_mod = _load_module("parquet_service", "robot_ui/services/parquet_service.py")

# metadata_service는 .parquet_service를 relative import — sys.modules에 등록 후 로드
import sys
sys.modules.setdefault("parquet_service", _parquet_mod)

# metadata_service의 relative import를 우회하기 위해 parquet_service를 패치
import importlib
_meta_path = _root / "robot_ui/services/metadata_service.py"
_meta_src = _meta_path.read_text().replace(
    "from .parquet_service import JOINT_NAMES",
    "from parquet_service import JOINT_NAMES",
)
_meta_spec = importlib.util.spec_from_loader("metadata_service", loader=None)
_meta_mod = importlib.util.module_from_spec(
    importlib.util.spec_from_file_location("metadata_service", _meta_path)
)
exec(compile(_meta_src, str(_meta_path), "exec"), _meta_mod.__dict__)

MetadataService = _meta_mod.MetadataService
_atomic_write_json = _meta_mod._atomic_write_json
INFO_TEMPLATE = _meta_mod.INFO_TEMPLATE


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_service(tmp_path: Path, camera_roles=None, fps=30) -> tuple:
    if camera_roles is None:
        camera_roles = {"top": "/camera_0/image_raw"}
    svc = MetadataService()
    offset = svc.load_or_init(tmp_path / "meta", camera_roles, fps)
    return svc, offset


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

class TestLoadOrInit:
    def test_creates_info_json_on_first_call(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        assert (tmp_path / "meta" / "info.json").exists()

    def test_returns_zero_offset_on_new_session(self, tmp_path):
        _, offset = _make_service(tmp_path)
        assert offset == 0

    def test_info_json_has_required_fields(self, tmp_path):
        _make_service(tmp_path)
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        for key in ("codebase_version", "robot_type", "fps", "features",
                    "total_episodes", "total_frames", "total_successes", "splits"):
            assert key in info

    def test_camera_roles_added_to_features(self, tmp_path):
        _make_service(tmp_path, camera_roles={"top": "/cam0", "wrist": "/cam2"})
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert "observation.images.top" in info["features"]
        assert "observation.images.wrist" in info["features"]

    def test_fps_stored_correctly(self, tmp_path):
        _make_service(tmp_path, fps=15)
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert info["fps"] == 15

    def test_loads_existing_info_json(self, tmp_path):
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        existing = dict(INFO_TEMPLATE)
        existing["total_frames"] = 999
        existing["total_episodes"] = 5
        (meta_dir / "info.json").write_text(json.dumps(existing))

        svc, offset = _make_service(tmp_path)
        assert offset == 999

    def test_no_tmp_file_left_after_init(self, tmp_path):
        _make_service(tmp_path)
        assert not (tmp_path / "meta" / "info.tmp").exists()


class TestAppendEpisode:
    def test_episodes_jsonl_created(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 300, True, "pick block", 0)
        assert (tmp_path / "meta" / "episodes.jsonl").exists()

    def test_jsonl_line_count_matches_episodes(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        svc.append_episode(1, 120, False, "task", 0)
        svc.append_episode(2, 90, True, "task", 0)
        lines = (tmp_path / "meta" / "episodes.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3

    def test_jsonl_record_fields(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 300, True, "pick block", 0)
        record = json.loads(
            (tmp_path / "meta" / "episodes.jsonl").read_text().strip()
        )
        assert record["episode_index"] == 0
        assert record["length"] == 300
        assert record["success"] is True
        assert record["language_instruction"] == "pick block"
        assert record["chunk_index"] == 0
        assert "timestamp" in record

    def test_info_json_total_episodes_increments(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        svc.append_episode(1, 100, True, "task", 0)
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert info["total_episodes"] == 2

    def test_info_json_total_frames_accumulates(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        svc.append_episode(1, 200, True, "task", 0)
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert info["total_frames"] == 300

    def test_total_successes_counts_only_success(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        svc.append_episode(1, 100, False, "task", 0)
        svc.append_episode(2, 100, True, "task", 0)
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert info["total_successes"] == 2

    def test_no_tmp_file_left_after_append(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        assert not (tmp_path / "meta" / "info.tmp").exists()

    def test_append_is_idempotent_on_file(self, tmp_path):
        """각 호출이 전체 파일을 덮어쓰지 않고 1줄만 추가하는지 확인"""
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        first_line = (tmp_path / "meta" / "episodes.jsonl").read_text().splitlines()[0]
        svc.append_episode(1, 200, False, "task", 0)
        lines = (tmp_path / "meta" / "episodes.jsonl").read_text().splitlines()
        assert lines[0] == first_line  # 첫 줄이 변경되지 않음
        assert len(lines) == 2


class TestFinalize:
    def test_splits_updated_to_train_range(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.append_episode(0, 100, True, "task", 0)
        svc.append_episode(1, 100, True, "task", 0)
        svc.finalize()
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert info["splits"] == {"train": "0:2"}

    def test_finalize_zero_episodes(self, tmp_path):
        svc, _ = _make_service(tmp_path)
        svc.finalize()
        info = json.loads((tmp_path / "meta" / "info.json").read_text())
        assert info["splits"] == {"train": "0:0"}


class TestAtomicWrite:
    def test_atomic_write_creates_file(self, tmp_path):
        path = tmp_path / "test.json"
        _atomic_write_json(path, {"key": "value"})
        assert path.exists()
        assert json.loads(path.read_text()) == {"key": "value"}

    def test_atomic_write_no_tmp_file_left(self, tmp_path):
        path = tmp_path / "test.json"
        _atomic_write_json(path, {})
        assert not (tmp_path / "test.tmp").exists()
