"""
System State Manager for runtime configuration persistence.
"""
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
import json
from utils import log


class StateManager:
    """Manage persistent system state across restarts."""

    def __init__(self, state_file: str = "data/system_state.json"):
        """
        Initialize state manager.

        Args:
            state_file: Path to JSON state file
        """
        self.state_file = Path(state_file)
        self._ensure_state_file()

    def _ensure_state_file(self):
        """Create state file with defaults if not exists."""
        if not self.state_file.exists():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            default_state = {
                "auto_refresh_enabled": True,
                "last_refresh_toggle": None,
                "refresh_schedule": "0 3 * * 1",  # Monday 3 AM
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            }

            self._save_state(default_state)
            log.info(f"Created default state file: {self.state_file}")

    def _load_state(self) -> dict:
        """Load state from JSON file."""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            log.error(f"State file corrupted: {e}. Using defaults.")
            return self._get_default_state()
        except Exception as e:
            log.error(f"Error loading state: {e}")
            return self._get_default_state()

    def _save_state(self, state: dict):
        """Save state to JSON file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log.error(f"Error saving state: {e}")

    def _get_default_state(self) -> dict:
        """Get default state dictionary."""
        return {
            "auto_refresh_enabled": True,
            "last_refresh_toggle": None,
            "refresh_schedule": "0 3 * * 1",
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from state.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        state = self._load_state()
        return state.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set a value in state.

        Args:
            key: State key
            value: Value to set
        """
        state = self._load_state()
        state[key] = value
        self._save_state(state)
        log.debug(f"State updated: {key} = {value}")

    def get_auto_refresh_status(self) -> bool:
        """
        Check if auto-refresh is enabled.

        Returns:
            True if enabled, False otherwise
        """
        return self.get("auto_refresh_enabled", True)

    def toggle_auto_refresh(self) -> bool:
        """
        Toggle auto-refresh on/off.

        Returns:
            New state (True = enabled, False = disabled)
        """
        current = self.get_auto_refresh_status()
        new_state = not current

        self.set("auto_refresh_enabled", new_state)
        self.set("last_refresh_toggle", datetime.now().isoformat())

        log.info(f"Auto-refresh {'enabled' if new_state else 'disabled'}")
        return new_state

    def enable_auto_refresh(self):
        """Enable auto-refresh."""
        if not self.get_auto_refresh_status():
            self.set("auto_refresh_enabled", True)
            self.set("last_refresh_toggle", datetime.now().isoformat())
            log.info("Auto-refresh enabled")

    def disable_auto_refresh(self):
        """Disable auto-refresh."""
        if self.get_auto_refresh_status():
            self.set("auto_refresh_enabled", False)
            self.set("last_refresh_toggle", datetime.now().isoformat())
            log.info("Auto-refresh disabled")

    def get_refresh_schedule(self) -> str:
        """
        Get refresh schedule (cron format).

        Returns:
            Cron schedule string
        """
        return self.get("refresh_schedule", "0 3 * * 1")

    def set_refresh_schedule(self, schedule: str):
        """
        Set refresh schedule.

        Args:
            schedule: Cron schedule string
        """
        self.set("refresh_schedule", schedule)
        log.info(f"Refresh schedule updated: {schedule}")

    def get_last_toggle_time(self) -> Optional[str]:
        """
        Get timestamp of last auto-refresh toggle.

        Returns:
            ISO format timestamp or None
        """
        return self.get("last_refresh_toggle")

    def get_full_state(self) -> dict:
        """
        Get entire state dictionary.

        Returns:
            Complete state dict
        """
        return self._load_state()

    def reset_to_defaults(self):
        """Reset state to default values."""
        default_state = self._get_default_state()
        self._save_state(default_state)
        log.info("State reset to defaults")
