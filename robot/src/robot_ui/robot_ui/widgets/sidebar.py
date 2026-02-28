from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Signal, Qt


class SidebarItem(QPushButton):
    """사이드바 메뉴 아이템"""

    def __init__(self, item_id: str, text: str, parent=None):
        super().__init__(text, parent)
        self.item_id = item_id
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #cccccc;
                font-size: 13px;
                text-align: left;
                padding-left: 16px;
            }
            QPushButton:hover {
                background-color: #2a2d2e;
            }
            QPushButton:checked {
                background-color: #094771;
                color: #ffffff;
            }
        """)


class Sidebar(QWidget):
    """고정 너비 사이드바"""

    menu_selected = Signal(str)  # menu_id 전달
    exit_requested = Signal()  # 종료 요청

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-right: 1px solid #3c3c3c;
            }
        """)

        self._items = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 헤더
        header = QLabel('MENU')
        header.setStyleSheet("""
            QLabel {
                color: #bbbbbb;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 1px;
                padding: 8px 8px 16px 8px;
            }
        """)
        layout.addWidget(header)

        # 메뉴 아이템들
        teleop_item = SidebarItem('teleop', 'Teleop')
        teleop_item.clicked.connect(lambda: self._on_item_clicked('teleop'))
        layout.addWidget(teleop_item)
        self._items['teleop'] = teleop_item

        camera_item = SidebarItem('camera_preview', 'Camera Preview')
        camera_item.clicked.connect(lambda: self._on_item_clicked('camera_preview'))
        layout.addWidget(camera_item)
        self._items['camera_preview'] = camera_item

        dataset_item = SidebarItem('dataset_setting', 'Dataset Setting')
        dataset_item.clicked.connect(lambda: self._on_item_clicked('dataset_setting'))
        layout.addWidget(dataset_item)
        self._items['dataset_setting'] = dataset_item

        # 추가 메뉴 공간
        layout.addStretch()

        # Exit 버튼
        exit_btn = QPushButton('Exit')
        exit_btn.setFixedHeight(40)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #cc6666;
                font-size: 13px;
                text-align: left;
                padding-left: 16px;
            }
            QPushButton:hover {
                background-color: #4a2525;
            }
        """)
        exit_btn.clicked.connect(self.exit_requested.emit)
        layout.addWidget(exit_btn)

    def _on_item_clicked(self, item_id: str):
        # 다른 아이템 체크 해제
        for id_, item in self._items.items():
            if id_ != item_id:
                item.setChecked(False)

        self.menu_selected.emit(item_id)
