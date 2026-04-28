import asyncio
from datetime import datetime
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar,
    QDialog, QHBoxLayout,
)
from PySide6.QtCore import Qt, Signal
from rclpy.logging import get_logger
from sensor_msgs.msg import Image

from ..utils import ApiClient
from ..utils.joint_state_collector import JointStateCollector
from ..services import UploadService, MultiCameraRecordingService, ParquetWriter, MetadataService

logger = get_logger('DataCollection')


class DataCollectionPanel(QWidget):
    """데이터 수집 패널"""

    recording_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings: dict = {}
        self.is_recording = False
        self.ros_node = None
        self.joint_collector = None
        self.recording_service = None
        self.session_dir: Path = None
        self.upload_service = UploadService(ApiClient())
        self._frame_subscriptions: list = []
        self.recording_task = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel('Data Collection')
        title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        self.status_label = QLabel('Ready to record')
        self.status_label.setStyleSheet("color: #858585; font-size: 14px;")
        layout.addWidget(self.status_label)

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
            QPushButton:hover { background-color: #e53935; }
            QPushButton:pressed { background-color: #b71c1c; }
            QPushButton:disabled { background-color: #5c5c5c; }
        """)
        self.record_btn.clicked.connect(self._on_record_clicked)
        layout.addWidget(self.record_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def set_ros_node(self, node):
        """ROS2 노드 설정 — JointStateCollector 생성"""
        self.ros_node = node
        self.joint_collector = JointStateCollector(node)

    def set_recording_config(self, settings: dict):
        """녹화 설정 저장 — 서비스 초기화"""
        self.settings = settings

        session_id  = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = Path(f"/tmp/dataset_{session_id}")

        metadata_service = MetadataService()
        global_offset = metadata_service.load_or_init(
            session_dir / "meta",
            camera_roles=settings['camera_roles'],
            fps=30,
        )
        parquet_writer = ParquetWriter(global_frame_offset=global_offset)

        self.recording_service = MultiCameraRecordingService(
            upload_service=self.upload_service,
            joint_collector=self.joint_collector,
            metadata_service=metadata_service,
            parquet_writer=parquet_writer,
        )
        self.session_dir = session_dir

        self.status_label.setText(
            f"Ready: {settings['episodes']} episodes, "
            f"{settings['data_length']}s each"
        )

    # ------------------------------------------------------------------
    # 내부 동작
    # ------------------------------------------------------------------

    def _on_record_clicked(self):
        if not self.is_recording:
            self.recording_task = asyncio.create_task(self._start_recording())

    async def _start_recording(self):
        if not self.ros_node:
            logger.error("ROS2 node not available")
            return
        if not self.recording_service:
            logger.error("Recording service not configured. Call set_recording_config() first.")
            return

        episodes = self.settings.get('episodes', 1)
        camera_roles = self.settings.get('camera_roles', {})

        self.is_recording = True
        self.record_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(episodes)
        self.progress_bar.setValue(0)

        # 카메라 role별 subscription 생성
        self._frame_subscriptions = []
        for role, topic in camera_roles.items():
            sub = self.ros_node.create_subscription(
                Image, topic,
                partial(self.recording_service.on_frame_received, role), 10
            )
            self._frame_subscriptions.append(sub)

        await self.recording_service.run(
            settings=self.settings,
            session_dir=self.session_dir,
            on_status=self.status_label.setText,
            on_progress=lambda idx: self.progress_bar.setValue(idx + 1),
            ask_result=self._ask_episode_result,
        )

        for sub in self._frame_subscriptions:
            self.ros_node.destroy_subscription(sub)
        self._frame_subscriptions = []

        self.progress_bar.setValue(episodes)
        self.status_label.setText("Recording complete!")
        self.is_recording = False
        self.record_btn.setEnabled(True)
        self.recording_finished.emit()

    async def _ask_episode_result(self, episode_index: int) -> bool:
        """에피소드 성공/실패 팝업 — asyncio 루프 블로킹 없이 Future로 대기"""
        loop   = asyncio.get_event_loop()
        future = loop.create_future()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Episode {episode_index + 1} Result")
        dialog.setStyleSheet("background-color: #2d2d2d; color: #ffffff;")
        dialog.setFixedSize(300, 120)

        btn_layout = QHBoxLayout(dialog)
        btn_layout.setContentsMargins(24, 24, 24, 24)
        btn_layout.setSpacing(16)

        label = QLabel(f"Episode {episode_index + 1} — Success?")
        label.setStyleSheet("color: #ffffff; font-size: 14px;")

        success_btn = QPushButton("✓ Success")
        success_btn.setStyleSheet(
            "background-color: #388e3c; color: #fff; border: none; "
            "border-radius: 4px; padding: 8px 20px; font-size: 14px;"
        )
        fail_btn = QPushButton("✗ Fail")
        fail_btn.setStyleSheet(
            "background-color: #d32f2f; color: #fff; border: none; "
            "border-radius: 4px; padding: 8px 20px; font-size: 14px;"
        )

        def _resolve(result: bool):
            if not future.done():
                future.set_result(result)
            dialog.accept()

        success_btn.clicked.connect(lambda: _resolve(True))
        fail_btn.clicked.connect(lambda: _resolve(False))

        outer = QVBoxLayout()
        outer.addWidget(label)
        outer.addLayout(btn_layout)
        btn_layout.addWidget(success_btn)
        btn_layout.addWidget(fail_btn)
        dialog.setLayout(outer)
        dialog.show()

        return await asyncio.wrap_future(future)
