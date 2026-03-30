import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

JOINT_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']

SCHEMA = pa.schema([
    ("frame_index",          pa.int64()),
    ("episode_index",        pa.int64()),
    ("timestamp",            pa.float32()),
    ("index",                pa.int64()),           # 세션 전체 절대 프레임 번호
    ("observation.state",    pa.list_(pa.float32())),  # follower 위치
    ("action",               pa.list_(pa.float32())),  # leader 위치
    ("action_is_pad",        pa.bool_()),
    ("language_instruction", pa.string()),
    ("next.done",            pa.bool_()),
    ("next.reward",          pa.float32()),
    ("next.success",         pa.bool_()),
])


class ParquetWriter:
    def __init__(self, global_frame_offset: int = 0):
        """
        global_frame_offset: 세션 재시작 시 이어받을 info.json의 total_frames
        """
        self._offset = global_frame_offset

    def write(
        self,
        output_path: Path,
        episode_index: int,
        joint_records: list[dict],   # [{"action": [6], "obs_state": [6]}, ...]
        frame_timestamps: list[float],
        language_instruction: str,
        success: bool,
    ):
        n = min(len(joint_records), len(frame_timestamps))

        col = {
            "frame_index":          list(range(n)),
            "episode_index":        [episode_index] * n,
            "timestamp":            [float(t) for t in frame_timestamps[:n]],
            "index":                [self._offset + i for i in range(n)],
            "observation.state":    [rec["obs_state"] for rec in joint_records[:n]],
            "action":               [rec["action"]    for rec in joint_records[:n]],
            "action_is_pad":        [False] * n,
            "language_instruction": [language_instruction] * n,
            "next.done":            [i == n - 1 for i in range(n)],
            "next.reward":          [1.0 if (success and i == n - 1) else 0.0 for i in range(n)],
            "next.success":         [success if i == n - 1 else False for i in range(n)],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.table(col, schema=SCHEMA)
        pq.write_table(table, output_path)

        self._offset += n

    def get_global_offset(self) -> int:
        return self._offset
