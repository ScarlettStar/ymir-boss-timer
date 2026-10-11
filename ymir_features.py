"""Interface gamer v2: lista global, overlay e bandeja do Windows."""
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

BG = "#0b101d"
PANEL = "#19263b"
TEXT = "#edf4ff"
MUTED = "#96a9c6"
ACCENT = "#5ae2c0"
WARNING = "#ffca79"
PURPLE = "#a99dff"


def location(boss):
    if boss.get("category") == "Bosses Myrkheimr":
        return "Myrkheimr • " + (boss.get("channel") or "CHN 1")
    if boss.get("category") == "Bosses Fólkvangr":
        return "Fólkvangr • " + (boss.get("floor") or "P1")
    return "Universais"


def remaining_text(seconds):
    s = max(0, int(seconds + 0.999))
    hours, remain = divmod(s, 3600)
    minutes, sec = divmod(remain, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}" if hours else f"{minutes:02d}:{sec:02d}"


class YmirVisualMixin:
    def upcoming_bosses(self, now=None):
        if now is None:
            now = time.time()
        upcoming = [b for b in self.bosses if b.get("end", 0) > now]
        ready = [b for b in self.bosses if 0 < b.get("end", 0) <= now]
        return sorted(upcoming, key=lambda b: b["end"]) + sorted(
            ready, key=lambda b: b["end"], reverse=True)

    def build_upcoming_ui(self):
        tk.Label(self.upcoming_view, text="PRÓXIMOS RESPAWNS", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=16, pady=(18, 4))
        tk.Label(self.upcoming_view,
                 text="Todos os bosses por horário • Myrkheimr CHN 1/2 • Fólkvangr P1–P4",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(0, 12))
        style = ttk.Style(self)
        style.configure("Ymir.Treeview", background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, rowheight=32, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Ymir.Treeview.Heading", background="#26364e", foreground=ACCENT,
                        font=("Segoe UI", 10, "bold"))
        style.map("Ymir.Treeview", background=[("selected", "#355a64")],
                  foreground=[("selected", TEXT)])
        holder = tk.Frame(self.upcoming_view, bg=BG)
        holder.pack(fill="both", expand=True, padx=16, pady=6)
        self.upcoming_table = ttk.Treeview(
            holder, columns=("name", "where", "time", "born"),
            show="headings", selectmode="none", style="Ymir.Treeview")
        for key, heading, width in (
            ("name", "BOSS", 140),
            ("where", "REGIÃO / CANAL / PISO", 190),
            ("time", "FALTA", 102),
            ("born", "NASCE ÀS", 105),
        ):
            self.upcoming_table.heading(key, text=heading)
            self.upcoming_table.column(key, width=width, minwidth=65, stretch=True)
        sb = ttk.Scrollbar(holder, orient="vertical", command=self.upcoming_table.yview)
        self.upcoming_table.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.upcoming_table.pack(fill="both", expand=True)
        self.upcoming_table.tag_configure("ready", foreground=ACCENT)
        self.upcoming_table.tag_configure("soon", foreground=WARNING)

    def render_upcoming(self):
        if not hasattr(self, "upcoming_table"):
            return
        now = time.time()
        for iid in self.upcoming_table.get_children():
            self.upcoming_table.delete(iid)
        for b in self.upcoming_bosses(now):
            remain = b["end"] - now
            text = "DISPONÍVEL" if remain <= 0 else remaining_text(remain)
            tag = "ready" if remain <= 0 else ("soon" if remain <= 60 else "")
            self.upcoming_table.insert("", "end", values=(
                b["name"], location(b), text,
                datetime.fromtimestamp(b["end"]).strftime("%H:%M:%S")
            ), tags=(tag,) if tag else ())

    def toggle_overlay(self):
        if self.overlay is not None and self.overlay.winfo_exists():
            self.close_overlay()
            return
        win = tk.Toplevel(self)
        self.overlay = win
        win.title("Ymir • Gamer overlay")
        win.configure(bg=BG)
        win.overrideredirect(True)
        win.geometry("395x385+80+85")
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.90)
        head = tk.Frame(win, bg="#26364e")
        head.pack(fill="x")
        tk.Label(head, text="  ⚔  YMIR  •  PRÓXIMOS BOSSES",
                 bg="#26364e", fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", pady=8)
        tk.Button(head, text="✕", bg="#26364e", fg=TEXT, relief="flat",
                  command=self.close_overlay, cursor="hand2", width=3).pack(side="right")
        head.bind("<ButtonPress-1>", self.overlay_drag_start)
        head.bind("<B1-Motion>", self.overlay_drag_move)
        tk.Label(win, text="Arraste pelo topo para mover",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=12, pady=(5, 2))
        self.overlay_rows = []
        for i in range(6):
            frame = tk.Frame(win, bg=PANEL)
            frame.pack(fill="x", padx=8, pady=2)
            label = tk.Label(frame, bg=PANEL, fg=TEXT, anchor="w", justify="left",
                             font=("Segoe UI", 9))
            label.pack(side="left", fill="x", expand=True, padx=7, pady=4)
            timing = tk.Label(frame, bg=PANEL, fg=WARNING, anchor="e",
                              font=("Consolas", 10, "bold"))
            timing.pack(side="right", padx=8)
            self.overlay_rows.append((frame, label, timing))
        footer = tk.Frame(win, bg=BG)
        footer.pack(fill="x", padx=10, pady=(5, 2))
        tk.Label(footer, text="OPACIDADE", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left")
        scale = tk.Scale(footer, from_=50, to=100, orient="horizontal", showvalue=True,
                         bg=BG, fg=TEXT, highlightthickness=0, troughcolor=PANEL,
                         command=lambda value: win.attributes("-alpha", int(float(value)) / 100))
        scale.pack(side="right", fill="x", expand=True)
        scale.set(90)
        self.refresh_overlay()

    def overlay_drag_start(self, event):
        self._drag = (event.x_root, event.y_root,
                      self.overlay.winfo_x(), self.overlay.winfo_y())

    def overlay_drag_move(self, event):
        if self.overlay is not None and self.overlay.winfo_exists():
            sx, sy, ox, oy = self._drag
            self.overlay.geometry(f"+{ox + event.x_root - sx}+{oy + event.y_root - sy}")

    def close_overlay(self):
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.overlay = None
        self.overlay_rows = []

    def refresh_overlay(self):
        if self.overlay is None or not self.overlay.winfo_exists():
            return
        now = time.time()
        bosses = self.upcoming_bosses(now)
        for index, (frame, name, timing) in enumerate(self.overlay_rows):
            if index >= len(bosses):
                frame.pack_forget()
                continue
            b = bosses[index]
            remain = b["end"] - now
            name.config(text=f"{b['name'][:27]}\n{location(b)}")
            timing.config(text="PRONTO" if remain <= 0 else remaining_text(remain),
                          fg=ACCENT if remain <= 0 else (WARNING if remain <= 60 else TEXT))
            frame.pack(fill="x", padx=8, pady=2)

    def init_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), (11, 16, 29, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse((6, 6, 58, 58), fill=(90, 226, 192, 255))
            draw.text((19, 15), "Y", fill=(11, 16, 29, 255))
            menu = pystray.Menu(
                pystray.MenuItem("Abrir timer",
                                 lambda _icon, _item: self.tray_commands.put("show"), default=True),
                pystray.MenuItem("Mostrar overlay",
                                 lambda _icon, _item: self.tray_commands.put("overlay")),
                pystray.MenuItem("Sair",
                                 lambda _icon, _item: self.tray_commands.put("quit")))
            icon = pystray.Icon("YmirBossTimer", img, "Ymir Boss Timer", menu)
            self.tray_icon = icon
            threading.Thread(target=icon.run, daemon=True).start()
        except Exception:
            self.tray_icon = None

    def hide_to_tray(self):
        if self.tray_icon is not None:
            self.withdraw()
        else:
            self.iconify()

    def process_tray_commands(self):
        while True:
            try:
                action = self.tray_commands.get_nowait()
            except queue.Empty:
                break
            if action == "show":
                self.deiconify()
                self.lift()
            elif action == "overlay":
                if self.overlay is None or not self.overlay.winfo_exists():
                    self.toggle_overlay()
                else:
                    self.overlay.lift()
            elif action == "quit":
                self.quit_app()

    def signal_update_ready(self):
        marker = os.environ.get("YMIR_READY_MARKER", "")
        if marker:
            try:
                Path(marker).write_text(self.app_version, encoding="ascii")
            except OSError:
                pass
