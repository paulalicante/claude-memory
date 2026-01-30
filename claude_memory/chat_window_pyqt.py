"""
PyQt6 Chat window UI for conversational memory search.
Uses QDialog with exec() for proper modal behavior.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from . import constants
from .database import search_entries
from .ai_query import chat_with_memories, NoAPIKeyError, AIQueryError


class ChatWorker(QThread):
    """Background thread for AI chat processing."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, message, messages, memories, locked_context):
        super().__init__()
        self.message = message
        self.messages = messages
        self.memories = memories
        self.locked_context = locked_context

    def run(self):
        try:
            if not self.locked_context:
                words = self.message.lower().split()
                keywords = [w for w in words if len(w) > 3]
                search_terms = " OR ".join(keywords) if keywords else self.message
                self.memories = search_entries(query=search_terms, limit=15)
                if self.memories:
                    self.status.emit(f"Found {len(self.memories)} memories")

            response = chat_with_memories(self.messages, self.memories)
            self.finished.emit(response)

        except NoAPIKeyError:
            self.error.emit("No API key. Add ai_api_key to config.json")
        except AIQueryError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Error: {e}")


class ChatWindow(QDialog):
    """PyQt6 Chat window using QDialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages = []
        self._current_memories = []
        self._locked_context = False
        self._worker = None

        self.setWindowTitle(f"{constants.APP_NAME} - AI Chat")
        self.resize(600, 500)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header = QLabel("AI Chat")
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(header)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display, 1)

        self._append_system("Welcome! Ask me anything about your memories.")

        # Input
        input_layout = QHBoxLayout()
        self.input_text = QPlainTextEdit()
        self.input_text.setMaximumHeight(60)
        self.input_text.setPlaceholderText("Type message, Enter to send...")
        input_layout.addWidget(self.input_text, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Enter to send
        self.input_text.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.input_text and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not event.modifiers():
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    def _append_system(self, text):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("gray"))
        fmt.setFontItalic(True)
        cursor.insertText(text + "\n", fmt)
        self.chat_display.ensureCursorVisible()

    def _append_message(self, role, content):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setFontWeight(700)
        if role == "user":
            fmt.setForeground(QColor("blue"))
            cursor.insertText("\nYou: ", fmt)
        else:
            fmt.setForeground(QColor("green"))
            cursor.insertText("\nClaude: ", fmt)

        fmt2 = QTextCharFormat()
        fmt2.setForeground(QColor("black"))
        cursor.insertText(content + "\n", fmt2)
        self.chat_display.ensureCursorVisible()

    def _send_message(self):
        msg = self.input_text.toPlainText().strip()
        if not msg:
            return

        self.input_text.clear()

        if msg.lower() == "clear":
            self._clear()
            return

        self._append_message("user", msg)
        self._messages.append({"role": "user", "content": msg})

        self.send_btn.setEnabled(False)
        self.status_label.setText("Thinking...")

        self._worker = ChatWorker(msg, self._messages.copy(),
                                   self._current_memories.copy(), self._locked_context)
        self._worker.finished.connect(self._on_response)
        self._worker.error.connect(self._on_error)
        self._worker.status.connect(lambda s: self.status_label.setText(s))
        self._worker.start()

    def _on_response(self, response):
        self._messages.append({"role": "assistant", "content": response})
        self._append_message("assistant", response)
        self.send_btn.setEnabled(True)
        self.status_label.setText("Ready")
        self.input_text.setFocus()

    def _on_error(self, error):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("red"))
        cursor.insertText(f"Error: {error}\n", fmt)
        self.send_btn.setEnabled(True)
        self.status_label.setText("Ready")

    def _clear(self):
        self._messages = []
        self._current_memories = []
        self._locked_context = False
        self.chat_display.clear()
        self._append_system("Cleared. Ask me anything.")

    def set_memories(self, memories, context_desc=""):
        """Set memories before showing dialog."""
        self._messages = []
        self._current_memories = memories
        self._locked_context = True
        self.chat_display.clear()
        if context_desc:
            self._append_system(f"Chatting about: {context_desc}")
        self._append_system(f"Using {len(memories)} memories.")
