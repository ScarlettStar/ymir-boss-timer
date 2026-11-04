"""Visible modeless alerts, independent of whether Windows accepts a native toast."""
import ctypes
import math
import os
import time
import tkinter as tk
from tkinter import ttk
from ymir_theme import BG, PANEL, TEXT, MUTED, ACCENT, WARNING, BORDER, GamerButton


def countdown_text(deadline, now, variable=False):
    if not deadline:
        return ""
    remaining = max(0, math.ceil(deadline - now))
    if not remaining:
        return "PREVISÃO / CONFIRA NO JOGO" if variable else "BOSS DISPONÍVEL"
    hours, rest = divmod(remaining, 3600)
    minutes, seconds = divmod(rest, 60)
    clock = f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"
    return ("PREVISÃO EM ~" if variable else "NASCE EM ") + clock


def screen_workarea(root):
    if os.name == "nt":
        try:
            from ctypes import wintypes
            rect = wintypes.RECT()
            api = ctypes.windll.user32.SystemParametersInfoW
            api.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
            api.restype = wintypes.BOOL
            if api(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return rect.left, rect.top, rect.right, rect.bottom
        except (AttributeError, OSError, ctypes.ArgumentError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def show_without_activation(window):
    """Apply WS_EX_NOACTIVATE before mapping the Windows popup."""
    if os.name == "nt":
        try:
            from ctypes import wintypes
            user = ctypes.windll.user32
            user.GetParent.argtypes, user.GetParent.restype = [wintypes.HWND], wintypes.HWND
            handle = user.GetParent(window.winfo_id()) or window.winfo_id()
            getter = getattr(user, "GetWindowLongPtrW", user.GetWindowLongW)
            setter = getattr(user, "SetWindowLongPtrW", user.SetWindowLongW)
            getter.argtypes, getter.restype = [wintypes.HWND, ctypes.c_int], ctypes.c_ssize_t
            setter.argtypes, setter.restype = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t
            setter(handle, -20, getter(handle, -20) | 0x08000000 | 0x00000080)
            window.deiconify()
            user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user.SetWindowPos.restype = wintypes.BOOL
            # TOPMOST, NOACTIVATE, NOMOVE, NOSIZE, FRAMECHANGED, SHOWWINDOW.
            user.SetWindowPos(handle, wintypes.HWND(-1), 0, 0, 0, 0, 0x0073)
            return
        except (AttributeError, OSError, ctypes.ArgumentError):
            pass
    window.deiconify()


class BossAlertPanel:
    def __init__(self, root):
        self.root = root
        self.window = None
        self.entries = []
        self.countdown_labels = []
        self.tick_id = None
        self.close_at = 0

    def _create(self):
        win = self.window = tk.Toplevel(self.root)
        win.withdraw()
        win.title("Ymir • Alertas de bosses")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=PANEL, highlightbackground=ACCENT, highlightthickness=2)
        header = tk.Frame(win, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="⚔  ALERTAS DE BOSSES", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=10)
        GamerButton(header, text="✕", command=self.dismiss, bg=BG, fg=TEXT,
                    takefocus=False, padx=9).pack(side="right", padx=7)
        holder = tk.Frame(win, bg=PANEL)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=PANEL)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.body_id, width=e.width))
        self.footer = tk.Label(win, bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.footer.pack(fill="x", ipady=5)

    def push(self, payload):
        if self.window is None or not self.window.winfo_exists():
            self._create()
        now = time.monotonic()
        payload = {**payload, "received": now}
        self.entries = [payload] + [p for p in self.entries if p["key"] != payload["key"] and now - p["received"] < 20]
        self.entries = self.entries[:100]
        self.close_at = now + 20
        left, top, right, bottom = screen_workarea(self.root)
        width = max(240, min(440, right - left - 24))
        wrap = width - 48
        for child in self.body.winfo_children():
            child.destroy()
        self.countdown_labels = []
        for item in self.entries:
            card = tk.Frame(self.body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", padx=7, pady=5)
            tk.Label(card, text=item["title"], bg=PANEL, fg=WARNING,
                     font=("Segoe UI", 10, "bold"), wraplength=wrap, justify="left").pack(anchor="w", padx=11, pady=(9, 2))
            tk.Label(card, text=item["boss_name"], bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 14, "bold"), wraplength=wrap, justify="left").pack(anchor="w", padx=11)
            tk.Label(card, text=item["context"], bg=PANEL, fg=ACCENT,
                     font=("Segoe UI", 9), wraplength=wrap, justify="left").pack(anchor="w", padx=11, pady=(2, 4))
            label = tk.Label(card, bg=PANEL, fg=WARNING, font=("Consolas", 14, "bold"), wraplength=wrap, justify="left")
            label.pack(anchor="w", padx=11)
            self.countdown_labels.append((item, label))
            tk.Label(card, text=item["description"], bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9), wraplength=wrap, justify="left").pack(anchor="w", padx=11, pady=(3, 10))
        self.body.update_idletasks()
        available = max(140, min(430, bottom - top - 100))
        self.canvas.configure(width=width - 20, height=min(available, self.body.winfo_reqheight()))
        self.window.update_idletasks()
        height = min(bottom - top - 24, self.window.winfo_reqheight())
        x, y = right - width - 12, bottom - height - 12
        self.window.geometry(f"{width}x{height}{x:+d}{y:+d}")
        self.canvas.yview_moveto(0)
        show_without_activation(self.window)
        self._tick()

    def _tick(self):
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None
        if self.window is None or not self.window.winfo_exists() or not self.entries:
            return
        seconds = math.ceil(self.close_at - time.monotonic())
        if seconds <= 0:
            self.dismiss()
            return
        now = time.time()
        for item, label in self.countdown_labels:
            label.configure(text=countdown_text(item["deadline"], now, item["variable"]))
        self.footer.configure(text=f"{len(self.entries)} aviso(s) • fecha em {seconds}s • role para ver os demais")
        self.tick_id = self.root.after(1000, self._tick)

    def dismiss(self):
        if self.tick_id is not None:
            self.root.after_cancel(self.tick_id)
            self.tick_id = None
        self.entries = []
        self.countdown_labels = []
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def close(self):
        self.dismiss()
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None
