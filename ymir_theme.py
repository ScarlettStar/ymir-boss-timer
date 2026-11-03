"""Shared presentation helpers; no changes to timer data or update settings."""
import tkinter as tk

BG = "#090d18"
PANEL = "#141e32"
TEXT = "#edf4ff"
MUTED = "#9cacca"
ACCENT = "#52edcc"
WARNING = "#ffc66d"
DANGER = "#ff758f"
BORDER = "#2b3b58"
PURPLE = "#b5a0ff"


class GamerButton(tk.Button):
    """Lightweight hover/focus feedback without animation timers."""

    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("highlightbackground", BORDER)
        kwargs.setdefault("highlightcolor", ACCENT)
        kwargs.setdefault("borderwidth", 0)
        kwargs.setdefault("activebackground", "#263c54")
        kwargs.setdefault("activeforeground", TEXT)
        kwargs.setdefault("cursor", "hand2")
        super().__init__(master, **kwargs)
        self.bind("<Enter>", lambda _e: self.configure(highlightbackground=ACCENT), add="+")
        self.bind("<Leave>", lambda _e: self.configure(highlightbackground=BORDER), add="+")


def dashboard_counts(bosses, now):
    active = sum(b.get("end", 0) > now for b in bosses)
    ready = sum(0 < b.get("end", 0) <= now for b in bosses)
    soon = sum(0 < b.get("end", 0) - now <= 300 for b in bosses)
    return len(bosses), active, soon, ready


def respawn_progress(boss, now):
    end = boss.get("end", 0)
    if not end:
        return 0
    duration = max(1, boss.get("minutes", 1) * 60)
    return max(0, min(100, 100 * (1 - (end - now) / duration)))
