import json
import os
from datetime import datetime
from pathlib import Path

from .parquet_service import JOINT_NAMES

INFO_TEMPLATE = {
    "codebase_version": "v2.0",
    "robot_type": "SO-ARM101",
    "fps": 30,
    "features": {
        "observation.state": {"dtype": "float32", "shape": [6], "names": JOINT_NAMES},
        "action":            {"dtype": "float32", "shape": [6], "names": JOINT_NAMES},
    },
    "total_episodes": 0,
    "total_frames": 0,
    "total_successes": 0,
    "chunks_size": 1000,
    "splits": {"train": "0:0"},
}


def _atomic_write_json(path: Path, data: dict):
    """임시 파일에 쓴 후 rename — POSIX atomic 보장"""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


class MetadataService:
    def __init__(self):
        self._meta_dir: Path = None
        self._info: dict = {}

    def load_or_init(self, meta_dir: Path, camera_roles: dict, fps: int = 30) -> int:
        """
        세션 시작 시 호출. info.json 없으면 생성.
        반환: total_frames (ParquetWriter global_frame_offset용)
        """
        self._meta_dir = meta_dir
        meta_dir.mkdir(parents=True, exist_ok=True)

        info_path = meta_dir / "info.json"
        if info_path.exists():
            self._info = json.loads(info_path.read_text())
        else:
            self._info = dict(INFO_TEMPLATE)
            self._info["fps"] = fps
            # 카메라 역할별 video feature 추가
            for role in camera_roles:
                key = f"observation.images.{role}"
                self._info["features"][key] = {
                    "dtype": "video", "shape": [480, 640, 3],
                    "names": ["height", "width", "channels"]
                }
            _atomic_write_json(info_path, self._info)

        return self._info.get("total_frames", 0)

    def append_episode(
        self,
        episode_index: int,
        length: int,
        success: bool,
        language_instruction: str,
        chunk_index: int,
    ):
        """에피소드 완료 시 episodes.jsonl에 1줄 append + info.json 업데이트"""
        record = {
            "episode_index":        episode_index,
            "length":               length,
            "success":              success,
            "language_instruction": language_instruction,
            "chunk_index":          chunk_index,
            "timestamp":            datetime.utcnow().isoformat(),
        }
        jsonl_path = self._meta_dir / "episodes.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        self._info["total_episodes"] += 1
        self._info["total_frames"]   += length
        if success:
            self._info["total_successes"] += 1
        _atomic_write_json(self._meta_dir / "info.json", self._info)

    def finalize(self):
        """전체 수집 완료 시 splits 업데이트"""
        n = self._info["total_episodes"]
        self._info["splits"] = {"train": f"0:{n}"}
        _atomic_write_json(self._meta_dir / "info.json", self._info)
