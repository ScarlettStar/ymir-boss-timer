"""Search and presentation preferences never limit the global alert monitor."""
import time
import unicodedata
import tkinter as tk
from tkinter import ttk, messagebox
from ymir_theme import BG, PANEL, TEXT, MUTED, ACCENT, PURPLE, GamerButton


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value).casefold())
                   if not unicodedata.combining(c))


def select_bosses(bosses, now, query="", region="Todas", place="Todos", status="Todos", favorites=False, kind="Todas"):
    result = []
    for boss in bosses:
        haystack = normalized(" ".join(str(boss.get(k, "")) for k in ("name", "category", "channel", "floor", "kind")))
        if any(word not in haystack for word in normalized(query).split()):
            continue
        if region != "Todas" and boss.get("category") != region:
            continue
        if place != "Todos" and place not in (boss.get("channel"), boss.get("floor")):
            continue
        if kind != "Todas" and boss.get("kind", "Boss") != kind:
            continue
        if favorites and not boss.get("favorite", False):
            continue
        end = boss.get("end", 0)
        if status == "Ativos" and end <= now:
            continue
        if status == "Disponíveis" and not 0 < end <= now:
            continue
        if status == "Aguardando" and end:
            continue
        if status == "Em até 5 min" and not 0 < end - now <= 300:
            continue
        result.append(boss)
    # Keep original order within each priority; channels/floors have independent favorites.
    return sorted(result, key=lambda b: not b.get("favorite", False))


def previous_death_timestamp(minutes_ago, now):
    if isinstance(minutes_ago, bool) or not isinstance(minutes_ago, int) or not 0 <= minutes_ago <= 10080:
        raise ValueError("Informe de 0 a 10080 minutos inteiros.")
    return now - minutes_ago * 60


class SmartTimersMixin:
    def build_filter_bar(self, categories, places):
        self.search_query = tk.StringVar(value="")
        self.filter_region = tk.StringVar(value="Todas")
        self.filter_place = tk.StringVar(value="Todos")
        self.filter_status = tk.StringVar(value="Todos")
        self.filter_kind = tk.StringVar(value="Todas")
        self.favorites_only = tk.BooleanVar(value=False)
        self._filter_options = (categories, places)
        self._filter_after = None
        self._filter_window = None
        bar = tk.Frame(self.timer_view, bg=BG)
        bar.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(bar, text="Buscar", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        entry = tk.Entry(bar, textvariable=self.search_query, bg=PANEL, fg=TEXT,
                         insertbackground=TEXT, relief="flat", font=("Segoe UI", 10), width=14)
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Checkbutton(bar, text="Só favoritos", variable=self.favorites_only,
                       command=self.apply_filters, bg=BG, fg=ACCENT, selectcolor=PANEL,
                       activebackground=BG, activeforeground=TEXT).pack(side="left", padx=6)
        GamerButton(bar, text="Filtros", command=self.filters_dialog, bg=PANEL,
                    fg=PURPLE, padx=8, pady=4).pack(side="left")
        GamerButton(bar, text="Limpar", command=self.clear_filters, bg=BG,
                    fg=MUTED, padx=8, pady=4).pack(side="left", padx=(5, 0))
        self.search_query.trace_add("write", self.queue_filter_refresh)
        self.build_quick_channel_controls(self.timer_view)

    def queue_filter_refresh(self, *_):
        if self._filter_after is not None:
            self.after_cancel(self._filter_after)
        self._filter_after = self.after(180, self.apply_filters)

    def filtered_bosses(self, bosses=None, now=None):
        values = self.__dict__
        if "search_query" not in values:
            return self.channel_view_bosses(self.profile_bosses() if bosses is None else bosses)
        return self.channel_view_bosses(select_bosses(self.profile_bosses() if bosses is None else bosses,
                             time.time() if now is None else now,
                             self.search_query.get(), self.filter_region.get(), self.filter_place.get(),
                             self.filter_status.get(), self.favorites_only.get(), self.filter_kind.get()))

    def filters_active(self):
        return "search_query" in self.__dict__ and bool(
            self.search_query.get().strip() or self.filter_region.get() != "Todas"
            or self.filter_place.get() != "Todos" or self.filter_status.get() != "Todos"
            or self.filter_kind.get() != "Todas" or self.favorites_only.get() or self.current_channel_view() != "Todos")

    def apply_filters(self):
        if (self.filter_place.get() in ("CHN 1", "CHN 2") and self.current_channel_view() != "Todos"
                and self.filter_place.get() != self.current_channel_view()):
            try:
                self.write_channel_preference("Todos")
            except OSError as exc:
                messagebox.showerror("Canal não alterado", str(exc), parent=self)
        if self._filter_after is not None:
            self.after_cancel(self._filter_after)
            self._filter_after = None
        # Search results must be discoverable even if the region was previously folded.
        if self.filters_active():
            self.collapsed.update({key: False for key in self.collapsed})
        self.render()
        self.canvas.yview_moveto(0)

    def clear_filters(self, reset_channel=True):
        self.search_query.set("")
        self.filter_region.set("Todas")
        self.filter_place.set("Todos")
        self.filter_status.set("Todos")
        self.filter_kind.set("Todas")
        self.favorites_only.set(False)
        if reset_channel:
            try:
                self.write_channel_preference("Todos")
            except OSError as exc:
                messagebox.showerror("Canal não alterado", str(exc), parent=self)
        self.apply_filters()

    def filters_dialog(self):
        if self._filter_window is not None and self._filter_window.winfo_exists():
            self._filter_window.lift()
            return
        win = self._filter_window = tk.Toplevel(self)
        win.title("Filtrar bosses")
        win.configure(bg=BG)
        win.geometry("370x350")
        win.transient(self)
        categories, places = self._filter_options
        for title, variable, choices in (
            ("Região", self.filter_region, ("Todas", *categories)),
            ("Canal / piso", self.filter_place, ("Todos", *places)),
            ("Categoria", self.filter_kind, ("Todas", *self.kind_choices())),
            ("Status", self.filter_status, ("Todos", "Ativos", "Disponíveis", "Aguardando", "Em até 5 min")),
        ):
            tk.Label(win, text=title, bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(10, 3))
            combo = ttk.Combobox(win, textvariable=variable, values=choices, state="readonly")
            combo.pack(fill="x", padx=18)
            combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_filters())
        GamerButton(win, text="Concluir", command=win.destroy, bg=ACCENT,
                    fg=BG, pady=6).pack(fill="x", padx=18, pady=15)

    def toggle_favorite(self, boss):
        boss["favorite"] = not boss.get("favorite", False)
        self.save()
        self.render()
        self.refresh_overlay()

    def overlay_bosses(self, now=None):
        return sorted(self.upcoming_bosses(now, all_profiles=True), key=lambda b: not b.get("favorite", False))

    def previous_death_dialog(self, boss):
        win = tk.Toplevel(self)
        win.title("Registrar morte anterior")
        win.configure(bg=BG)
        win.geometry("400x280")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=boss["name"], bg=BG, fg=TEXT,
                 font=("Segoe UI", 14, "bold"), wraplength=360).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(win, text="Morreu há quantos minutos?", bg=BG, fg=MUTED).pack(anchor="w", padx=18)
        value = tk.StringVar(value="0")
        entry = tk.Entry(win, textvariable=value, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                         font=("Consolas", 18), relief="flat")
        entry.pack(fill="x", padx=18, pady=8, ipady=5)
        entry.focus_set()
        entry.select_range(0, "end")
        tk.Label(win, text="Ex.: 7 = morreu há 7 minutos.\nO respawn usa o horário da morte, não o de agora.",
                 justify="left", bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(0, 12))
        def submit():
            try:
                raw = value.get().strip()
                if not raw.isdecimal():
                    raise ValueError("Informe minutos inteiros de 0 a 10080.")
                killed_at = previous_death_timestamp(int(raw), time.time())
                self.record_kill(boss, killed_at)
            except ValueError as exc:
                messagebox.showwarning("Horário inválido", str(exc), parent=win)
                return
            win.destroy()
        GamerButton(win, text="Registrar morte", command=submit, bg=ACCENT, fg=BG,
                    pady=7).pack(fill="x", padx=18)
        win.bind("<Return>", lambda _e: submit())
        win.bind("<Escape>", lambda _e: win.destroy())
