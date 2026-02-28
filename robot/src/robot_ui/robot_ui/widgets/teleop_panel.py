import threading

import serial.tools.list_ports
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QProgressBar, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QObject

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, String

from robot_driver.leader_arm_node import LeaderArmNode
from robot_driver.follower_arm_node import FollowerArmNode
from robot_driver.teleop_node import TeleopNode

JOINT_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']
POS_MIN = 0
POS_MAX = 4095

_LED_STYLE = {
    'connected':    'color: #4ec9b0;',
    'disconnected': 'color: #f48771;',
    'connecting':   'color: #dcdcaa;',
    'idle':         'color: #858585;',
}


# ─── ROS2 → Qt 시그널 ────────────────────────────────────────────────────────

class TeleopSignals(QObject):
    leader_joints_received   = Signal(list)
    follower_joints_received = Signal(list)
    leader_status_changed    = Signal(str)
    follower_status_changed  = Signal(str)
    teleop_status_changed    = Signal(str)


# ─── UI 전용 ROS2 노드 (상태 구독 + 명령 퍼블리시) ────────────────────────────

class TeleopUINode(Node):
    def __init__(self, signals: TeleopSignals):
        super().__init__('teleop_ui_node')
        self._signals = signals

        self.create_subscription(JointState, '/leader/joint_states',        self._on_leader_joints,   10)
        self.create_subscription(JointState, '/follower/joint_states',      self._on_follower_joints, 10)
        self.create_subscription(String,     '/leader/connection_status',   self._on_leader_status,   10)
        self.create_subscription(String,     '/follower/connection_status', self._on_follower_status, 10)
        self.create_subscription(String,     '/teleop/status',              self._on_teleop_status,   10)

        self._teleop_pub = self.create_publisher(Bool, '/teleop/command', 10)

    def _on_leader_joints(self, msg: JointState):
        self._signals.leader_joints_received.emit(list(msg.position))

    def _on_follower_joints(self, msg: JointState):
        self._signals.follower_joints_received.emit(list(msg.position))

    def _on_leader_status(self, msg: String):
        self._signals.leader_status_changed.emit(msg.data)

    def _on_follower_status(self, msg: String):
        self._signals.follower_status_changed.emit(msg.data)

    def _on_teleop_status(self, msg: String):
        self._signals.teleop_status_changed.emit(msg.data)

    def send_teleop_command(self, active: bool):
        self._teleop_pub.publish(Bool(data=active))


# ─── 암 연결 위젯 ─────────────────────────────────────────────────────────────

class ArmConnectionWidget(QGroupBox):
    connect_clicked = Signal(str)  # 선택된 포트 device 문자열

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        """)
        self._setup_ui()
        self._refresh_ports()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(8)

        self._led = QLabel('●')
        self._led.setStyleSheet(_LED_STYLE['idle'])
        self._led.setFixedWidth(14)
        layout.addWidget(self._led)

        self._status_label = QLabel('대기')
        self._status_label.setStyleSheet('color: #858585; font-size: 11px;')
        self._status_label.setFixedWidth(80)
        layout.addWidget(self._status_label)

        self._combo = QComboBox()
        self._combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px 8px;
                color: #cccccc;
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #3c3c3c;
                color: #cccccc;
                selection-background-color: #094771;
            }
        """)
        layout.addWidget(self._combo, 1)

        refresh_btn = QPushButton('↺')
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip('포트 목록 새로고침')
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 3px;
                color: #cccccc;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #505050; }
        """)
        refresh_btn.clicked.connect(self._refresh_ports)
        layout.addWidget(refresh_btn)

        self._connect_btn = QPushButton('연결')
        self._connect_btn.setFixedHeight(28)
        self._connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 16px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:disabled { background-color: #3c3c3c; color: #555; }
        """)
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self._connect_btn)

    def _refresh_ports(self):
        self._combo.clear()
        usb_ports = [p for p in serial.tools.list_ports.comports() if '/dev/ttyS' not in p.device]
        for p in usb_ports:
            self._combo.addItem(f'{p.device} — {p.description}', p.device)
        if self._combo.count() == 0:
            self._combo.addItem('포트 없음', '')

    def _on_connect_clicked(self):
        port = self._combo.currentData()
        if not port:
            return
        self.set_connecting()
        self.connect_clicked.emit(port)

    def set_connecting(self):
        self._led.setStyleSheet(_LED_STYLE['connecting'])
        self._status_label.setText('연결 중...')
        self._connect_btn.setEnabled(False)
        self._combo.setEnabled(False)

    def set_status(self, status: str):
        if status == 'connected':
            self._led.setStyleSheet(_LED_STYLE['connected'])
            self._status_label.setText('연결됨')
            self._connect_btn.setEnabled(False)
            self._combo.setEnabled(False)
        else:
            self._led.setStyleSheet(_LED_STYLE['disconnected'])
            self._status_label.setText('연결 끊김')
            self._connect_btn.setEnabled(True)
            self._combo.setEnabled(True)


# ─── 관절 상태 행 ──────────────────────────────────────────────────────────────

class JointStateRow(QWidget):
    def __init__(self, joint_name: str, parent=None):
        super().__init__(parent)
        self._setup_ui(joint_name)

    def _setup_ui(self, joint_name: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        name_label = QLabel(joint_name)
        name_label.setFixedWidth(110)
        name_label.setStyleSheet('color: #cccccc; font-size: 12px;')
        layout.addWidget(name_label)

        self._leader_bar = QProgressBar()
        self._leader_bar.setRange(POS_MIN, POS_MAX)
        self._leader_bar.setValue(2048)
        self._leader_bar.setFixedHeight(14)
        self._leader_bar.setTextVisible(False)
        self._leader_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #3c3c3c; border-radius: 3px; background-color: #2d2d2d; }
            QProgressBar::chunk { background-color: #264f78; border-radius: 2px; }
        """)
        layout.addWidget(self._leader_bar, 1)

        self._leader_val = QLabel('2048')
        self._leader_val.setFixedWidth(38)
        self._leader_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._leader_val.setStyleSheet('color: #9cdcfe; font-size: 11px; font-family: monospace;')
        layout.addWidget(self._leader_val)

        sep = QLabel('→')
        sep.setStyleSheet('color: #555555; font-size: 11px;')
        layout.addWidget(sep)

        self._follower_bar = QProgressBar()
        self._follower_bar.setRange(POS_MIN, POS_MAX)
        self._follower_bar.setValue(2048)
        self._follower_bar.setFixedHeight(14)
        self._follower_bar.setTextVisible(False)
        self._follower_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #3c3c3c; border-radius: 3px; background-color: #2d2d2d; }
            QProgressBar::chunk { background-color: #1e4d3a; border-radius: 2px; }
        """)
        layout.addWidget(self._follower_bar, 1)

        self._follower_val = QLabel('2048')
        self._follower_val.setFixedWidth(38)
        self._follower_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._follower_val.setStyleSheet('color: #4ec9b0; font-size: 11px; font-family: monospace;')
        layout.addWidget(self._follower_val)

    def update_leader(self, value: float):
        v = int(max(POS_MIN, min(POS_MAX, value)))
        self._leader_bar.setValue(v)
        self._leader_val.setText(str(v))

    def update_follower(self, value: float):
        v = int(max(POS_MIN, min(POS_MAX, value)))
        self._follower_bar.setValue(v)
        self._follower_val.setText(str(v))


# ─── 메인 패널 ────────────────────────────────────────────────────────────────

class TeleopPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui_node: TeleopUINode | None = None
        self._teleop_node: TeleopNode | None = None
        self._leader_node: LeaderArmNode | None = None
        self._follower_node: FollowerArmNode | None = None
        self._executor: MultiThreadedExecutor | None = None
        self._ros_thread: threading.Thread | None = None
        self._running = False
        self._teleop_active = False
        self._leader_connected = False
        self._follower_connected = False

        self._signals = TeleopSignals()
        self._signals.leader_joints_received.connect(self._on_leader_joints)
        self._signals.follower_joints_received.connect(self._on_follower_joints)
        self._signals.leader_status_changed.connect(self._on_leader_status)
        self._signals.follower_status_changed.connect(self._on_follower_status)
        self._signals.teleop_status_changed.connect(self._on_teleop_status)

        self._setup_ui()
        self._init_ros()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        title = QLabel('Teleop Control')
        title.setStyleSheet('color: #ffffff; font-size: 18px; font-weight: 600;')
        main_layout.addWidget(title)

        subtitle = QLabel('리더 → 팔로워 암  (SO-ARM 101)')
        subtitle.setStyleSheet('color: #858585; font-size: 12px;')
        main_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { background-color: #1e1e1e; width: 12px; }
            QScrollBar::handle:vertical { background-color: #424242; border-radius: 6px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        content = QWidget()
        content.setStyleSheet('background-color: transparent;')
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(12)

        conn_label = QLabel('연결 설정')
        conn_label.setStyleSheet('color: #bbbbbb; font-size: 11px; font-weight: 600; letter-spacing: 1px;')
        content_layout.addWidget(conn_label)

        self._leader_widget = ArmConnectionWidget('리더암')
        self._leader_widget.connect_clicked.connect(self._on_leader_connect)
        content_layout.addWidget(self._leader_widget)

        self._follower_widget = ArmConnectionWidget('팔로워암')
        self._follower_widget.connect_clicked.connect(self._on_follower_connect)
        content_layout.addWidget(self._follower_widget)

        joint_group = QGroupBox('관절 상태')
        joint_group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        """)
        joint_layout = QVBoxLayout(joint_group)
        joint_layout.setContentsMargins(10, 16, 10, 10)
        joint_layout.setSpacing(4)

        legend_layout = QHBoxLayout()
        legend_layout.addSpacing(118)
        leader_legend = QLabel('● 리더')
        leader_legend.setStyleSheet('color: #9cdcfe; font-size: 11px;')
        legend_layout.addWidget(leader_legend)
        legend_layout.addStretch()
        follower_legend = QLabel('● 팔로워')
        follower_legend.setStyleSheet('color: #4ec9b0; font-size: 11px;')
        legend_layout.addWidget(follower_legend)
        joint_layout.addLayout(legend_layout)

        self._joint_rows: list[JointStateRow] = []
        for name in JOINT_NAMES:
            row = JointStateRow(name)
            self._joint_rows.append(row)
            joint_layout.addWidget(row)

        content_layout.addWidget(joint_group)
        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._teleop_btn = QPushButton('텔레옵 시작')
        self._teleop_btn.setFixedHeight(44)
        self._teleop_btn.setEnabled(False)
        self._apply_teleop_btn_style(active=False)
        self._teleop_btn.clicked.connect(self._on_teleop_toggle)
        btn_layout.addWidget(self._teleop_btn, 1)

        estop_btn = QPushButton('긴급정지')
        estop_btn.setFixedHeight(44)
        estop_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b1a1a;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #a52020; }
        """)
        estop_btn.clicked.connect(self._on_estop)
        btn_layout.addWidget(estop_btn, 1)

        main_layout.addLayout(btn_layout)

    def _apply_teleop_btn_style(self, active: bool):
        if active:
            self._teleop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7a5500;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #9a6a00; }
                QPushButton:disabled { background-color: #2a2a2a; color: #555; }
            """)
        else:
            self._teleop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #16825d;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #1a9a6e; }
                QPushButton:disabled { background-color: #2a2a2a; color: #555; }
            """)

    # ── ROS2 초기화 ──────────────────────────────────────────────────────────

    def _init_ros(self):
        try:
            if not rclpy.ok():
                rclpy.init()
            self._executor = MultiThreadedExecutor()

            self._ui_node = TeleopUINode(self._signals)
            self._teleop_node = TeleopNode()
            self._executor.add_node(self._ui_node)
            self._executor.add_node(self._teleop_node)

            self._running = True
            self._ros_thread = threading.Thread(target=self._ros_spin, daemon=True)
            self._ros_thread.start()
        except Exception:
            pass

    def _ros_spin(self):
        while self._running and rclpy.ok():
            self._executor.spin_once(timeout_sec=0.1)

    # ── [연결] 버튼 핸들러 ────────────────────────────────────────────────────

    def _on_leader_connect(self, port: str):
        if not self._executor:
            return
        if self._leader_node is not None:
            self._executor.remove_node(self._leader_node)
            self._leader_node.destroy_node()
        self._leader_node = LeaderArmNode(
            parameter_overrides=[Parameter('port', Parameter.Type.STRING, port)]
        )
        self._executor.add_node(self._leader_node)

    def _on_follower_connect(self, port: str):
        if not self._executor:
            return
        if self._follower_node is not None:
            self._executor.remove_node(self._follower_node)
            self._follower_node.destroy_node()
        self._follower_node = FollowerArmNode(
            parameter_overrides=[Parameter('port', Parameter.Type.STRING, port)]
        )
        self._executor.add_node(self._follower_node)

    # ── ROS2 상태 수신 ───────────────────────────────────────────────────────

    def _on_leader_joints(self, positions: list):
        for i, row in enumerate(self._joint_rows):
            if i < len(positions):
                row.update_leader(positions[i])

    def _on_follower_joints(self, positions: list):
        for i, row in enumerate(self._joint_rows):
            if i < len(positions):
                row.update_follower(positions[i])

    def _on_leader_status(self, status: str):
        self._leader_widget.set_status(status)
        self._leader_connected = (status == 'connected')
        self._update_teleop_btn()

    def _on_follower_status(self, status: str):
        self._follower_widget.set_status(status)
        self._follower_connected = (status == 'connected')
        self._update_teleop_btn()

    def _on_teleop_status(self, status: str):
        self._teleop_active = (status == 'active')
        self._teleop_btn.setText('텔레옵 정지' if self._teleop_active else '텔레옵 시작')
        self._apply_teleop_btn_style(active=self._teleop_active)

    def _update_teleop_btn(self):
        self._teleop_btn.setEnabled(self._leader_connected and self._follower_connected)

    def _on_teleop_toggle(self):
        if self._ui_node:
            self._ui_node.send_teleop_command(not self._teleop_active)

    def _on_estop(self):
        if self._ui_node:
            self._ui_node.send_teleop_command(False)

    # ── 정리 ─────────────────────────────────────────────────────────────────

    def cleanup(self):
        self._running = False
        if self._ros_thread and self._ros_thread.is_alive():
            self._ros_thread.join(timeout=1.0)
        if self._executor:
            self._executor.shutdown()
        for node in [self._leader_node, self._follower_node, self._teleop_node, self._ui_node]:
            if node is not None:
                node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
