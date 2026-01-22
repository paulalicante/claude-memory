"""
HTTP server for Claude Memory app.
Provides REST API for external integrations (e.g., browser extensions).
"""

import threading
from typing import Optional, Callable

from flask import Flask, request, jsonify
from flask_cors import CORS

from . import database
from .notifications import notify_saved


# Create Flask app
app = Flask(__name__)
CORS(app, origins=[
    "chrome-extension://*",
    "http://localhost:*",
    "http://127.0.0.1:*",
    "https://docs.google.com",
    "https://mail.google.com",
    "https://claude.ai"
])

# Server state
_server_thread: Optional[threading.Thread] = None
_shutdown_event = threading.Event()


@app.route("/api/memories", methods=["POST"])
def add_memory():
    """
    Add a new memory entry.

    Expected JSON body:
    {
        "title": "Required title",
        "content": "Required content",
        "category": "optional category",
        "tags": "optional, comma-separated",
        "metadata": {  // optional, stored in source_conversation
            "recipients": ["email@example.com"],
            "subject": "Email subject",
            "date": "2026-01-19T10:30:00Z"
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No JSON body provided"}), 400

        # Validate required fields
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()

        if not title:
            return jsonify({"success": False, "error": "Title is required"}), 400
        if not content:
            return jsonify({"success": False, "error": "Content is required"}), 400

        # Optional fields
        category = data.get("category")
        tags = data.get("tags")

        # Store metadata as source_conversation (JSON string)
        metadata = data.get("metadata")
        source_conversation = None
        if metadata:
            import json
            source_conversation = json.dumps(metadata)

        # Add to database
        entry_id = database.add_entry(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source_conversation=source_conversation,
        )

        # Skip toast notification for extension saves - they handle their own feedback
        # (and WhatsApp saves silently to avoid spam)
        # notify_saved(title)

        return jsonify({
            "success": True,
            "id": entry_id,
            "message": f"Memory saved: {title}"
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "claude-memory"})


# ============================================================================
# Trusted Contacts Endpoints
# ============================================================================

@app.route("/api/contacts", methods=["GET"])
def list_contacts():
    """List all trusted contacts."""
    try:
        limit = request.args.get("limit", 100, type=int)
        contacts = database.get_trusted_contacts(limit)
        return jsonify({"success": True, "contacts": contacts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/contacts", methods=["POST"])
def add_contacts():
    """
    Add one or more trusted contacts.

    Expected JSON body:
    {
        "emails": ["email1@example.com", "email2@example.com"]
    }
    or
    {
        "email": "single@example.com",
        "name": "Optional Name"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON body"}), 400

        # Handle single email
        if "email" in data:
            added = database.add_trusted_contact(
                data["email"],
                data.get("name")
            )
            return jsonify({
                "success": True,
                "added": 1 if added else 0,
                "message": "Contact added" if added else "Contact already exists"
            })

        # Handle multiple emails
        if "emails" in data:
            emails = data["emails"]
            if not isinstance(emails, list):
                return jsonify({"success": False, "error": "emails must be a list"}), 400

            added = database.add_trusted_contacts(emails)
            return jsonify({
                "success": True,
                "added": added,
                "message": f"Added {added} new contact(s)"
            })

        return jsonify({"success": False, "error": "Provide 'email' or 'emails'"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/contacts/check", methods=["GET"])
def check_contact():
    """
    Check if an email is a trusted contact.

    Query params: ?email=test@example.com
    """
    email = request.args.get("email")
    if not email:
        return jsonify({"success": False, "error": "email parameter required"}), 400

    try:
        is_trusted = database.is_trusted_contact(email)
        return jsonify({"success": True, "email": email, "trusted": is_trusted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/contacts/<email>", methods=["DELETE"])
def delete_contact(email):
    """Remove a trusted contact."""
    try:
        removed = database.remove_trusted_contact(email)
        if removed:
            return jsonify({"success": True, "message": "Contact removed"})
        else:
            return jsonify({"success": False, "error": "Contact not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# Email Tracking Endpoints (duplicate prevention)
# ============================================================================

@app.route("/api/emails/check", methods=["GET"])
def check_email_saved():
    """
    Check if an email has already been saved.

    Query params: ?gmail_id=abc123
    """
    gmail_id = request.args.get("gmail_id")
    if not gmail_id:
        return jsonify({"success": False, "error": "gmail_id parameter required"}), 400

    try:
        is_saved = database.is_email_saved(gmail_id)
        return jsonify({"success": True, "gmail_id": gmail_id, "saved": is_saved})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emails/mark-saved", methods=["POST"])
def mark_email_as_saved():
    """
    Mark an email as saved (for duplicate prevention).

    Expected JSON body:
    {
        "gmail_id": "abc123",
        "entry_id": 42  // optional
    }
    """
    try:
        data = request.get_json()
        if not data or "gmail_id" not in data:
            return jsonify({"success": False, "error": "gmail_id required"}), 400

        database.mark_email_saved(data["gmail_id"], data.get("entry_id"))
        return jsonify({"success": True, "message": "Email marked as saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/copy-document", methods=["POST"])
def copy_document():
    """
    Send real OS-level Ctrl+A, Ctrl+C keystrokes to copy document content.
    Used by Google Docs extension since synthetic JS events don't work.
    """
    import time
    import keyboard
    import pyperclip

    try:
        # Remember old clipboard content to detect change
        old_content = ""
        try:
            old_content = pyperclip.paste() or ""
        except Exception:
            pass

        # Clear clipboard to ensure we detect the new copy
        try:
            pyperclip.copy("")
        except Exception:
            pass

        # Longer delay to ensure window has focus after button click
        time.sleep(0.5)

        # Click in the center of the screen to ensure something is focused
        # This helps when the browser button stole focus
        import pyautogui
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        time.sleep(0.2)

        # Send real Ctrl+A (select all)
        keyboard.send('ctrl+a')
        time.sleep(0.3)

        # Send real Ctrl+C (copy)
        keyboard.send('ctrl+c')

        # Wait for clipboard to update - poll with retries
        content = ""
        for attempt in range(10):  # Try up to 10 times over 1 second
            time.sleep(0.1)
            try:
                content = pyperclip.paste() or ""
            except Exception:
                continue

            # If clipboard has non-empty content that's different from old, we got it
            if content.strip() and content != old_content:
                break

        # Press Escape to deselect (cleaner UX)
        keyboard.send('escape')

        if content and content.strip():
            return jsonify({
                "success": True,
                "content": content.strip(),
                "length": len(content.strip())
            })
        else:
            return jsonify({
                "success": False,
                "error": "Clipboard did not update after copy - is the document focused?"
            }), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def start_server(port: int = 8765, on_started: Optional[Callable] = None) -> None:
    """
    Start the HTTP server in a background thread.

    Args:
        port: Port to listen on (default 8765)
        on_started: Optional callback when server is ready
    """
    global _server_thread, _shutdown_event

    if _server_thread and _server_thread.is_alive():
        return  # Already running

    _shutdown_event.clear()

    def run_server():
        # Use werkzeug's server with threaded mode
        from werkzeug.serving import make_server

        server = make_server("127.0.0.1", port, app, threaded=True)
        server.timeout = 1  # Check for shutdown every second

        if on_started:
            on_started()

        while not _shutdown_event.is_set():
            server.handle_request()

        server.shutdown()

    _server_thread = threading.Thread(target=run_server, daemon=True, name="http-server")
    _server_thread.start()


def stop_server() -> None:
    """Stop the HTTP server."""
    global _shutdown_event
    _shutdown_event.set()
