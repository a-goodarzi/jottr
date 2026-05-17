import os
import py_compile
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "jottr"
sys.path.insert(0, str(SRC_DIR))


class ImportAndPackagingTests(unittest.TestCase):
    def test_source_files_compile(self):
        for path in SRC_DIR.glob("*.py"):
            with self.subTest(path=path.name):
                py_compile.compile(str(path), doraise=True)

    def test_core_modules_import(self):
        import editor_tab
        import feed_manager_dialog
        import main
        import rss_reader
        import settings_dialog
        import settings_manager
        import snippet_editor_dialog
        import snippet_manager
        import theme_manager

        self.assertEqual(main.APP_NAME, "Jottr")

    def test_no_qt5_compatibility_references_remain(self):
        offenders = []
        for path in SRC_DIR.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in ("PyQt5", "qt_compat", "install_qt5_aliases"):
                if marker in text:
                    offenders.append(f"{path.name}: {marker}")

        self.assertEqual(offenders, [])

    def test_generated_artifacts_are_ignored(self):
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in (
            "__pycache__/",
            "*.pyc",
            "*.egg-info/",
            "packaging/debian/jottr/",
            "/deb_dist",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, gitignore)


if __name__ == "__main__":
    unittest.main()
