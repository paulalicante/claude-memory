"""
Watchdog Service for Otterly Memory.

Runs as a separate lightweight process that:
1. Monitors if the main Otterly Memory app is running
2. Shows Windows toast notification if it crashes
3. Optionally auto-restarts the app
4. Checks the HTTP server health endpoint

This ensures you're always notified if your memory backup system goes down.
"""

import subprocess
import sys
import time
import os
from datetime import datetime

# Windows toast notifications
try:
    from win10toast import ToastNotifier
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False

# Alternative: use plyer for cross-platform
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

import requests


# Configuration
CHECK_INTERVAL = 30  # seconds between checks
HEALTH_URL = "http://localhost:8765/api/health"
APP_PATH = r"G:\My Drive\MyProjects\ClaudeMemory"
PYTHON_PATH = r"C:\Python314\pythonw.exe"
AUTO_RESTART = True
MAX_RESTART_ATTEMPTS = 3
RESTART_COOLDOWN = 60  # seconds between restart attempts


class WatchdogService:
    def __init__(self):
        self.restart_attempts = 0
        self.last_restart_time = 0
        self.toaster = ToastNotifier() if HAS_TOAST else None
        self.running = True

    def log(self, message: str):
        """Log with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def notify(self, title: str, message: str, urgent: bool = False):
        """Send Windows notification."""
        self.log(f"NOTIFY: {title} - {message}")

        if HAS_TOAST:
            try:
                self.toaster.show_toast(
                    title,
                    message,
                    duration=10 if urgent else 5,
                    threaded=True
                )
            except Exception as e:
                self.log(f"Toast error: {e}")

        elif HAS_PLYER:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=10 if urgent else 5
                )
            except Exception as e:
                self.log(f"Plyer error: {e}")

    def check_health(self) -> bool:
        """Check if the HTTP server is responding."""
        try:
            response = requests.get(HEALTH_URL, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def check_process_running(self) -> bool:
        """Check if pythonw.exe is running with our app."""
        try:
            # Use tasklist to check for pythonw processes
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq pythonw.exe", "/FO", "CSV"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return "pythonw.exe" in result.stdout
        except Exception as e:
            self.log(f"Process check error: {e}")
            return False

    def restart_app(self) -> bool:
        """Attempt to restart Otterly Memory."""
        now = time.time()

        # Check cooldown
        if now - self.last_restart_time < RESTART_COOLDOWN:
            self.log("Restart cooldown active, skipping")
            return False

        # Check max attempts
        if self.restart_attempts >= MAX_RESTART_ATTEMPTS:
            self.notify(
                "Otterly Memory - CRITICAL",
                f"Failed to restart after {MAX_RESTART_ATTEMPTS} attempts. Manual intervention needed!",
                urgent=True
            )
            return False

        self.log("Attempting to restart Otterly Memory...")
        self.restart_attempts += 1
        self.last_restart_time = now

        try:
            # Start the app
            run_script = os.path.join(APP_PATH, "run.pyw")
            subprocess.Popen(
                [PYTHON_PATH, run_script],
                cwd=APP_PATH,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )

            # Wait a bit and check if it started
            time.sleep(5)

            if self.check_health():
                self.notify(
                    "Otterly Memory Restarted",
                    "The app was down but has been automatically restarted.",
                    urgent=False
                )
                self.restart_attempts = 0  # Reset on success
                return True
            else:
                self.log("Restart attempt failed - health check failed")
                return False

        except Exception as e:
            self.log(f"Restart error: {e}")
            return False

    def run(self):
        """Main watchdog loop."""
        self.log("Watchdog service started")
        self.log(f"Monitoring: {HEALTH_URL}")
        self.log(f"Check interval: {CHECK_INTERVAL}s")
        self.log(f"Auto-restart: {AUTO_RESTART}")

        # Initial notification
        self.notify(
            "Otterly Memory Watchdog",
            "Watchdog service is now monitoring the app.",
            urgent=False
        )

        consecutive_failures = 0

        while self.running:
            try:
                is_healthy = self.check_health()

                if is_healthy:
                    if consecutive_failures > 0:
                        self.log("App is back online")
                        self.notify(
                            "Otterly Memory Online",
                            "The app is responding normally again.",
                            urgent=False
                        )
                    consecutive_failures = 0

                else:
                    consecutive_failures += 1
                    self.log(f"Health check failed (consecutive: {consecutive_failures})")

                    if consecutive_failures >= 2:  # Confirm it's really down
                        self.notify(
                            "Otterly Memory DOWN!",
                            "The app is not responding. Your conversation backups may not be saved!",
                            urgent=True
                        )

                        if AUTO_RESTART:
                            self.restart_app()

                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                self.log("Watchdog stopped by user")
                break
            except Exception as e:
                self.log(f"Watchdog error: {e}")
                time.sleep(CHECK_INTERVAL)

        self.log("Watchdog service stopped")


def main():
    """Run the watchdog service."""
    service = WatchdogService()
    service.run()


if __name__ == "__main__":
    main()
