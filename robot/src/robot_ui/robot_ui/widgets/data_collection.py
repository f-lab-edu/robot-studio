import asyncio
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar
from PySide6.QtCore import Qt, Signal
from rclpy.logging import get_logger
from sensor_msgs.msg import Image
from ..utils import ApiClient
from ..services import UploadService, RecordingService

logger = get_logger('DataCollection')


class DataCollectionPanel(QWidget):
    """데이터 수집 패널"""

    recording_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings: dict = {}
        self.is_recording = False
        self.ros_node = None
        self._frame_subscription = None
        self.recording_service = RecordingService(UploadService(ApiClient()))
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 헤더
        title = QLabel('Data Collection')
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
            }
        """)
        layout.addWidget(title)

        # 상태 표시
        self.status_label = QLabel('Ready to record')
        self.status_label.setStyleSheet("color: #858585; font-size: 14px;")
        layout.addWidget(self.status_label)

        # 진행률 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                background-color: #2d2d2d;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        layout.addStretch()

        # Record 버튼
        self.record_btn = QPushButton('Record')
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 12px 32px;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e53935;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #5c5c5c;
            }
        """)
        self.record_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self.record_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    def set_ros_node(self, ros_node):
        """ROS2 노드 설정"""
        self.ros_node = ros_node

    def set_recording_config(self, settings: dict):
        """녹화 설정 저장"""
        self.settings = settings
        self.status_label.setText(
            f"Ready: {settings['episodes']} episodes, "
            f"{settings['data_length']}s each"
        )

    def _on_record_clicked(self):
        """Record 버튼 클릭 시"""
        if not self.is_recording:
            self.recodign_task = asyncio.create_task(self._start_recording())

    async def _start_recording(self):
        """녹화 시작"""
        if not self.ros_node:
            logger.error("ROS2 node not available")
            return

        episodes = self.settings.get('episodes', 1)
        topic = self.settings.get('topic', '')

        self.is_recording = True
        self.record_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(episodes)
        self.progress_bar.setValue(0)

        self._frame_subscription = self.ros_node.create_subscription(
            Image, topic, self.recording_service.on_frame_received, 10
        )

        await self.recording_service.run(
            self.settings,
            on_status=self.status_label.setText,
            on_progress=lambda idx: self.progress_bar.setValue(idx + 1),
        )

        if self._frame_subscription:
            self.ros_node.destroy_subscription(self._frame_subscription)
            self._frame_subscription = None

        self.progress_bar.setValue(episodes)
        self.status_label.setText("Recording complete!")
        self.is_recording = False
        self.record_btn.setEnabled(True)
        self.recording_finished.emit()
