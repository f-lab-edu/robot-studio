from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Signal, QUrl
from urllib.parse import urlparse, parse_qs


class LoginWebView(QWidget):
    """Embedded Browser 기반 로그인 위젯"""

    login_success = Signal(str)  # (code,) — 토큰이 아닌 1회용 코드 전달

    def __init__(self, login_url: str = "http://localhost:3000/login?from=robot"):
        super().__init__()
        self._login_url = login_url
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl(self._login_url))
        self.web_view.urlChanged.connect(self._on_url_changed)
        layout.addWidget(self.web_view)

    def _on_url_changed(self, url: QUrl):
        """URL 변경 감지 — /auth/callback 도달 시 code 추출"""
        parsed = urlparse(url.toString())
        if parsed.path == "/auth/callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            if code:
                self.login_success.emit(code)

    def reset(self):
        """로그인 실패/로그아웃 시 초기화"""
        self.web_view.setUrl(QUrl(self._login_url))
