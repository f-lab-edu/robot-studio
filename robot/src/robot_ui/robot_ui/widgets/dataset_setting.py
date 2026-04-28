from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QFrame, QPushButton, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal

CAMERA_ROLES = ['top', 'wrist']

LABEL_STYLE    = "color: #cccccc; font-size: 14px;"
INPUT_STYLE    = """
    background-color: #3c3c3c;
    color: #ffffff;
    border: 1px solid #5c5c5c;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 14px;
"""
FOCUSED_BORDER = "border-color: #0e639c;"


class DatasetSettingPanel(QWidget):
    """데이터셋 설정 패널"""

    submitted = Signal(dict)  # 설정값 전달

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_combos: dict[str, QComboBox] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 헤더
        title = QLabel('Dataset Setting')
        title.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3c3c3c;")
        layout.addWidget(separator)

        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(12)

        # Dataset Name
        self.dataset_name_edit = self._create_lineedit_row(
            settings_layout, 'Dataset Name',
            datetime.now().strftime("dataset_%Y%m%d"),
        )

        # Camera role → topic 매핑
        for role in CAMERA_ROLES:
            combo = self._create_combo_row(settings_layout, f'Camera: {role}')
            self._camera_combos[role] = combo

        # Language Instruction
        self.language_edit = self._create_lineedit_row(
            settings_layout, 'Language Instruction', ''
        )

        # Episodes
        self.episode_spin = self._create_spin_row(
            settings_layout, 'Episodes', 1, 1000, 10
        )

        # Data Length (초)
        self.data_length_spin = self._create_double_spin_row(
            settings_layout, 'Data Length (sec)', 0.1, 3600.0, 10.0
        )

        # Term Length (초)
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
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:pressed { background-color: #094771; }
        """)
        self.submit_btn.clicked.connect(self._on_submit)
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # 위젯 팩토리
    # ------------------------------------------------------------------

    def _create_lineedit_row(
        self, parent_layout: QVBoxLayout, label: str, default: str
    ) -> QLineEdit:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(LABEL_STYLE)
        lbl.setFixedWidth(160)
        row.addWidget(lbl)

        edit = QLineEdit(default)
        edit.setStyleSheet(f"QLineEdit {{ {INPUT_STYLE} }} QLineEdit:focus {{ {FOCUSED_BORDER} }}")
        edit.setFixedWidth(200)
        row.addWidget(edit)
        row.addStretch()
        parent_layout.addLayout(row)
        return edit

    def _create_combo_row(
        self, parent_layout: QVBoxLayout, label: str
    ) -> QComboBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(LABEL_STYLE)
        lbl.setFixedWidth(160)
        row.addWidget(lbl)

        combo = QComboBox()
        combo.addItem('')  # 선택 안 함
        combo.setStyleSheet(f"QComboBox {{ {INPUT_STYLE} }} QComboBox:focus {{ {FOCUSED_BORDER} }}")
        combo.setFixedWidth(200)
        row.addWidget(combo)
        row.addStretch()
        parent_layout.addLayout(row)
        return combo

    def _create_spin_row(
        self, parent_layout: QVBoxLayout, label: str,
        min_val: int, max_val: int, default: int
    ) -> QSpinBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(LABEL_STYLE)
        lbl.setFixedWidth(160)
        row.addWidget(lbl)

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setStyleSheet(f"QSpinBox {{ {INPUT_STYLE} }} QSpinBox:focus {{ {FOCUSED_BORDER} }}")
        spin.setFixedWidth(120)
        row.addWidget(spin)
        row.addStretch()
        parent_layout.addLayout(row)
        return spin

    def _create_double_spin_row(
        self, parent_layout: QVBoxLayout, label: str,
        min_val: float, max_val: float, default: float
    ) -> QDoubleSpinBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(LABEL_STYLE)
        lbl.setFixedWidth(160)
        row.addWidget(lbl)

        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setStyleSheet(f"QDoubleSpinBox {{ {INPUT_STYLE} }} QDoubleSpinBox:focus {{ {FOCUSED_BORDER} }}")
        spin.setFixedWidth(120)
        row.addWidget(spin)
        row.addStretch()
        parent_layout.addLayout(row)
        return spin

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def set_available_topics(self, topics: list[str]):
        """CameraPreviewArea refresh 결과로 ComboBox 목록 갱신"""
        for combo in self._camera_combos.values():
            current = combo.currentText()
            combo.clear()
            combo.addItem('')  # 선택 안 함
            for t in topics:
                combo.addItem(t)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)

    def get_settings(self) -> dict:
        """현재 설정값 반환"""
        camera_roles = {}
        for role, combo in self._camera_combos.items():
            topic = combo.currentText()
            if topic:
                camera_roles[role] = topic

        return {
            'dataset_name':        self.dataset_name_edit.text().strip(),
            'camera_roles':        camera_roles,
            'language_instruction': self.language_edit.text().strip(),
            'episodes':            self.episode_spin.value(),
            'data_length':         self.data_length_spin.value(),
            'term_length':         self.term_length_spin.value(),
        }

    def _on_submit(self):
        self.submitted.emit(self.get_settings())
