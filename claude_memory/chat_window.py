"""
Chat window UI for conversational memory search.
Allows natural language queries about memories with multi-turn conversation.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional
import threading

from . import constants
from .database import search_entries
from .ai_query import chat_with_memories, NoAPIKeyError, AIQueryError


class ChatWindow:
    """
    Chat window for conversational AI search over memories.
    """

    def __init__(self):
        self._root: Optional[tk.Toplevel] = None
        self._messages: list[dict] = []  # Conversation history
        self._current_memories: list[dict] = []  # Memories in current context
        self._locked_context: bool = False  # If True, don't search for new memories

        # Widget references
        self._chat_display: Optional[scrolledtext.ScrolledText] = None
        self._input_text: Optional[tk.Text] = None
        self._send_btn: Optional[ttk.Button] = None
        self._status_label: Optional[ttk.Label] = None

    def _create_window(self) -> None:
        """Create the chat window."""
        self._root = tk.Toplevel()
        self._root.title(f"{constants.APP_NAME} - AI Chat")
        self._root.geometry(
            f"{constants.CHAT_WINDOW_WIDTH}x{constants.CHAT_WINDOW_HEIGHT}"
        )

        # Handle window close - hide instead of destroy
        self._root.protocol("WM_DELETE_WINDOW", self.hide)

        # Configure grid
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        self._create_chat_area()
        self._create_input_area()

        # Bind Escape to hide
        self._root.bind("<Escape>", lambda e: self.hide())

    def _create_chat_area(self) -> None:
        """Create the chat display area."""
        frame = ttk.Frame(self._root, padding="10 10 10 5")
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # Chat display - light pastel theme (like Claude.ai)
        self._chat_display = scrolledtext.ScrolledText(
            frame,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#FDF6E3",  # Light cream/yellow pastel
            fg="#5C5C5C",  # Dark gray text
        )
        self._chat_display.grid(row=0, column=0, sticky="nsew")

        # Configure tags for styling - warm pastel theme
        self._chat_display.tag_configure("user", foreground="#B8860B", font=("Segoe UI", 10, "bold"))  # Dark goldenrod
        self._chat_display.tag_configure("assistant", foreground="#D2691E", font=("Segoe UI", 10, "bold"))  # Chocolate/orange
        self._chat_display.tag_configure("system", foreground="#9A9A7C", font=("Segoe UI", 9, "italic"))  # Olive gray
        self._chat_display.tag_configure("error", foreground="#CC4444")  # Soft red

        # Welcome message
        self._append_system("Welcome! Ask me anything about your memories.\n"
                          "I'll search your database and answer based on what I find.\n"
                          "Type 'clear' to start a new conversation.\n")

    def _create_input_area(self) -> None:
        """Create the input area."""
        frame = ttk.Frame(self._root, padding="10 5 10 10")
        frame.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        # Status label
        self._status_label = ttk.Label(frame, text="Ready", foreground="gray")
        self._status_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Input text area (3 lines, slightly different background)
        self._input_text = tk.Text(
            frame,
            font=("Segoe UI", 11),
            height=3,
            wrap=tk.WORD,
            bg="#FAF0E6",  # Linen - slightly warmer than chat area
            fg="#5C5C5C",
            insertbackground="#5C5C5C",  # Cursor color
            relief=tk.SOLID,
            borderwidth=1,
        )
        self._input_text.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        # Bind Enter to send (Shift+Enter for newline)
        self._input_text.bind("<Return>", self._on_enter_key)
        self._input_text.bind("<Shift-Return>", lambda e: None)  # Allow newline

        # Send button
        self._send_btn = ttk.Button(frame, text="Send", command=self._send_message)
        self._send_btn.grid(row=1, column=1, sticky="n", pady=5)

    def _append_message(self, role: str, content: str) -> None:
        """Append a message to the chat display."""
        self._chat_display.config(state=tk.NORMAL)

        if role == "user":
            self._chat_display.insert(tk.END, "\nYou: ", "user")
        elif role == "assistant":
            self._chat_display.insert(tk.END, "\nClaude: ", "assistant")

        self._chat_display.insert(tk.END, content + "\n")
        self._chat_display.see(tk.END)
        self._chat_display.config(state=tk.DISABLED)

    def _append_system(self, content: str) -> None:
        """Append a system message."""
        self._chat_display.config(state=tk.NORMAL)
        self._chat_display.insert(tk.END, content + "\n", "system")
        self._chat_display.see(tk.END)
        self._chat_display.config(state=tk.DISABLED)

    def _append_error(self, content: str) -> None:
        """Append an error message."""
        self._chat_display.config(state=tk.NORMAL)
        self._chat_display.insert(tk.END, f"Error: {content}\n", "error")
        self._chat_display.see(tk.END)
        self._chat_display.config(state=tk.DISABLED)

    def _on_enter_key(self, event) -> str:
        """Handle Enter key - send message unless Shift is held."""
        if event.state & 0x1:  # Shift is held
            return  # Allow newline
        self._send_message()
        return "break"  # Prevent default newline insertion

    def _send_message(self) -> None:
        """Send user message and get AI response."""
        message = self._input_text.get("1.0", tk.END).strip()
        if not message:
            return

        # Clear input
        self._input_text.delete("1.0", tk.END)

        # Handle clear command
        if message.lower() == "clear":
            self._clear_conversation()
            return

        # Display user message
        self._append_message("user", message)
        self._messages.append({"role": "user", "content": message})

        # Disable input while processing
        self._set_loading(True)

        # Process in background thread
        thread = threading.Thread(target=self._process_message, args=(message,))
        thread.daemon = True
        thread.start()

    def _extract_search_terms(self, message: str) -> str:
        """Extract meaningful search terms from a natural language question."""
        # Common words to filter out
        stop_words = {
            "what", "where", "when", "who", "why", "how", "is", "are", "was", "were",
            "do", "does", "did", "can", "could", "would", "should", "will", "shall",
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "between", "under", "again", "further", "then",
            "once", "here", "there", "all", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "about", "my", "your", "his", "her", "its", "our",
            "their", "this", "that", "these", "those", "am", "been", "being", "have",
            "has", "had", "having", "me", "i", "you", "he", "she", "it", "we", "they",
            "find", "show", "tell", "give", "get", "make", "know", "think", "look",
            "search", "summarize", "summarise", "explain", "describe", "list",
        }

        words = message.lower().split()
        keywords = [w.strip("?.,!") for w in words if w.strip("?.,!") not in stop_words and len(w) > 2]

        # Use OR to match any keyword
        if keywords:
            return " OR ".join(keywords)
        return message

    def _process_message(self, message: str) -> None:
        """Process message in background thread."""
        try:
            # Skip search if context is locked (using specific memories from search window)
            if not self._locked_context:
                # For first message or if context seems different, search for new memories
                if len(self._messages) <= 1 or self._should_refresh_context(message):
                    search_terms = self._extract_search_terms(message)
                    self._current_memories = search_entries(query=search_terms, limit=15)
                    if self._current_memories:
                        self._root.after(0, lambda: self._update_status(
                            f"Found {len(self._current_memories)} relevant memories"
                        ))
                    else:
                        self._root.after(0, lambda: self._update_status("Chatting (no memories matched)"))

            # Use chat_with_memories - it handles both with and without memories
            response = chat_with_memories(self._messages, self._current_memories)

            self._messages.append({"role": "assistant", "content": response})
            self._root.after(0, lambda: self._append_message("assistant", response))

        except NoAPIKeyError:
            self._root.after(0, lambda: self._append_error(
                "No API key configured. Add your Anthropic API key to config.json"
            ))
        except AIQueryError as e:
            self._root.after(0, lambda: self._append_error(str(e)))
        except Exception as e:
            self._root.after(0, lambda: self._append_error(f"Unexpected error: {e}"))
        finally:
            self._root.after(0, lambda: self._set_loading(False))

    def _should_refresh_context(self, message: str) -> bool:
        """Determine if we should search for new memories."""
        # Simple heuristic: refresh if message contains question words
        # or if conversation is getting long
        question_words = ["what", "when", "where", "who", "why", "how", "find", "search", "show"]
        message_lower = message.lower()
        return any(word in message_lower for word in question_words) or len(self._messages) > 6

    def _set_loading(self, loading: bool) -> None:
        """Set loading state."""
        if loading:
            self._send_btn.config(state=tk.DISABLED)
            self._input_text.config(state=tk.DISABLED)
            self._status_label.config(text="Thinking...")
        else:
            self._send_btn.config(state=tk.NORMAL)
            self._input_text.config(state=tk.NORMAL)
            self._input_text.focus()
            self._status_label.config(text="Ready")

    def _update_status(self, text: str) -> None:
        """Update status label."""
        self._status_label.config(text=text)

    def _clear_conversation(self) -> None:
        """Clear conversation history."""
        self._messages = []
        self._current_memories = []
        self._locked_context = False  # Unlock context on clear
        self._chat_display.config(state=tk.NORMAL)
        self._chat_display.delete("1.0", tk.END)
        self._chat_display.config(state=tk.DISABLED)
        self._append_system("Conversation cleared. Ask me anything about your memories.")
        self._status_label.config(text="Ready")

    def show(self) -> None:
        """Show the chat window."""
        if self._root is None:
            self._create_window()

        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        if self._input_text:
            self._input_text.focus()

    def show_with_memories(self, memories: list[dict], context_description: str = "") -> None:
        """
        Show the chat window with a fixed set of memories.
        The AI will only use these memories, not search for new ones.

        Args:
            memories: List of memory entries to use as context
            context_description: Optional description of the context (e.g., "Tesla search results")
        """
        if self._root is None:
            self._create_window()

        # Clear previous conversation
        self._messages = []
        self._current_memories = memories
        self._locked_context = True  # Flag to prevent auto-searching

        # Clear display and show context info
        self._chat_display.config(state=tk.NORMAL)
        self._chat_display.delete("1.0", tk.END)
        self._chat_display.config(state=tk.DISABLED)

        if context_description:
            self._append_system(f"Chatting about: {context_description}")
        self._append_system(f"Context locked to {len(memories)} memories from your search.")
        self._append_system("Ask questions about these specific results.\n")

        self._update_status(f"Locked to {len(memories)} memories")

        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        if self._input_text:
            self._input_text.focus()

    def hide(self) -> None:
        """Hide the chat window."""
        if self._root:
            self._root.withdraw()

    def toggle(self) -> None:
        """Toggle window visibility."""
        if self._root is None or not self._root.winfo_viewable():
            self.show()
        else:
            self.hide()

    def destroy(self) -> None:
        """Destroy the window."""
        if self._root:
            self._root.destroy()
            self._root = None
