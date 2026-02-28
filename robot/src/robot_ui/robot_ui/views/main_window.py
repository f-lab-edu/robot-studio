from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
from rclpy.logging import get_logger
from ..widgets import Sidebar, CameraPreviewArea, DatasetSettingPanel, DataCollectionPanel, TeleopPanel

logger = get_logger('MainWindow')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Robot Studio')
        self.setMinimumSize(1200, 800)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #cccccc;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 고정 사이드바
        self.sidebar = Sidebar()
        self.sidebar.menu_selected.connect(self._on_menu_selected)
        self.sidebar.exit_requested.connect(self.close)
        main_layout.addWidget(self.sidebar)

        # 2. 텔레옵 패널
        self.teleop_panel = TeleopPanel()
        self.teleop_panel.setVisible(False)
        main_layout.addWidget(self.teleop_panel, 1)

        # 3. 메인 콘텐츠 영역
        self.camera_preview_area = CameraPreviewArea()
        self.camera_preview_area.setVisible(False)
        self.camera_preview_area.camera_selected.connect(self._on_camera_selected)
        main_layout.addWidget(self.camera_preview_area, 1)

        # 3. 데이터셋 설정 패널
        self.dataset_setting_panel = DatasetSettingPanel()
        self.dataset_setting_panel.setVisible(False)
        self.dataset_setting_panel.submitted.connect(self._on_dataset_submitted)
        main_layout.addWidget(self.dataset_setting_panel, 1)

        # 4. 데이터 수집 패널
        self.data_collection_panel = DataCollectionPanel()
        self.data_collection_panel.setVisible(False)
        main_layout.addWidget(self.data_collection_panel, 1)

        # 빈 메인 영역 (기본)
        self.empty_area = QWidget()
        self.empty_area.setStyleSheet("background-color: #1e1e1e;")
        main_layout.addWidget(self.empty_area, 1)

    def _on_menu_selected(self, menu_id: str):
        # 모든 영역 숨기기
        self.teleop_panel.setVisible(False)
        self.camera_preview_area.setVisible(False)
        self.dataset_setting_panel.setVisible(False)
        self.data_collection_panel.setVisible(False)
        self.empty_area.setVisible(False)

        if menu_id == 'teleop':
            self.teleop_panel.setVisible(True)
        elif menu_id == 'camera_preview':
            self.camera_preview_area.setVisible(True)
        elif menu_id == 'dataset_setting':
            self.dataset_setting_panel.setVisible(True)
        else:
            self.empty_area.setVisible(True)

    def _on_camera_selected(self, topic_name: str):
        """카메라 선택 시 Dataset Setting 화면으로 전환"""
        self.dataset_setting_panel.set_camera(topic_name)

        # 모든 영역 숨기고 Dataset Setting 표시
        self.camera_preview_area.setVisible(False)
        self.dataset_setting_panel.setVisible(True)
        self.empty_area.setVisible(False)

        # 사이드바 메뉴 상태 업데이트
        self.sidebar._items['camera_preview'].setChecked(False)
        self.sidebar._items['dataset_setting'].setChecked(True)

    def _on_dataset_submitted(self, settings: dict):
        """Dataset Setting 제출 시 데이터 수집 화면으로 이동"""
        logger.info(f"Dataset settings submitted: {settings}")

        # ROS2 노드 공유
        if self.camera_preview_area.ros_node:
            self.data_collection_panel.set_ros_node(self.camera_preview_area.ros_node)
        self.data_collection_panel.set_recording_config(settings)
        self.camera_preview_area.setVisible(False)
        self.dataset_setting_panel.setVisible(False)
        self.data_collection_panel.setVisible(True)
        self.empty_area.setVisible(False)      

    def closeEvent(self, event):
        if hasattr(self, 'teleop_panel'):
            self.teleop_panel.cleanup()
        if hasattr(self, 'camera_preview_area'):
            self.camera_preview_area.cleanup()
        super().closeEvent(event)
