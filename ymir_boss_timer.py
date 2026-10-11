import json
import hashlib
import shutil
import queue
import re
import subprocess
import threading
import urllib.request
import urllib.error
import tempfile
import os
import sys
import time
import uuid
import ctypes
from ymir_features import YmirVisualMixin, location as boss_location
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "Ymir Boss Timer"
APP_VERSION = "2.1.0"
DEFAULT_UPDATE_REPO = "ScarlettStar/ymir-boss-timer"
NEAR_RESPAWN_SECONDS = 5 * 60  # Próximos 5 minutos
CATEGORIES = ("Bosses Universais", "Bosses Myrkheimr", "Bosses Fólkvangr")
MYRKHEIMR = "Bosses Myrkheimr"
CHANNELS = ("CHN 1", "CHN 2")
FOLKVANGR = "Bosses Fólkvangr"
FLOORS = ("P1", "P2", "P3", "P4 UNIVERSAL")


def channel_group_key(channel):
    return f"{MYRKHEIMR} • {channel}"


def floor_group_key(floor):
    return f"{FOLKVANGR} • {floor}"


def clone_for_floor(boss, floor):
    """Cópia independente do mesmo boss em outro piso, sem inventar kill."""
    return {**boss, "id": uuid.uuid4().hex, "floor": floor,
            "end": 0, "last_kill": 0, "warned_for": 0, "finished_for": 0}


def boss_location(boss):
    category = boss.get("category", CATEGORIES[0])
    if category == MYRKHEIMR:
        return f"Myrkheimr • {boss.get('channel') or CHANNELS[0]}"
    if category == FOLKVANGR:
        return f"Fólkvangr • {boss.get('floor') or FLOORS[0]}"
    return "Universais"


def backup_data():
    """Backups locais independentes do EXE; nunca alteram os arquivos originais."""
    files = (DATA_FILE, HISTORY_FILE, UPDATE_SETTINGS)
    if not any(p.exists() for p in files):
        return None
    backup_root = DATA_DIR / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    dest = backup_root / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest.mkdir()
    try:
        for path in files:
            if path.is_file():
                shutil.copy2(path, dest / path.name)
    except OSError:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    # Conservar os 12 backups mais recentes.
    for old in sorted([p for p in backup_root.iterdir() if p.is_dir()], reverse=True)[12:]:
        shutil.rmtree(old, ignore_errors=True)
    return dest


def clone_for_channel(boss, channel):
    """Cria o mesmo boss no outro canal, com timer independente e ainda não iniciado."""
    return {**boss, "id": uuid.uuid4().hex, "channel": channel,
            "end": 0, "last_kill": 0, "warned_for": 0, "finished_for": 0}


def boss_alert_label(boss):
    return f"{boss['name']} • {boss_location(boss)}"
DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "YmirBossTimer"
DATA_FILE = DATA_DIR / "bosses.json"
HISTORY_FILE = DATA_DIR / "history.json"
UPDATE_SETTINGS = DATA_DIR / "updates.json"
MAX_HISTORY = 1000
BG = "#0b101d"
PANEL = "#19263b"
TEXT = "#edf4ff"
MUTED = "#96a9c6"
ACCENT = "#5ae2c0"
WARNING = "#ffca79"
DANGER = "#ff748e"
BORDER = "#30425b"
PURPLE = "#a99dff"


def format_seconds(seconds):
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


class BossTimerApp(YmirVisualMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("830x800")
        self.minsize(680, 450)
        self.configure(bg=BG)
        self._channel_migrated = False
        self._floor_migrated = False
        try:
            backup_data()  # Antes de qualquer migração ou gravação de dados.
        except OSError:
            pass
        self.last_backup_at = time.time()
        self.bosses = self.load()
        self.history = self.load_history()
        self.active_tab = "timers"
        self.alerted = set()
        self.warning_alerted = set()
        self.always_on_top = tk.BooleanVar(value=False)
        self.warning_minutes = tk.IntVar(value=1)
        self.compact = None
        self.compact_labels = {}
        self.overlay = None
        self.overlay_rows = []
        self.tray_icon = None
        self.tray_commands = queue.SimpleQueue()
        self.last_upcoming_refresh = 0
        self.app_version = APP_VERSION
        self.category_headers = []
        self.collapsed = {category: False for category in CATEGORIES}
        self.collapsed.update({channel_group_key(ch): False for ch in CHANNELS})
        self.collapsed.update({floor_group_key(f): False for f in FLOORS})
        self.category_var = tk.StringVar(value=CATEGORIES[0])
        self.update_busy = False
        self.latest_release = None
        self.update_repo = self.read_update_repo()
        self.auto_update_enabled = tk.BooleanVar(value=self.read_auto_update())
        self.last_update_check = 0
        self.auto_update_idle_since = time.time()
        self.build_ui()
        self.after(1400, self.init_tray)
        self.after(650, self.signal_update_ready)
        if self._channel_migrated or self._floor_migrated:
            self.save()  # Evita refazer migrações em inicializações posteriores.
        self.after(3000, lambda: self.check_updates(silent=True))
        self.render()
        self.render_history()
        self.tick()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def read_update_repo(self):
        try:
            data = json.loads(UPDATE_SETTINGS.read_text(encoding="utf-8"))
            repo = data.get("github_repo", "")
            return repo if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) else DEFAULT_UPDATE_REPO
        except (OSError, ValueError, TypeError):
            return DEFAULT_UPDATE_REPO

    def read_auto_update(self):
        try:
            data = json.loads(UPDATE_SETTINGS.read_text(encoding="utf-8"))
            return data.get("auto_update", True) is not False
        except (OSError, ValueError, TypeError):
            return True

    def save_update_repo(self, repository):
        repository = repository.strip().removeprefix("https://github.com/").strip("/")
        if repository and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            messagebox.showerror("Repositório inválido", "Use usuario/repositorio (ex.: equipe/ymir-timer).")
            return False
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        UPDATE_SETTINGS.write_text(json.dumps({"github_repo": repository or DEFAULT_UPDATE_REPO,
                                               "auto_update": self.auto_update_enabled.get()}, indent=2),
                                   encoding="utf-8")
        self.update_repo = repository or DEFAULT_UPDATE_REPO
        self.latest_release = None
        return True

    def updates_dialog(self):
        win = tk.Toplevel(self)
        win.title("Atualizações • Ymir Boss Timer")
        win.geometry("530x345")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        tk.Label(win, text=f"ATUALIZAÇÕES  •  v{APP_VERSION}", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(win, text="Repositório GitHub (usuario/repositorio):", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18)
        repo_entry = tk.Entry(win, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                              relief="flat", font=("Segoe UI", 11))
        repo_entry.insert(0, self.update_repo)
        repo_entry.pack(fill="x", padx=18, pady=(5, 12), ipady=8)
        tk.Checkbutton(win, text="Instalar atualizações automaticamente quando não houver timers ativos",
                       variable=self.auto_update_enabled, bg=BG, fg=TEXT, selectcolor=PANEL,
                       activebackground=BG, activeforeground=TEXT,
                       command=lambda: self.save_update_repo(repo_entry.get()),
                       font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 5))
        status = tk.StringVar(value="Verificando o GitHub automaticamente a cada 30 minutos.")
        tk.Label(win, textvariable=status, bg=BG, fg=WARNING, wraplength=485,
                 justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=5)
        buttons = tk.Frame(win, bg=BG)
        buttons.pack(fill="x", padx=18, pady=15)
        def save_and_check():
            if self.save_update_repo(repo_entry.get()):
                self.check_updates(silent=False, status_var=status)
        tk.Button(buttons, text="Salvar e verificar", command=save_and_check, bg=ACCENT, fg=BG,
                  relief="flat", padx=12, pady=10, font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(buttons, text="Instalar atualização", command=lambda: self.install_update(status),
                  bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=10).pack(side="left", padx=10)
        tk.Label(win, text="A instalação exige um .exe gerado pelo GERAR_EXE.bat.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18)

    @staticmethod
    def version_tuple(value):
        found = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", value.strip(), re.IGNORECASE)
        return tuple(map(int, (found.group(1), found.group(2), found.group(3) or "0"))) if found else None

    def check_updates(self, silent=False, status_var=None):
        if self.update_busy:
            return
        if not self.update_repo:
            if not silent:
                (status_var.set("Defina um repositório GitHub para ativar as atualizações.") if status_var else
                 messagebox.showinfo("Atualizações", "Configure o repositório GitHub em Atualizações."))
            return
        self.update_busy = True
        self.last_update_check = time.time()
        if status_var:
            status_var.set("Verificando o GitHub Releases...")
        def work():
            try:
                url = f"https://api.github.com/repos/{self.update_repo}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": f"YmirBossTimer/{APP_VERSION}",
                                                           "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(req, timeout=12) as response:
                    data = json.load(response)
                version = self.version_tuple(data.get("tag_name", ""))
                if not version:
                    raise ValueError("A versão do Release deve ser v1.8.0, por exemplo.")
                if version <= self.version_tuple(APP_VERSION):
                    self.after(0, lambda: self._update_feedback("Seu aplicativo já está atualizado.", silent, status_var))
                    return
                assets = {x.get("name", ""): x.get("browser_download_url", "") for x in data.get("assets", [])}
                if not assets.get("YmirBossTimer.exe") or not assets.get("YmirBossTimer.exe.sha256"):
                    raise ValueError("Release sem YmirBossTimer.exe e YmirBossTimer.exe.sha256.")
                info = {"version": data["tag_name"], "exe": assets["YmirBossTimer.exe"],
                        "sha256": assets["YmirBossTimer.exe.sha256"]}
                self.after(0, lambda: self._update_found(info, silent, status_var))
            except (ValueError, OSError, urllib.error.URLError, KeyError) as exc:
                self.after(0, lambda err=str(exc): self._update_feedback(f"Falha na verificação: {err}", silent, status_var))
            finally:
                self.after(0, lambda: setattr(self, "update_busy", False))
        threading.Thread(target=work, daemon=True).start()

    def _update_feedback(self, message, silent, status_var):
        if status_var:
            try: status_var.set(message)
            except tk.TclError: pass
        elif not silent:
            messagebox.showinfo("Atualizações", message)

    def _update_found(self, info, silent, status_var):
        self.latest_release = info
        text = f"Nova versão {info['version']} disponível."
        if status_var:
            try:
                status_var.set(text + " Atualização automática quando estiver ocioso.")
            except tk.TclError:
                pass
        elif not silent:
            messagebox.showinfo("Atualização disponível", text + "\nAbra Atualizações para instalar.")
        elif not self.auto_update_enabled.get():
            messagebox.showinfo("Atualização disponível", text + "\nAbra Atualizações para instalar.")

    def install_update(self, status_var=None, auto=False):
        info = self.latest_release
        if not info:
            if not auto:
                messagebox.showinfo("Atualizações", "Clique primeiro em Salvar e verificar.")
            return
        if not getattr(sys, "frozen", False) or os.name != "nt":
            if not auto:
                messagebox.showinfo("Atualizações", "Instalação direta requer o executável Windows (.exe).")
            return
        if self.update_busy:
            return
        if auto and any(b.get("end", 0) > time.time() for b in self.bosses):
            return  # Nunca interromper respawns em andamento.
        if not auto and not messagebox.askyesno(
            "Instalar atualização", f"Instalar {info['version']}? O aplicativo reiniciará e seus dados serão preservados."
        ):
            return
        self.update_busy = True
        if status_var:
            status_var.set("Baixando e verificando SHA-256...")
        def work():
            stage = None
            try:
                def req(url):
                    if not url.startswith("https://github.com/") and not url.startswith(
                        "https://objects.githubusercontent.com/"
                    ):
                        raise ValueError("URL de download fora dos servidores GitHub.")
                    return urllib.request.Request(url, headers={"User-Agent": f"YmirBossTimer/{APP_VERSION}"})
                with urllib.request.urlopen(req(info["sha256"]), timeout=25) as res:
                    checksum_text = res.read(2048).decode("utf-8").strip()
                match = re.search(r"\b[a-fA-F0-9]{64}\b", checksum_text)
                if not match:
                    raise ValueError("SHA-256 inválido.")
                target = Path(sys.executable).resolve()
                stage = target.with_name(target.name + ".new")
                digest = hashlib.sha256()
                total_bytes = 0
                with urllib.request.urlopen(req(info["exe"]), timeout=60) as res, stage.open("wb") as output:
                    while True:
                        chunk = res.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        digest.update(chunk)
                        total_bytes += len(chunk)
                        if total_bytes > 150 * 1024 * 1024:
                            raise ValueError("Download excedeu o limite de 150 MB.")
                if total_bytes < 200_000 or digest.hexdigest().lower() != match.group(0).lower():
                    raise ValueError("O executável está incompleto ou seu SHA-256 não confere.")
                with stage.open("rb") as binary:
                    if binary.read(2) != b"MZ":
                        raise ValueError("O arquivo baixado não é um executável Windows.")
                self.after(0, lambda: self._launch_update(stage, target))
            except (OSError, ValueError, urllib.error.URLError) as exc:
                if stage is not None:
                    try:
                        stage.unlink(missing_ok=True)
                    except OSError:
                        pass
                self.after(0, lambda err=str(exc): self._update_failed(err))
        threading.Thread(target=work, daemon=True).start()

    def _update_failed(self, err):
        self.update_busy = False
        messagebox.showerror("Falha na atualização", err)

    def _launch_update(self, stage, target):
        """Troca o EXE, aguardando sinal real da interface e restaurando em falhas."""
        script = Path(tempfile.gettempdir()) / f"ymir-update-{os.getpid()}.ps1"
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        backup = target.with_name(target.name + ".previous")
        ready = target.with_name(target.name + ".ready")
        logfile = DATA_DIR / "update.log"
        expected = str(self.latest_release["version"]).removeprefix("v")
        ps = r'''
$ErrorActionPreference = "Stop"
$target = __TARGET__
$stage = __STAGE__
$backup = __BACKUP__
$marker = __MARKER__
$logfile = __LOGFILE__
$expected = __EXPECTED__
$parentId = __PARENT_ID__
$child = $null
$swapped = $false
function Write-UpdateLog([string]$message) {
  try {
    Add-Content -LiteralPath $logfile -Encoding UTF8 -Value (
      (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " | " + $message
    )
  } catch {}
}
try {
  Write-UpdateLog "Iniciando atualização para $expected"
  try { Wait-Process -Id $parentId -Timeout 90 -ErrorAction SilentlyContinue } catch {}
  Start-Sleep -Milliseconds 900
  if (-not (Test-Path -LiteralPath $stage)) { throw "Executável baixado não encontrado." }
  if (-not (Test-Path -LiteralPath $target)) { throw "Executável original não encontrado." }
  # O backup é copiado primeiro e permanece intacto até a inicialização ter sucesso.
  Copy-Item -LiteralPath $target -Destination $backup -Force -ErrorAction Stop
  Move-Item -LiteralPath $stage -Destination $target -Force -ErrorAction Stop
  $swapped = $true
  Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
  $env:YMIR_READY_MARKER = $marker
  $child = Start-Process -FilePath $target -PassThru -ErrorAction Stop
  Write-UpdateLog "Executável iniciado. Aguardando confirmação da interface."
  $readyOk = $false
  # O PyInstaller --onefile pode iniciar um processo secundário: não confiar
  # no estado do PID retornado por Start-Process como prova de falha.
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path -LiteralPath $marker) {
      try {
        $written = (Get-Content -LiteralPath $marker -Raw -Encoding ASCII).Trim()
        if ($written -eq $expected) {
          $readyOk = $true
          break
        }
      } catch {}
    }
  }
  if (-not $readyOk) {
    throw "O aplicativo não confirmou a versão $expected após 90 segundos."
  }
  Write-UpdateLog "Atualização confirmada: versão $expected iniciou normalmente."
  Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
  exit 0
} catch {
  $reason = $_.Exception.Message
  Write-UpdateLog "Falha: $reason"
  Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
  $env:YMIR_READY_MARKER = ""
  $restored = $false
  if ($swapped -and (Test-Path -LiteralPath $backup)) {
    # Encerra os processos iniciados do EXE novo para permitir substituição.
    try {
      Get-CimInstance Win32_Process -Filter "Name='YmirBossTimer.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -eq $target } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    } catch {}
    try { if ($child) { Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue } } catch {}
    Start-Sleep -Seconds 2
    for ($retry = 0; $retry -lt 10; $retry++) {
      try {
        Copy-Item -LiteralPath $backup -Destination $target -Force -ErrorAction Stop
        if ((Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash -eq
            (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash) {
          $restored = $true
          break
        }
      } catch {
        Start-Sleep -Seconds 2
      }
    }
  } elseif (-not $swapped -and (Test-Path -LiteralPath $target)) {
    $restored = $true  # A atualização falhou antes de substituir o EXE.
  }
  if ($restored) {
    Write-UpdateLog "Executável antigo confirmado/restaurado."
    try { Start-Process -FilePath $target -ErrorAction Stop } catch {
      Write-UpdateLog "Não foi possível reabrir a versão anterior: $($_.Exception.Message)"
    }
  } else {
    Write-UpdateLog "Não foi possível confirmar a restauração. Backup em: $backup"
    if (Test-Path -LiteralPath $backup) {
      try { Start-Process -FilePath $backup -ErrorAction Stop } catch {}
    }
  }
  try {
    Add-Type -AssemblyName System.Windows.Forms
    if ($restored) {
      [System.Windows.Forms.MessageBox]::Show(
        "A nova versão não iniciou corretamente. A anterior foi restaurada. Detalhes em: $logfile",
        "Ymir Boss Timer"
      ) | Out-Null
    } else {
      [System.Windows.Forms.MessageBox]::Show(
        "A atualização falhou. Consulte o log: $logfile e o backup: $backup",
        "Ymir Boss Timer"
      ) | Out-Null
    }
  } catch {}
}
'''
        ps = (ps.replace("__TARGET__", quote(target))
                .replace("__STAGE__", quote(stage))
                .replace("__BACKUP__", quote(backup))
                .replace("__MARKER__", quote(ready))
                .replace("__LOGFILE__", quote(logfile))
                .replace("__EXPECTED__", quote(expected))
                .replace("__PARENT_ID__", str(os.getpid())))
        # utf-8-sig evita acentos corrompidos no Windows PowerShell 5.1.
        script.write_text(ps, encoding="utf-8-sig")
        try:
            subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True)
            self.quit_app()
        except OSError as exc:
            self._update_failed(str(exc))

    def load(self):
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                clean = []
                for x in data:
                    if not isinstance(x, dict):
                        continue
                    name = str(x.get("name", "")).strip()[:60]
                    minutes = int(x.get("minutes", 0))
                    if not name or not 1 <= minutes <= 10080:
                        continue
                    category = x.get("category") if x.get("category") in CATEGORIES else CATEGORIES[0]
                    channel = x.get("channel") if x.get("channel") in CHANNELS else CHANNELS[0]
                    floor = x.get("floor") if x.get("floor") in FLOORS else FLOORS[0]
                    boss = {"id": str(x.get("id", uuid.uuid4().hex)), "name": name,
                            "minutes": minutes, "category": category,
                            "channel": channel if category == MYRKHEIMR else "",
                            "floor": floor if category == FOLKVANGR else "",
                            "end": float(x.get("end", 0)),
                            "warned_for": float(x.get("warned_for", 0)),
                            "finished_for": float(x.get("finished_for", 0)),
                            "last_kill": float(x.get("last_kill", 0))}
                    clean.append(boss)
                    if category == MYRKHEIMR and x.get("channel") not in CHANNELS:
                        clean.append(clone_for_channel(boss, CHANNELS[1]))
                        self._channel_migrated = True
                    if category == FOLKVANGR and x.get("floor") not in FLOORS:
                        for extra_floor in FLOORS[1:]:
                            clean.append(clone_for_floor(boss, extra_floor))
                        self._floor_migrated = True
                return clean
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return []

    def load_history(self):
        try:
            with HISTORY_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict) and
                        all(k in r for k in ("name", "category", "killed_at", "respawn_at"))][-MAX_HISTORY:]
        except (OSError, ValueError, TypeError):
            pass
        return []

    def save_history(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = HISTORY_FILE.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self.history[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)
            tmp.replace(HISTORY_FILE)
        except OSError as e:
            messagebox.showerror("Histórico", f"Não foi possível salvar o histórico:\n{e}")

    def switch_tab(self, tab):
        self.active_tab = tab
        for view in (self.timer_view, self.history_view, self.upcoming_view):
            view.pack_forget()
        selected = {"timers": self.timer_view, "history": self.history_view,
                    "upcoming": self.upcoming_view}[tab]
        selected.pack(fill="both", expand=True)
        if tab == "history":
            self.render_history()
        elif tab == "upcoming":
            self.render_upcoming()
        for key, button in (("timers", self.tab_timers), ("history", self.tab_history),
                            ("upcoming", self.tab_upcoming)):
            button.config(bg=ACCENT if key == tab else PANEL,
                          fg=BG if key == tab else TEXT)

    def render_history(self):
        if not hasattr(self, "history_rows"):
            return
        for child in self.history_rows.winfo_children():
            child.destroy()
        self.history_count.config(text=f"{len(self.history)} registros de derrotas")
        if not self.history:
            tk.Label(self.history_rows, text="Nenhuma derrota registrada ainda.\nClique em 'Boss morreu / Iniciar' para registrar a primeira.",
                     fg=MUTED, bg=BG, font=("Segoe UI", 11), pady=32, justify="center").pack(fill="x")
            return
        for index, r in enumerate(reversed(self.history)):
            row = tk.Frame(self.history_rows, bg=PANEL if index % 2 == 0 else BG,
                           highlightbackground=BORDER, highlightthickness=1)
            row.pack(fill="x", pady=3)
            name = tk.Frame(row, bg=row.cget("bg"))
            name.pack(fill="x", padx=12, pady=(9, 2))
            tk.Label(name, text=r["name"], fg=TEXT, bg=row.cget("bg"),
                     font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left")
            tk.Label(name, text=(f"{r['category']} • {r.get('channel', CHANNELS[0])}" if r["category"] == MYRKHEIMR else (f"{r['category']} • {r.get('floor', FLOORS[0])}" if r["category"] == FOLKVANGR else r["category"])), fg=PURPLE, bg=row.cget("bg"),
                     font=("Segoe UI", 9), anchor="e").pack(side="right")
            details = tk.Frame(row, bg=row.cget("bg"))
            details.pack(fill="x", padx=12, pady=(1, 10))
            kill = datetime.fromtimestamp(float(r["killed_at"])).strftime("%d/%m/%Y  %H:%M:%S")
            spawn = datetime.fromtimestamp(float(r["respawn_at"])).strftime("%d/%m/%Y  %H:%M:%S")
            tk.Label(details, text="MORTE  " + kill, fg=MUTED, bg=row.cget("bg"),
                     font=("Consolas", 9)).pack(side="left")
            tk.Label(details, text="RESPAWN  " + spawn, fg=ACCENT, bg=row.cget("bg"),
                     font=("Consolas", 9, "bold")).pack(side="right")

    def clear_history(self):
        if self.history and messagebox.askyesno("Limpar histórico", "Apagar todos os registros de derrotas? Os timers continuarão ativos."):
            self.history.clear()
            self.save_history()
            self.render_history()

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temp = DATA_FILE.with_suffix(".tmp")
            with temp.open("w", encoding="utf-8") as f:
                json.dump(self.bosses, f, ensure_ascii=False, indent=2)
            temp.replace(DATA_FILE)
        except OSError as e:
            messagebox.showerror("Erro ao salvar", f"Não foi possível salvar os dados:\n{e}")

    def build_ui(self):
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                        foreground=TEXT, arrowcolor=ACCENT)
        style.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                        bordercolor=BG, arrowcolor=ACCENT)
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(header, text="⚔  YMIR BOSS TIMER", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(header, text=f"LEGEND OF YMIR   /   CENTRAL DE RESPAWNS   /   v{APP_VERSION}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))
        nav = tk.Frame(self, bg=BG)
        nav.pack(fill="x", padx=16, pady=(10, 2))
        self.tab_timers = tk.Button(nav, text="  ◷  TIMERS  ", command=lambda: self.switch_tab("timers"),
                                    bg=ACCENT, fg=BG, relief="flat", padx=15, pady=10,
                                    font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.tab_timers.pack(side="left", padx=(0, 9))
        self.tab_history = tk.Button(nav, text="  ▤  HISTÓRICO  ", command=lambda: self.switch_tab("history"),
                                     bg=PANEL, fg=TEXT, relief="flat", padx=15, pady=10,
                                     font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.tab_history.pack(side="left")
        self.tab_upcoming = tk.Button(nav, text="  ◷  PRÓXIMOS  ", command=lambda: self.switch_tab("upcoming"),
                                      bg=PANEL, fg=TEXT, relief="flat", padx=12, pady=10,
                                      font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.tab_upcoming.pack(side="left", padx=(9, 0))
        tk.Button(nav, text="⬇ ATUALIZAÇÕES", command=self.updates_dialog, bg=PANEL, fg=ACCENT,
                  relief="flat", padx=15, pady=10, font=("Segoe UI", 10, "bold"),
                  cursor="hand2").pack(side="right")
        self.timer_view = tk.Frame(self, bg=BG)
        self.timer_view.pack(fill="both", expand=True)
        self.history_view = tk.Frame(self, bg=BG)
        self.upcoming_view = tk.Frame(self, bg=BG)
        self.build_history_ui()
        self.build_upcoming_ui()
        bar = tk.Frame(self.timer_view, bg=PANEL)
        bar.pack(fill="x", padx=16, pady=8, ipady=7)
        tk.Button(bar, text="◈ Overlay gamer", command=self.toggle_overlay, bg=PURPLE,
                  fg=BG, relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2").pack(side="right", padx=(0, 7))
        tk.Button(bar, text="⊟ Bandeja", command=self.hide_to_tray, bg=PANEL,
                  fg=TEXT, relief="flat", font=("Segoe UI", 9),
                  cursor="hand2").pack(side="right", padx=(0, 7))
        tk.Button(bar, text="◱ Modo compacto", command=self.open_compact, bg=ACCENT,
                  fg=BG, relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2").pack(side="right", padx=8)
        tk.Checkbutton(bar, text="Sempre no topo", variable=self.always_on_top,
                       command=self.update_topmost, bg=PANEL, fg=TEXT, selectcolor=BG,
                       activebackground=PANEL, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(side="left", padx=8)
        tk.Label(bar, text="🔔 Aviso: 1 min", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 3))
        form = tk.Frame(self.timer_view, bg=BG)
        form.pack(fill="x", padx=16, pady=(6, 8))
        tk.Label(form, text="Boss", bg=BG, fg=MUTED).grid(row=0, column=0, sticky="w")
        tk.Label(form, text="Seção", bg=BG, fg=MUTED).grid(row=0, column=2, sticky="w")
        tk.Label(form, text="Respawn (min)", bg=BG, fg=MUTED).grid(row=0, column=1, sticky="w")
        self.name_entry = tk.Entry(form, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                                   font=("Segoe UI", 10))
        self.name_entry.grid(row=1, column=0, sticky="ew", ipady=8, padx=(0, 8))
        self.minutes_entry = tk.Entry(form, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                                      width=12, font=("Segoe UI", 10))
        self.minutes_entry.grid(row=1, column=1, sticky="ew", ipady=8, padx=(0, 8))
        self.category_select = ttk.Combobox(form, textvariable=self.category_var, values=CATEGORIES,
                                             state="readonly", width=19, font=("Segoe UI", 9))
        self.category_select.grid(row=1, column=2, sticky="ew", padx=(0, 8), ipady=5)
        tk.Button(form, text="+ Adicionar", command=self.add_boss, bg=ACCENT, fg=BG,
                  activebackground="#8ef2dc", relief="flat", cursor="hand2",
                  font=("Segoe UI", 9, "bold"), padx=9).grid(row=1, column=3, ipady=6)
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=2)
        self.minutes_entry.bind("<Return>", lambda _e: self.add_boss())
        self.name_entry.bind("<Return>", lambda _e: self.add_boss())
        tk.Label(self.timer_view, text="SEUS BOSSES", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(8, 5))
        outer = tk.Frame(self.timer_view, bg=BG)
        outer.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.cards = tk.Frame(self.canvas, bg=BG)
        self.window_id = self.canvas.create_window((0, 0), window=self.cards, anchor="nw")
        self.cards.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self.scroll))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))
        self.footer = tk.Label(self.timer_view, text="Alertas de todas as seções ativos mesmo recolhidas • Mantenha o app aberto", bg=BG,
                               fg=MUTED, font=("Segoe UI", 9))
        self.footer.pack(pady=(0, 12))

    def build_history_ui(self):
        heading = tk.Frame(self.history_view, bg=BG)
        heading.pack(fill="x", padx=16, pady=(15, 8))
        tk.Label(heading, text="HISTÓRICO DE DERROTAS", bg=BG, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(heading, text="Última morte e próximo nascimento registrados em cada acionamento manual.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
        toolbar = tk.Frame(self.history_view, bg=BG)
        toolbar.pack(fill="x", padx=16, pady=(6, 8))
        self.history_count = tk.Label(toolbar, text="", bg=BG, fg=ACCENT,
                                      font=("Segoe UI", 10, "bold"))
        self.history_count.pack(side="left")
        tk.Button(toolbar, text="Abrir backups", command=self.open_backup_folder,
                  bg=PANEL, fg=ACCENT, relief="flat", padx=8).pack(side="right", padx=(0, 8))
        tk.Button(toolbar, text="Limpar histórico", command=self.clear_history,
                  bg=PANEL, fg=DANGER, relief="flat", padx=12, pady=7,
                  font=("Segoe UI", 9), cursor="hand2").pack(side="right")
        container = tk.Frame(self.history_view, bg=BG)
        container.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.history_rows = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), anchor="nw", window=self.history_rows)
        self.history_rows.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    def scroll(self, event):
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-1 * event.delta / 120), "units")

    def update_topmost(self):
        self.attributes("-topmost", self.always_on_top.get())
        if self.compact is not None and self.compact.winfo_exists():
            self.compact.attributes("-topmost", self.always_on_top.get())

    def open_compact(self):
        if self.compact is not None and self.compact.winfo_exists():
            self.compact.lift()
            return
        mini = tk.Toplevel(self)
        self.compact = mini
        mini.title("Ymir • Mini Timer")
        mini.configure(bg=BG)
        mini.geometry("385x330+60+60")
        mini.minsize(310, 160)
        mini.attributes("-topmost", True)
        self.always_on_top.set(True)
        self.attributes("-topmost", True)
        mini.protocol("WM_DELETE_WINDOW", self.close_compact)
        header = tk.Frame(mini, bg=BG)
        header.pack(fill="x", padx=10, pady=(9, 5))
        tk.Label(header, text="⚔ YMIR • alertas de todas as seções", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Button(header, text="Modo completo", command=self.close_compact,
                  bg=PANEL, fg=TEXT, relief="flat", cursor="hand2",
                  font=("Segoe UI", 9)).pack(side="right")
        self.mini_canvas = tk.Canvas(mini, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(mini, orient="vertical", command=self.mini_canvas.yview)
        self.mini_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.mini_canvas.pack(fill="both", expand=True, padx=(10, 0), pady=(0, 8))
        self.mini_cards = tk.Frame(self.mini_canvas, bg=BG)
        window = self.mini_canvas.create_window((0, 0), window=self.mini_cards, anchor="nw")
        self.mini_cards.bind("<Configure>", lambda _e: self.mini_canvas.configure(scrollregion=self.mini_canvas.bbox("all")))
        self.mini_canvas.bind("<Configure>", lambda e: self.mini_canvas.itemconfigure(window, width=e.width))
        self.mini_canvas.bind("<MouseWheel>", lambda e: self.mini_canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.render_compact()
        self.withdraw()

    def close_compact(self):
        if self.compact is not None:
            self.compact.destroy()
            self.compact = None
        self.compact_labels = {}
        self.deiconify()
        self.lift()
        self.update_topmost()

    def toggle_category(self, category):
        self.collapsed[category] = not self.collapsed[category]
        self.render()

    def category_header(self, parent, category, group, compact=False, nested=False):
        collapsed = self.collapsed[category]
        header = tk.Frame(parent, bg=PANEL)
        indent = 18 if nested else 0
        header.pack(fill="x", pady=(5 if nested else 8, 5),
                    padx=(indent, 7 if compact else 0))
        title = self.category_title(category, group)
        button = tk.Button(header, text=title, command=lambda c=category: self.toggle_category(c),
                   bg=PANEL, fg=PURPLE if nested else ACCENT, anchor="w",
                   relief="flat", cursor="hand2",
                   font=("Segoe UI", 9 if compact or nested else 11, "bold"),
                   padx=8, activebackground=PANEL, activeforeground=TEXT)
        button.pack(fill="x", pady=5)
        self.category_headers.append((category, button))
        # Recolher uma seção só esconde os cartões. O monitoramento segue global.

    def category_title(self, category, group):
        """Contagem por seção e por canal, mesmo quando recolhidos."""
        now = time.time()
        soon = sum(1 for boss in group if boss.get("end", 0) > now
                   and boss["end"] - now <= NEAR_RESPAWN_SECONDS)
        ready = sum(1 for boss in group if boss.get("end", 0) > 0
                    and boss["end"] <= now)
        prefix = "▸" if self.collapsed[category] else "▾"
        suffix = f"  • {soon} em até 5 min" if soon else ""
        if ready:
            suffix += f"  • {ready} disponível(is)"
        label = category.split(" • ")[-1] if " • " in category else category.upper()
        return f"{prefix}  {label} ({len(group)}){suffix}"

    def group_for_header(self, category):
        if category.startswith(MYRKHEIMR + " • "):
            channel = category.split(" • ")[-1]
            return [b for b in self.bosses
                    if b.get("category") == MYRKHEIMR and b.get("channel") == channel]
        if category.startswith(FOLKVANGR + " • "):
            floor = category.split(" • ", 1)[-1]
            return [b for b in self.bosses
                    if b.get("category") == FOLKVANGR and b.get("floor") == floor]
        return [b for b in self.bosses if b.get("category", CATEGORIES[0]) == category]

    def render_sections(self, parent, compact=False):
        make_card = self.make_compact_card if compact else self.make_full_card
        for category in CATEGORIES:
            group = self.group_for_header(category)
            self.category_header(parent, category, group, compact=compact)
            if self.collapsed[category]:
                continue
            if category in (MYRKHEIMR, FOLKVANGR):
                subgroups = (
                    [channel_group_key(c) for c in CHANNELS] if category == MYRKHEIMR
                    else [floor_group_key(f) for f in FLOORS]
                )
                for key in subgroups:
                    subgroup = self.group_for_header(key)
                    self.category_header(parent, key, subgroup, compact=compact, nested=True)
                    if self.collapsed[key]:
                        continue
                    if not subgroup and not compact:
                        tk.Label(parent, text="Nenhum boss neste local", bg=BG, fg=MUTED,
                                 anchor="w", font=("Segoe UI", 9)).pack(fill="x", padx=26, pady=(0, 8))
                    for boss in subgroup:
                        make_card(boss, nested=True)
            else:
                if not group and not compact:
                    tk.Label(parent, text="Nenhum boss nesta seção", bg=BG, fg=MUTED,
                             anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(0, 8))
                for boss in group:
                    make_card(boss, nested=False)

    def refresh_category_headers(self):
        for category, button in self.category_headers:
            if button.winfo_exists():
                group = self.group_for_header(category)
                button.config(text=self.category_title(category, group),
                              fg=WARNING if any(0 < b.get("end", 0) - time.time() <= NEAR_RESPAWN_SECONDS
                                                for b in group)
                              else (PURPLE if " • " in category else ACCENT))

    def render_compact(self):
        if self.compact is None or not self.compact.winfo_exists():
            return
        for child in self.mini_cards.winfo_children():
            child.destroy()
        self.compact_labels = {}
        self.category_headers = [(cat, button) for cat, button in self.category_headers if button.winfo_exists()]
        if not self.bosses:
            tk.Label(self.mini_cards, text="Cadastre bosses no modo completo.",
                     bg=BG, fg=MUTED, pady=20).pack()
        self.render_sections(self.mini_cards, compact=True)
        self.refresh_compact()

    def make_compact_card(self, boss, nested=False):
            row = tk.Frame(self.mini_cards, bg=PANEL)
            row.pack(fill="x", pady=(0, 6), padx=(26 if nested else 0, 7))
            top = tk.Frame(row, bg=PANEL)
            top.pack(fill="x", padx=9, pady=(6, 0))
            tk.Label(top, text=boss["name"], bg=PANEL, fg=TEXT,
                     anchor="w", font=("Segoe UI", 10, "bold")).pack(side="left", fill="x", expand=True)
            tk.Button(top, text="Iniciar", command=lambda b=boss: self.start(b),
                      bg=ACCENT, fg=BG, relief="flat", cursor="hand2",
                      font=("Segoe UI", 8, "bold")).pack(side="right")
            timer = tk.Label(row, bg=PANEL, fg=TEXT, anchor="w", font=("Consolas", 15, "bold"))
            timer.pack(fill="x", padx=9)
            born = tk.Label(row, bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 9))
            born.pack(fill="x", padx=9, pady=(0, 6))
            self.compact_labels[boss["id"]] = (timer, born)

    def refresh_compact(self):
        if self.compact is None or not self.compact.winfo_exists():
            return
        now = time.time()
        for boss in self.bosses:
            if boss["id"] not in self.compact_labels:
                continue
            timer, born = self.compact_labels[boss["id"]]
            end = boss.get("end", 0)
            if not end:
                timer.config(text="--:--  • Aguardando", fg=MUTED)
                born.config(text="Nascimento: --:--")
            elif end <= now:
                timer.config(text="00:00  • DISPONÍVEL", fg=ACCENT)
                born.config(text="Previsto: " + datetime.fromtimestamp(end).strftime("%d/%m %H:%M:%S"))
            else:
                remain = end - now
                timer.config(text=format_seconds(remain + .999), fg=WARNING if remain <= 60 else TEXT)
                born.config(text="Nasce: " + datetime.fromtimestamp(end).strftime("%d/%m %H:%M:%S"))

    def add_boss(self):
        name = self.name_entry.get().strip()
        try:
            minutes = int(self.minutes_entry.get().strip())
        except ValueError:
            minutes = 0
        if not name or len(name) > 60 or not 1 <= minutes <= 10080:
            messagebox.showwarning("Dados inválidos", "Informe um nome (até 60 caracteres) e tempo entre 1 e 10080 minutos.")
            return
        category = self.category_var.get()
        boss = {"id": uuid.uuid4().hex, "name": name, "minutes": minutes,
                "category": category,
                "channel": CHANNELS[0] if category == MYRKHEIMR else "",
                "floor": FLOORS[0] if category == FOLKVANGR else "",
                "end": 0, "warned_for": 0, "finished_for": 0, "last_kill": 0}
        self.bosses.append(boss)
        if category == MYRKHEIMR:
            self.bosses.append(clone_for_channel(boss, CHANNELS[1]))
        elif category == FOLKVANGR:
            for floor in FLOORS[1:]:
                self.bosses.append(clone_for_floor(boss, floor))
        self.name_entry.delete(0, "end")
        self.minutes_entry.delete(0, "end")
        self.save()
        self.render()

    def start(self, boss):
        killed_at = time.time()
        boss["end"] = killed_at + boss["minutes"] * 60
        boss["last_kill"] = killed_at
        self.history.append({"name": boss["name"], "category": boss.get("category", CATEGORIES[0]),
                             "channel": boss.get("channel", "") if boss.get("category") == MYRKHEIMR else "",
                             "floor": boss.get("floor", "") if boss.get("category") == FOLKVANGR else "",
                             "killed_at": killed_at, "respawn_at": boss["end"],
                             "boss_id": boss["id"]})
        self.history = self.history[-MAX_HISTORY:]
        self.save_history()
        self.render_history()
        boss["warned_for"] = 0
        boss["finished_for"] = 0
        self.alerted.discard(boss["id"])
        self.warning_alerted.discard(boss["id"])
        self.save()
        self.render()

    def reset(self, boss):
        boss["end"] = 0
        boss["warned_for"] = 0
        boss["finished_for"] = 0
        self.alerted.discard(boss["id"])
        self.warning_alerted.discard(boss["id"])
        self.save()
        self.render()

    def delete(self, boss):
        if messagebox.askyesno("Remover boss", f"Remover '{boss_alert_label(boss)}' da lista?"):
            self.bosses = [b for b in self.bosses if b["id"] != boss["id"]]
            self.save()
            self.render()

    def render(self):
        for child in self.cards.winfo_children():
            child.destroy()
        self.category_headers = [(cat, button) for cat, button in self.category_headers if button.winfo_exists()]
        self.time_labels = {}
        self.status_labels = {}
        self.respawn_labels = {}
        if not self.bosses:
            tk.Label(self.cards, text="Nenhum boss cadastrado.\nAdicione o primeiro acima.",
                     bg=BG, fg=MUTED, font=("Segoe UI", 11), pady=34).pack(fill="x")
        self.render_sections(self.cards)
        self.refresh_times()
        self.render_compact()

    def make_full_card(self, boss, nested=False):
            card = tk.Frame(self.cards, bg=PANEL)
            card.pack(fill="x", pady=(0, 9), ipady=9, padx=(26 if nested else 0, 0))
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill="x", padx=12, pady=(4, 3))
            tk.Label(top, text=boss["name"], bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 11, "bold"), anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(top, text="Editar tempo", command=lambda b=boss: self.edit_respawn_dialog(b),
                      bg="#34465e", fg=ACCENT, relief="flat", cursor="hand2",
                      font=("Segoe UI", 9, "bold"), padx=10, pady=3).pack(side="right", padx=(0, 7))
            tk.Button(top, text="✕", command=lambda b=boss: self.delete(b), bg=PANEL,
                      fg=MUTED, relief="flat", cursor="hand2").pack(side="right")
            mid = tk.Frame(card, bg=PANEL)
            mid.pack(fill="x", padx=12, pady=2)
            timer = tk.Label(mid, text="", bg=PANEL, fg=ACCENT, font=("Consolas", 19, "bold"))
            timer.pack(side="left")
            status = tk.Label(mid, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
            status.pack(side="left", padx=12)
            self.time_labels[boss["id"]] = timer
            self.status_labels[boss["id"]] = status
            respawn = tk.Label(card, text="", bg=PANEL, fg=ACCENT,
                               font=("Segoe UI", 10, "bold"), anchor="w")
            respawn.pack(fill="x", padx=12, pady=(0, 5))
            self.respawn_labels[boss["id"]] = respawn
            tk.Label(card, text=("Última morte: " + datetime.fromtimestamp(boss["last_kill"]).strftime("%d/%m às %H:%M:%S"))
                     if boss.get("last_kill") else "Última morte: ainda não registrada",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=12, pady=(0, 5))
            bottom = tk.Frame(card, bg=PANEL)
            bottom.pack(fill="x", padx=12, pady=(2, 0))
            tk.Label(bottom, text=f"Respawn: {boss['minutes']} min", bg=PANEL,
                     fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
            tk.Button(bottom, text="Boss morreu / Iniciar", command=lambda b=boss: self.start(b),
                      bg=ACCENT, fg=BG, activebackground="#8ef2dc", relief="flat",
                      cursor="hand2", font=("Segoe UI", 9, "bold"), padx=8).pack(side="right")
            tk.Button(bottom, text="Zerar", command=lambda b=boss: self.reset(b),
                      bg=PANEL, fg=TEXT, relief="flat", cursor="hand2",
                      font=("Segoe UI", 9)).pack(side="right", padx=4)
            category_select = ttk.Combobox(bottom, values=CATEGORIES, state="readonly", width=16,
                                           font=("Segoe UI", 8))
            category_select.set(boss.get("category", CATEGORIES[0]))
            category_select.pack(side="right", padx=(2, 5))
            category_select.bind("<<ComboboxSelected>>", lambda _e, b=boss, c=category_select: self.change_category(b, c.get()))

    def matching_respawn_copies(self, boss):
        """Cópias com mesmo nome, na mesma região, mas IDs e timers próprios."""
        category = boss.get("category", CATEGORIES[0])
        if category not in (MYRKHEIMR, FOLKVANGR):
            return [boss]
        name = boss["name"].strip().casefold()
        return [entry for entry in self.bosses
                if entry.get("category") == category
                and entry.get("name", "").strip().casefold() == name]

    def change_respawn_duration(self, boss, new_minutes, all_copies=False):
        """Corrige duração sem apagar timers, IDs, kills ou histórico."""
        if (isinstance(new_minutes, bool) or not isinstance(new_minutes, int)
                or not 1 <= new_minutes <= 10080):
            raise ValueError("O tempo deve ser um inteiro entre 1 e 10080 minutos.")
        targets = self.matching_respawn_copies(boss) if all_copies else [boss]
        now = time.time()
        changed = 0
        history_changed = False
        for target in targets:
            if target["minutes"] == new_minutes:
                continue
            old_end = target.get("end", 0)
            killed_at = target.get("last_kill", 0)
            target["minutes"] = new_minutes
            if old_end and killed_at:
                new_end = killed_at + new_minutes * 60
                target["end"] = new_end
                if new_end > now:
                    target["warned_for"] = 0
                    target["finished_for"] = 0
                else:
                    target["warned_for"] = new_end
                    target["finished_for"] = new_end if old_end <= now else 0
                for item in reversed(self.history):
                    if item.get("boss_id") != target["id"]:
                        continue
                    if abs(float(item.get("killed_at", 0)) - killed_at) < 0.01:
                        item["respawn_at"] = new_end
                        history_changed = True
                    break
            self.alerted.discard(target["id"])
            self.warning_alerted.discard(target["id"])
            changed += 1
        if changed:
            self.save()
            if history_changed:
                self.save_history()
                self.render_history()
            self.render()
        return changed

    def edit_respawn_dialog(self, boss):
        win = tk.Toplevel(self)
        win.title("Editar tempo de respawn")
        win.geometry("480x310")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        area = tk.Frame(win, bg=BG)
        area.pack(fill="both", expand=True, padx=19, pady=15)
        tk.Label(area, text="EDITAR TEMPO DE RESPAWN", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 9))
        tk.Label(area, text=f"{boss['name']}  •  {boss_location(boss)}", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11, "bold"), wraplength=440).pack(anchor="w", pady=(0, 10))
        tk.Label(area, text=f"Tempo atual: {boss['minutes']} minutos", bg=BG,
                 fg=MUTED).pack(anchor="w")
        value_var = tk.StringVar(value=str(boss["minutes"]))
        entry = tk.Entry(area, textvariable=value_var, bg=PANEL, fg=TEXT,
                         insertbackground=TEXT, relief="flat", width=12,
                         font=("Consolas", 14))
        entry.pack(anchor="w", ipady=5, pady=(5, 11))
        entry.select_range(0, "end")
        entry.focus_set()
        copies = self.matching_respawn_copies(boss)
        together = tk.BooleanVar(value=len(copies) > 1)
        if len(copies) > 1:
            tk.Checkbutton(area,
                           text=f"Aplicar também a todas as {len(copies)} cópias desta região",
                           variable=together, bg=BG, fg=ACCENT, selectcolor=PANEL,
                           activebackground=BG, activeforeground=TEXT,
                           font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 9))
        tk.Label(area, text="O respawn será recalculado pela última morte de cada\n"
                             "piso/canal. Não altera as mortes anteriores do histórico.",
                 bg=BG, fg=MUTED, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 12))
        buttons = tk.Frame(area, bg=BG)
        buttons.pack(fill="x")

        def save_new_time():
            raw = value_var.get().strip()
            if not raw.isdecimal():
                messagebox.showwarning("Tempo inválido", "Informe minutos inteiros.",
                                       parent=win)
                return
            new_minutes = int(raw)
            if not 1 <= new_minutes <= 10080:
                messagebox.showwarning("Tempo inválido", "Informe de 1 a 10080 minutos.",
                                       parent=win)
                return
            targets = copies if together.get() else [boss]
            if all(b["minutes"] == new_minutes for b in targets):
                win.destroy()
                return
            try:
                backup_data()
            except OSError as exc:
                messagebox.showerror("Backup não realizado",
                                     f"Não foi possível criar backup antes da edição:\n{exc}",
                                     parent=win)
                return
            self.change_respawn_duration(boss, new_minutes, all_copies=together.get())
            win.destroy()

        tk.Button(buttons, text="Salvar alterações", command=save_new_time,
                  bg=ACCENT, fg=BG, relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold"), padx=13).pack(side="left")
        tk.Button(buttons, text="Cancelar", command=win.destroy,
                  bg=PANEL, fg=TEXT, relief="flat", cursor="hand2",
                  padx=10).pack(side="left", padx=10)
        win.bind("<Return>", lambda _event: save_new_time())
        win.bind("<Escape>", lambda _event: win.destroy())

    def change_category(self, boss, category):
        if category not in CATEGORIES or boss.get("category") == category:
            return
        boss["category"] = category
        boss["channel"] = CHANNELS[0] if category == MYRKHEIMR else ""
        boss["floor"] = FLOORS[0] if category == FOLKVANGR else ""
        if category == MYRKHEIMR:
            self.bosses.append(clone_for_channel(boss, CHANNELS[1]))
        elif category == FOLKVANGR:
            for floor in FLOORS[1:]:
                self.bosses.append(clone_for_floor(boss, floor))
        self.save()
        self.render()

    def sound(self):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except (ImportError, RuntimeError):
            self.bell()

    def notify(self, boss_name, title, description):
        """Aviso sonoro + toast nativo Windows; popup como alternativa."""
        self.sound()
        toast_ok = False
        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "YmirBossTimer.LegendOfYmir")
                from winotify import Notification
                toast = Notification(app_id="Ymir Boss Timer", title=title,
                                     msg=f"{boss_name}\n{description}", duration="short")
                toast.show()
                toast_ok = True
            except Exception:
                toast_ok = False
        if toast_ok:
            return
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.configure(bg=PANEL)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.geometry("370x130")
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        popup.geometry(f"+{max(0, screen_width - 390)}+{max(0, screen_height - 210)}")
        tk.Label(popup, text=title, fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 12, "bold"), wraplength=340).pack(pady=(13, 5))
        tk.Label(popup, text=f"{boss_name}\n{description}", fg=TEXT, bg=PANEL,
                 font=("Segoe UI", 10), wraplength=340).pack()
        popup.after(12000, lambda: popup.destroy() if popup.winfo_exists() else None)

    def check_alerts(self):
        """Percorre TODOS os bosses sem depender das seções visíveis."""
        now = time.time()
        for boss in self.bosses:
            end = boss.get("end", 0)
            if not end:
                continue
            remaining = end - now
            if remaining <= 0:
                if boss.get("finished_for", 0) != end:
                    boss["finished_for"] = end
                    self.save()
                    self.notify(boss_alert_label(boss), "Boss disponível!", "O horário de respawn chegou.")
            elif remaining <= 60 and boss.get("warned_for", 0) != end:
                boss["warned_for"] = end
                self.save()
                self.notify(boss_alert_label(boss), "Falta 1 minuto!",
                            "Nasce às " + datetime.fromtimestamp(end).strftime("%H:%M:%S"))

    def refresh_times(self):
        now = time.time()
        for boss in self.bosses:
            bid = boss["id"]
            if bid not in self.time_labels:
                continue
            end = boss.get("end", 0)
            remaining = end - now
            timer = self.time_labels[bid]
            status = self.status_labels[bid]
            respawn = self.respawn_labels[bid]
            respawn.config(text=("Nascimento previsto: " + datetime.fromtimestamp(end).strftime("%d/%m às %H:%M:%S")) if end else "Nascimento previsto: --:--")
            if not end:
                timer.config(text="--:--", fg=MUTED)
                status.config(text="Aguardando kill", fg=MUTED)
            elif remaining <= 0:
                timer.config(text="00:00", fg=ACCENT)
                status.config(text="PRONTO / RESPAWN", fg=ACCENT)
            else:
                timer.config(text=format_seconds(remaining + 0.999), fg=WARNING if remaining <= 60 else TEXT)
                status.config(text="Contando...", fg=MUTED)

    def tick(self):
        self.check_alerts()  # Todos os canais e pisos, mesmo recolhidos.
        self.refresh_times()
        self.refresh_compact()
        self.refresh_category_headers()
        self.refresh_overlay()
        self.process_tray_commands()
        if not self.winfo_exists():
            return
        now = time.time()
        if now - self.last_upcoming_refresh >= 1:
            self.render_upcoming()
            self.last_upcoming_refresh = now
        if now - self.last_backup_at >= 6 * 3600:
            try:
                backup_data()
            except OSError:
                pass
            self.last_backup_at = now
        if now - self.last_update_check >= 30 * 60:
            self.check_updates(silent=True)
        if self.latest_release and self.auto_update_enabled.get() and not self.update_busy:
            active = any(b.get("end", 0) > now for b in self.bosses)
            if active:
                self.auto_update_idle_since = now
            elif now - self.auto_update_idle_since >= 120:
                self.install_update(auto=True)
        else:
            self.auto_update_idle_since = now
        self.after(500, self.tick)

    def open_backup_folder(self):
        folder = DATA_DIR / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(folder))
        else:
            messagebox.showinfo("Backups", f"Seus backups estão em: {folder}")

    def close(self):
        """O X minimiza para a bandeja; a opção Sair encerra de verdade."""
        if self.tray_icon is not None:
            self.hide_to_tray()
        else:
            self.quit_app()

    def quit_app(self):
        self.save()
        self.save_history()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        if self.overlay is not None and self.overlay.winfo_exists():
            self.overlay.destroy()
        if self.compact is not None and self.compact.winfo_exists():
            self.compact.destroy()
        self.destroy()

if __name__ == "__main__":
    app = BossTimerApp()
    app.mainloop()
