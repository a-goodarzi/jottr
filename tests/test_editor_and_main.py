import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "jottr"
sys.path.insert(0, str(SRC_DIR))

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QTextEdit, QWidget

from editor_tab import EditorTab
import main as main_module
from main import APP_NAME, TextEditorApp
from settings_manager import SettingsManager
from snippet_manager import SnippetManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication([])
    return _APP


class EditorAndMainTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.settings = SettingsManager()
        self.snippets = SnippetManager(self.settings)

    def make_editor(self):
        editor = EditorTab(self.snippets, self.settings)
        self.addCleanup(editor.deleteLater)
        self.addCleanup(editor.backup_timer.stop)
        self.addCleanup(editor.preview_scroll_timer.stop)
        return editor

    def test_markdown_helpers_cover_tables_tasks_math_and_shortcodes(self):
        editor = self.make_editor()

        self.assertEqual(EditorTab.split_table_row(r"| a \| b | c |"), ["a | b", "c"])
        self.assertEqual(EditorTab.apply_emoji_shortcodes("Ship it :rocket:"), "Ship it 🚀")
        html = editor.render_markdown_html(
            "# Title\n\n- [x] done\n\n| A | B |\n| --- | ---: |\n| one | two |\n\n$$x^2$$"
        )

        self.assertIn("Title", html)
        self.assertIn("task-list-item-checkbox", html)
        self.assertIn("<table", html)
        self.assertIn("math-block", html)

    def test_editor_file_and_line_number_state(self):
        editor = self.make_editor()

        self.assertTrue(editor.is_markdown_file("notes.md"))
        self.assertTrue(editor.is_markdown_file("notes.markdown"))
        self.assertFalse(editor.is_markdown_file("notes.txt"))

        editor.set_line_numbers_visible(False)
        self.assertFalse(editor.editor.line_numbers_visible)
        editor.set_line_numbers_visible(True)
        self.assertTrue(editor.editor.line_numbers_visible)

    def test_editor_snippet_insert_find_replace_and_save(self):
        editor = self.make_editor()
        self.snippets.add_snippet("sig", "Regards")
        editor.update_snippet_list()

        self.assertEqual(editor.snippet_list.count(), 1)
        editor.insert_snippet(editor.snippet_list.item(0))
        self.assertEqual(editor.editor.toPlainText(), "Regards")

        editor.editor.setPlainText("alpha beta alpha")
        editor.find_input.setText("alpha")
        editor.replace_input.setText("omega")
        with patch("editor_tab.QMessageBox.information"):
            editor.replace_all()
        self.assertEqual(editor.editor.toPlainText(), "omega beta omega")

        target = Path(self.temp_dir.name) / "saved.txt"
        editor.current_file = str(target)
        editor.editor.setPlainText("saved content")
        self.assertTrue(editor.save_file())
        self.assertEqual(target.read_text(encoding="utf-8"), "saved content")

    def test_editor_pane_state_is_saved(self):
        editor = self.make_editor()
        editor.show()
        app().processEvents()

        editor.toggle_pane("snippets")
        states = self.settings.get_setting("pane_states")

        self.assertTrue(states["snippets_visible"])
        self.assertIn("sizes", states)

    def test_main_window_smoke_actions(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.settings_manager = settings_manager
                self.editor = QTextEdit(self)
                self.editor.line_numbers_visible = True
                self.current_font = settings_manager.get_font()
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def update_font(self, font):
                self.current_font = QFont(font)

            def toggle_markdown_preview(self):
                self.markdown_preview_visible = not self.markdown_preview_visible

            def set_line_numbers_visible(self, visible):
                self.editor.line_numbers_visible = visible

            def save_file(self, force_dialog=False):
                return True

        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            self.assertEqual(window.windowTitle(), APP_NAME)
            self.assertGreaterEqual(window.tab_widget.count(), 1)
            first_tab = window.tab_widget.currentWidget()
            original_size = first_tab.current_font.pointSize()

            window.zoom_in()
            self.assertEqual(first_tab.current_font.pointSize(), original_size + 1)
            window.zoom_out()
            self.assertEqual(first_tab.current_font.pointSize(), original_size)
            window.toggle_markdown_preview()
            self.assertTrue(first_tab.markdown_preview_visible)
            window.apply_editor_line_numbers(False)
            self.assertFalse(first_tab.editor.line_numbers_visible)

    def test_main_window_opens_file_in_new_tab(self):
        class FakeEditorTab(QWidget):
            def __init__(self, snippet_manager, settings_manager):
                super().__init__()
                self.editor = QTextEdit(self)
                self.current_file = None
                self.markdown_preview_visible = False

            def set_main_window(self, main_window):
                self.main_window = main_window

            def is_markdown_file(self, file_path=None):
                return str(file_path or self.current_file or "").lower().endswith((".md", ".markdown"))

            def set_markdown_preview_visible(self, visible):
                self.markdown_preview_visible = visible

        target = Path(self.temp_dir.name) / "story.md"
        target.write_text("# Story", encoding="utf-8")
        with patch.object(main_module, "EditorTab", FakeEditorTab):
            window = TextEditorApp()
            self.addCleanup(window.close)
            self.addCleanup(window.deleteLater)

            window.open_file(str(target))
            current = window.tab_widget.currentWidget()

            self.assertEqual(current.current_file, str(target))
            self.assertEqual(current.editor.toPlainText(), "# Story")
            self.assertTrue(current.markdown_preview_visible)


if __name__ == "__main__":
    unittest.main()
