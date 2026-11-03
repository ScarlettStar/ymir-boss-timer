"""Command-center layout for the desktop app; timer behavior stays in the app."""
import tkinter as tk
from ymir_theme import BG, PANEL, TEXT, MUTED, ACCENT, WARNING, BORDER, PURPLE, GamerButton

SIDEBAR = "#0e1526"


class CommandCenterMixin:
    def build_command_shell(self, version):
        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=172)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        emblem = tk.Canvas(self.sidebar, height=66, bg=SIDEBAR, highlightthickness=0)
        emblem.pack(fill="x", pady=(14, 0))
        emblem.create_polygon(86, 4, 112, 30, 86, 56, 60, 30, outline=ACCENT,
                              fill=PANEL, width=2)
        emblem.create_line(75, 19, 86, 31, 97, 19, fill=PURPLE, width=3)
        emblem.create_line(86, 31, 86, 44, fill=ACCENT, width=3)
        tk.Label(self.sidebar, text="YMIR", bg=SIDEBAR, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack()
        tk.Label(self.sidebar, text="B O S S   T I M E R", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8)).pack(pady=(0, 20))
        tk.Label(self.sidebar, text="NAVEGAÇÃO", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(0, 8))
        nav = tk.Frame(self.sidebar, bg=SIDEBAR)
        nav.pack(fill="x", padx=10)
        tk.Label(self.sidebar, text="FERRAMENTAS", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=14, pady=(22, 8))
        for title, action, color in (
            ("◈  Overlay gamer", self.toggle_overlay, PURPLE),
            ("◱  Modo compacto", self.open_compact, ACCENT),
            ("⊟  Minimizar", self.hide_to_tray, TEXT),
        ):
            GamerButton(self.sidebar, text=title, command=action, bg=SIDEBAR,
                        fg=color, anchor="w", padx=10, pady=8,
                        font=("Segoe UI", 9)).pack(fill="x", padx=10, pady=3)
        tk.Label(self.sidebar, text=f"v{version}\nAlertas em todas as regiões",
                 bg=SIDEBAR, fg=MUTED, justify="left",
                 font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=14, pady=14)
        GamerButton(self.sidebar, text="↓  Atualizações", command=self.updates_dialog,
                    bg=PANEL, fg=ACCENT, anchor="w", padx=10, pady=9,
                    font=("Segoe UI", 9)).pack(side="bottom", fill="x", padx=10)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        heading = tk.Frame(self.content, bg=BG)
        heading.pack(fill="x", padx=18, pady=(18, 10))
        tk.Label(heading, text="LEGEND OF YMIR  /  CONTROLE DE RESPAWNS",
                 bg=BG, fg=ACCENT, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.page_heading = tk.Label(heading, text="Central de combate", bg=BG, fg=TEXT,
                                     font=("Segoe UI", 23, "bold"))
        self.page_heading.pack(anchor="w", pady=(2, 0))
        self.compact_summary = tk.Label(heading, bg=BG, fg=MUTED, font=("Segoe UI", 9))

        hero = tk.Frame(self.content, bg=PANEL, highlightbackground=BORDER,
                        highlightthickness=1)
        hero.pack(fill="x", padx=16, pady=(0, 12))
        tk.Frame(hero, bg=PURPLE, height=3).grid(row=0, column=0, columnspan=2, sticky="ew")
        hero.columnconfigure(0, weight=1)
        tk.Label(hero, text="RADAR DE RESPAWNS  /  PRÓXIMO ALVO", bg=PANEL,
                 fg=PURPLE, font=("Segoe UI", 8, "bold")).grid(
                     row=1, column=0, sticky="w", padx=16, pady=(12, 4))
        self.target_name = tk.Label(hero, text="Cadastre seu primeiro boss", bg=PANEL,
                                    fg=TEXT, font=("Segoe UI", 16, "bold"),
                                    anchor="w", justify="left", wraplength=330)
        self.target_name.grid(row=2, column=0, sticky="w", padx=16)
        self.target_location = tk.Label(hero, text="Seus próximos respawns aparecem aqui",
                                        bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.target_location.grid(row=3, column=0, sticky="w", padx=16, pady=(4, 14))
        self.target_timer = tk.Label(hero, text="--:--", bg=PANEL, fg=ACCENT,
                                     font=("Consolas", 29, "bold"))
        self.target_timer.grid(row=1, column=1, rowspan=2, sticky="e", padx=(8, 18))
        self.target_state = tk.Label(hero, text="AGUARDANDO REGISTRO", bg=PANEL, fg=MUTED,
                                     font=("Segoe UI", 8, "bold"))
        self.target_state.grid(row=3, column=1, sticky="e", padx=(8, 18), pady=(4, 14))
        return nav

    def adapt_layout(self, event):
        if event.widget is not self:
            return
        if self.winfo_height() < 740 or self.winfo_width() < 900:
            self.dashboard_frame.pack_forget()
            self.compact_summary.pack(anchor="w", pady=(4, 0))
        else:
            self.compact_summary.pack_forget()
            view = {"timers": self.timer_view, "upcoming": self.upcoming_view,
                    "history": self.history_view}[self.active_tab]
            self.dashboard_frame.pack(fill="x", padx=16, pady=(2, 4), before=view)
