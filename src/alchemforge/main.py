import os
import sys
import tempfile


def configure_qt_runtime():
    """Set writable Qt/WebEngine defaults for remote desktop sessions."""
    if not os.environ.get("XDG_RUNTIME_DIR"):
        runtime_dir = os.path.join(
            tempfile.gettempdir(),
            f"runtime-{os.getuid()}",
        )
        os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
        os.chmod(runtime_dir, 0o700)
        os.environ["XDG_RUNTIME_DIR"] = runtime_dir

    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--use-gl=swiftshader --enable-unsafe-swiftshader "
        "--disable-gpu-sandbox",
    )

from PyQt5.QtWidgets import QApplication

from alchemforge.ui.main_window import MainWindow


def main():
    configure_qt_runtime()
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()