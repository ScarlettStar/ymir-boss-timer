"""Quick channel views are account preferences, never changes to boss timers."""
import copy
import tkinter as tk
from tkinter import messagebox
from ymir_models import uses_channels
from ymir_theme import BG, PANEL, TEXT, MUTED, ACCENT, GamerButton

CHANNEL_VIEWS = ("Todos", "CHN 1", "CHN 2")


def channel_view_items(bosses, choice):
    if choice not in ("CHN 1", "CHN 2"):
        return list(bosses)
    return [b for b in bosses if not uses_channels(b.get("category")) or (b.get("channel") or "CHN 1") == choice]


class ChannelViewMixin:
    def current_channel_view(self):
        choice = self.profile_definition().get("channel_view", "Todos")
        return choice if choice in CHANNEL_VIEWS else "Todos"

    def channel_view_bosses(self, bosses):
        return channel_view_items(bosses, self.current_channel_view())

    def build_quick_channel_controls(self, parent, compact=False):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=10 if compact else 16, pady=(3, 4))
        tk.Label(row, text="Canal" if compact else "Myrk / Túmulo • canal:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8 if compact else 9)).pack(side="left", padx=(0, 8))
        buttons = self.__dict__.setdefault("channel_view_buttons", [])
        for choice in CHANNEL_VIEWS:
            button = GamerButton(row, text=choice, command=lambda value=choice: self.choose_channel(value),
                                 bg=PANEL, fg=TEXT, padx=8 if compact else 12, pady=4,
                                 font=("Segoe UI", 8 if compact else 9, "bold"))
            button.pack(side="left", padx=(0, 5))
            buttons.append((choice, button))
        if not compact:
            GamerButton(row, text="Copiar Túmulo → CHN 2", command=self.complete_tomb_dialog,
                        bg=PANEL, fg=ACCENT, padx=8, pady=4,
                        font=("Segoe UI", 9)).pack(side="right")
        self.refresh_channel_buttons()

    def refresh_channel_buttons(self):
        live = []
        for choice, button in self.__dict__.get("channel_view_buttons", []):
            if button.winfo_exists():
                selected = choice == self.current_channel_view()
                button.configure(bg=ACCENT if selected else PANEL, fg=BG if selected else TEXT)
                live.append((choice, button))
        self.channel_view_buttons = live

    def write_channel_preference(self, choice):
        if choice not in CHANNEL_VIEWS:
            raise ValueError("Selecione Todos, CHN 1 ou CHN 2.")
        if choice != self.current_channel_view():
            candidate = copy.deepcopy(self.profile_state)
            profile = next(p for p in candidate["profiles"] if p["id"] == self.active_profile_id())
            profile["channel_view"] = choice
            self.persist_profile_state(candidate)
        self.refresh_channel_buttons()

    def choose_channel(self, choice):
        try:
            self.write_channel_preference(choice)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Canal não alterado", str(exc), parent=self)
            return
        # Quick controls replace a previous advanced channel filter instead of contradicting it.
        if self.filter_place.get() in ("CHN 1", "CHN 2"):
            self.filter_place.set("Todos")
        self.apply_filters()
