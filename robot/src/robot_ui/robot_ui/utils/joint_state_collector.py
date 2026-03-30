import time
from collections import deque
import numpy as np
from sensor_msgs.msg import JointState
from rclpy.node import Node

JOINT_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']


class JointStateCollector:
    """에피소드 단위 관절 데이터 수집 + 프레임 타임스탬프 정렬"""

    def __init__(self, ros_node: Node):
        self._node = ros_node
        self._leader_buf: deque = deque()    # (wall_time, positions[6])
        self._follower_buf: deque = deque()  # (wall_time, positions[6])

        self._sub_leader = ros_node.create_subscription(
            JointState, '/leader/joint_states', self._on_leader, 10
        )
        self._sub_follower = ros_node.create_subscription(
            JointState, '/follower/joint_states', self._on_follower, 10
        )

    def start_episode(self):
        """에피소드 시작 전 버퍼 초기화"""
        self._leader_buf.clear()
        self._follower_buf.clear()

    def _on_leader(self, msg: JointState):
        self._leader_buf.append((time.time(), list(msg.position[:6])))

    def _on_follower(self, msg: JointState):
        self._follower_buf.append((time.time(), list(msg.position[:6])))

    def align_to_frames(self, frame_timestamps: list[float]) -> list[dict]:
        """
        프레임 타임스탬프 목록에 관절 데이터를 nearest-neighbor 정렬.
        반환: [{"action": [6 floats], "obs_state": [6 floats]}, ...]
        leader/follower 데이터가 없으면 ValueError 발생.
        """
        if not self._leader_buf:
            raise ValueError("No leader joint data collected. Check /leader/joint_states topic.")
        if not self._follower_buf:
            raise ValueError("No follower joint data collected. Check /follower/joint_states topic.")

        leader_times   = np.array([t for t, _ in self._leader_buf])
        leader_pos     = [p for _, p in self._leader_buf]
        follower_times = np.array([t for t, _ in self._follower_buf])
        follower_pos   = [p for _, p in self._follower_buf]

        result = []
        for ts in frame_timestamps:
            action    = leader_pos[int(np.argmin(np.abs(leader_times - ts)))]
            obs_state = follower_pos[int(np.argmin(np.abs(follower_times - ts)))]
            result.append({"action": action, "obs_state": obs_state})

        return result

    def destroy(self):
        self._node.destroy_subscription(self._sub_leader)
        self._node.destroy_subscription(self._sub_follower)
