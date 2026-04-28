from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QFrame, QPushButton
)
from PySide6.QtCore import Qt, Signal


class DatasetSettingPanel(QWidget):
    """데이터셋 설정 패널"""

    submitted = Signal(dict)  # 설정값 전달

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_topic: str = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 헤더
        title = QLabel('Dataset Setting')
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
            }
        """)
        layout.addWidget(title)

        # 선택된 카메라 표시
        self.camera_label = QLabel('No camera selected')
        self.camera_label.setStyleSheet("""
            QLabel {
                color: #858585;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.camera_label)

        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3c3c3c;")
        layout.addWidget(separator)

        # 설정 영역
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(12)

        # 에피소드 개수
        self.episode_spin = self._create_spin_row(
            settings_layout, 'Episodes', 1, 1000, 10
        )

        # Data 길이 (초)
        self.data_length_spin = self._create_double_spin_row(
            settings_layout, 'Data Length (sec)', 0.1, 3600.0, 10.0
        )

        # Term 길이 (초)
        self.term_length_spin = self._create_double_spin_row(
            settings_layout, 'Term Length (sec)', 0.0, 3600.0, 1.0
        )

        layout.addLayout(settings_layout)
        layout.addStretch()

        # Submit 버튼
        btn_layout = QHBoxLayout()
        self.submit_btn = QPushButton('Start Recording')
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:pressed {
                background-color: #094771;
            }
        """)
        self.submit_btn.clicked.connect(self._on_submit)
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _create_spin_row(
        self, parent_layout: QVBoxLayout, label: str,
        min_val: int, max_val: int, default: int
    ) -> QSpinBox:
        """정수 입력 행 생성"""
        row = QHBoxLayout()

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #cccccc; font-size: 14px;")
        lbl.setFixedWidth(150)
        row.addWidget(lbl)

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #5c5c5c;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
            }
            QSpinBox:focus {
                border-color: #0e639c;
            }
        """)
        spin.setFixedWidth(120)
        row.addWidget(spin)

        row.addStretch()
        parent_layout.addLayout(row)
        return spin

    def _create_double_spin_row(
        self, parent_layout: QVBoxLayout, label: str,
        min_val: float, max_val: float, default: float
    ) -> QDoubleSpinBox:
        """실수 입력 행 생성"""
        row = QHBoxLayout()

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #cccccc; font-size: 14px;")
        lbl.setFixedWidth(150)
        row.addWidget(lbl)

        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #5c5c5c;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
            }
            QDoubleSpinBox:focus {
                border-color: #0e639c;
            }
        """)
        spin.setFixedWidth(120)
        row.addWidget(spin)

        row.addStretch()
        parent_layout.addLayout(row)
        return spin

    def set_camera(self, topic_name: str):
        """선택된 카메라 설정"""
        self.selected_topic = topic_name
        self.camera_label.setText(f'Selected: {topic_name}')

    def _on_submit(self):
        """Submit 버튼 클릭 시"""
        settings = self.get_settings()
        settings['topic'] = self.selected_topic
        self.submitted.emit(settings)

    def get_settings(self) -> dict:
        """현재 설정값 반환"""
        return {
            'episodes': self.episode_spin.value(),
            'data_length': self.data_length_spin.value(),
            'term_length': self.term_length_spin.value(),
        }
