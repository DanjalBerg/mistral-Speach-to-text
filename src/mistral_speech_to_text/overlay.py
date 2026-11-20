import queue
import sys


class ConsoleOverlay:
    def __init__(self, settings):
        self._settings = settings

    def update(self, lines) -> None:
        print("\r" + " | ".join(lines), end="", flush=True)

    def run(self) -> None:
        pass

    def close(self) -> None:
        print()


class QtOverlay:
    def __init__(self, settings):
        self._settings = settings
        self._queue: queue.Queue = queue.Queue()
        self._app = None
        self._window = None
        self._label = None

    def update(self, lines) -> None:
        self._queue.put(list(lines))

    def _build(self) -> None:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QColor, QGraphicsDropShadowEffect
        from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

        self._app = QApplication.instance() or QApplication(sys.argv)
        window = QWidget()
        window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        label = QLabel()
        alpha = int(round(self._settings.opacity * 255))
        label.setStyleSheet(
            f"color: white; font-size: {self._settings.font_size}px; font-weight: 600; "
            f"padding: 10px 18px; background-color: rgba(0, 0, 0, {alpha}); border-radius: 14px;"
        )
        label.setWordWrap(True)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 2)
        label.setGraphicsEffect(shadow)

        layout = QVBoxLayout(window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)

        self._window = window
        self._label = label

        timer = QTimer()
        timer.timeout.connect(self._drain)
        timer.start(50)

    def _drain(self) -> None:
        lines = None
        while True:
            try:
                lines = self._queue.get_nowait()
            except queue.Empty:
                break
        if lines is None:
            return
        text = "\n".join(lines) if lines else " "
        self._label.setText(text)
        self._window.adjustSize()
        self._reposition()

    def _reposition(self) -> None:
        screen = self._app.primaryScreen().availableGeometry()
        width = min(int(screen.width() * 0.8), 1400)
        self._window.resize(width, self._window.sizeHint().height())
        x = screen.x() + (screen.width() - self._window.width()) // 2
        y = screen.y() + screen.height() - self._window.height() - 60
        self._window.move(x, y)

    def _make_click_through_windows(self) -> None:
        if sys.platform != "win32":
            return
        import ctypes

        hwnd = int(self._window.winId())
        gwl_exstyle = -20
        ws_ex_transparent = 0x20
        ws_ex_layered = 0x80000
        ws_ex_noactivate = 0x08000000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, gwl_exstyle, style | ws_ex_transparent | ws_ex_layered | ws_ex_noactivate
        )

    def run(self) -> None:
        self._build()
        self._window.show()
        self._make_click_through_windows()
        self._reposition()
        self._app.exec()

    def close(self) -> None:
        if self._app is not None:
            self._app.quit()
