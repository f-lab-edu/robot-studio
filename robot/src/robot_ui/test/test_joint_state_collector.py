"""
JointStateCollector 유닛 테스트 — ROS2 없이 실행 가능.
pytest robot/src/robot_ui/test/test_joint_state_collector.py
"""
import sys
import types
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# ROS2 stub — sensor_msgs, rclpy 없는 환경에서도 import 가능하게
# ---------------------------------------------------------------------------

def _make_ros_stubs():
    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs.msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs.msg.JointState = MagicMock

    rclpy = types.ModuleType("rclpy")
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = MagicMock

    sys.modules.setdefault("sensor_msgs", sensor_msgs)
    sys.modules.setdefault("sensor_msgs.msg", sensor_msgs.msg)
    sys.modules.setdefault("rclpy", rclpy)
    sys.modules.setdefault("rclpy.node", rclpy.node)


_make_ros_stubs()

# stub 등록 후 import
import importlib.util
_root = __import__("pathlib").Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location(
    "joint_state_collector",
    _root / "robot_ui/utils/joint_state_collector.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
JointStateCollector = _mod.JointStateCollector


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _make_collector() -> JointStateCollector:
    node = MagicMock()
    node.create_subscription.return_value = MagicMock()
    return JointStateCollector(node)


def _fill(collector: JointStateCollector, leader_data, follower_data):
    """버퍼에 직접 데이터 주입"""
    collector._leader_buf.extend(leader_data)
    collector._follower_buf.extend(follower_data)


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

class TestStartEpisode:
    def test_clears_buffers(self):
        c = _make_collector()
        _fill(c, [(0.0, [1.0] * 6)], [(0.0, [2.0] * 6)])
        c.start_episode()
        assert len(c._leader_buf) == 0
        assert len(c._follower_buf) == 0


class TestCallbacks:
    def test_on_leader_appends(self):
        c = _make_collector()
        msg = MagicMock()
        msg.position = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.99]  # 7개, 6개만 사용
        c._on_leader(msg)
        assert len(c._leader_buf) == 1
        _, pos = c._leader_buf[0]
        assert pos == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]

    def test_on_follower_appends(self):
        c = _make_collector()
        msg = MagicMock()
        msg.position = [1.0] * 7
        c._on_follower(msg)
        assert len(c._follower_buf) == 1
        _, pos = c._follower_buf[0]
        assert pos == [1.0] * 6


class TestAlignToFrames:
    def test_nearest_neighbor_basic(self):
        """플랜 명세 검증: 0.04→0.0, 0.09→0.1 에 nearest"""
        c = _make_collector()
        _fill(
            c,
            leader_data=[(0.0, [1.0] * 6), (0.1, [2.0] * 6)],
            follower_data=[(0.05, [3.0] * 6)],
        )
        result = c.align_to_frames([0.04, 0.09])

        assert result[0]["action"] == [1.0] * 6   # 0.04 → 0.0 더 가까움
        assert result[1]["action"] == [2.0] * 6   # 0.09 → 0.1 더 가까움
        assert result[0]["obs_state"] == [3.0] * 6
        assert result[1]["obs_state"] == [3.0] * 6

    def test_result_length_matches_frames(self):
        c = _make_collector()
        _fill(
            c,
            leader_data=[(i * 0.1, [float(i)] * 6) for i in range(5)],
            follower_data=[(i * 0.1, [float(i)] * 6) for i in range(5)],
        )
        result = c.align_to_frames([0.05, 0.15, 0.25])
        assert len(result) == 3

    def test_empty_frames_returns_empty(self):
        c = _make_collector()
        _fill(c, [(0.0, [1.0] * 6)], [(0.0, [1.0] * 6)])
        assert c.align_to_frames([]) == []

    def test_raises_if_no_leader_data(self):
        c = _make_collector()
        _fill(c, leader_data=[], follower_data=[(0.0, [1.0] * 6)])
        with pytest.raises(ValueError, match="/leader/joint_states"):
            c.align_to_frames([0.0])

    def test_raises_if_no_follower_data(self):
        c = _make_collector()
        _fill(c, leader_data=[(0.0, [1.0] * 6)], follower_data=[])
        with pytest.raises(ValueError, match="/follower/joint_states"):
            c.align_to_frames([0.0])

    def test_single_sample_always_selected(self):
        """샘플이 하나뿐이면 어떤 타임스탬프든 그 샘플을 반환"""
        c = _make_collector()
        _fill(c, [(99.0, [7.0] * 6)], [(99.0, [8.0] * 6)])
        result = c.align_to_frames([0.0, 50.0, 200.0])
        assert all(r["action"] == [7.0] * 6 for r in result)
        assert all(r["obs_state"] == [8.0] * 6 for r in result)


class TestDestroy:
    def test_destroy_calls_unsubscribe(self):
        node = MagicMock()
        sub_leader = MagicMock()
        sub_follower = MagicMock()
        node.create_subscription.side_effect = [sub_leader, sub_follower]

        c = JointStateCollector(node)
        c.destroy()

        node.destroy_subscription.assert_any_call(sub_leader)
        node.destroy_subscription.assert_any_call(sub_follower)
        assert node.destroy_subscription.call_count == 2
