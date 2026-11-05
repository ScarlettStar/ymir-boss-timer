"""Preferences, per-boss alerts, backup validation and quick combat actions."""
import copy
import io
import json
import math
import os
import struct
import threading
import time
import wave
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ymir_models import atomic_json, item_profile, clean_samples, read_profiles
from ymir_theme import BG, PANEL, TEXT, MUTED, ACCENT, WARNING, GamerButton

DATA_NAMES = ('bosses.json', 'history.json', 'profiles.json', 'updates.json', 'preferences.json')
DEFAULTS = {'lead_seconds': 60, 'volume': 70, 'tone': 'Cristal', 'boss_alerts': {},
            'muted_until': {}, 'overlay_alpha': 90, 'global_hotkeys': False}


def validated_preferences(saved):
    if not isinstance(saved, dict):
        raise ValueError('Preferências inválidas.')
    result = copy.deepcopy(DEFAULTS)
    result.update(saved)
    def check(options):
        for key, maximum in (('lead_seconds', 3600), ('volume', 100)):
            if key in options and (type(options[key]) is not int or not 0 <= options[key] <= maximum):
                raise ValueError('Valor inválido nas opções de alerta.')
        if options.get('tone', 'Cristal') not in ('Cristal', 'Grave', 'Duplo'):
            raise ValueError('Som de alerta inválido.')
    check(result)
    if type(result['overlay_alpha']) is not int or not 50 <= result['overlay_alpha'] <= 100:
        raise ValueError('Opacidade inválida.')
    if not isinstance(result['boss_alerts'], dict) or not isinstance(result['muted_until'], dict):
        raise ValueError('Opções de contas/bosses inválidas.')
    for options in result['boss_alerts'].values():
        if not isinstance(options, dict):
            raise ValueError('Opções de boss inválidas.')
        check(options)
    for until in result['muted_until'].values():
        if type(until) not in (int, float) or not math.isfinite(until) or until < 0:
            raise ValueError('Prazo de silêncio inválido.')
    if type(result['global_hotkeys']) is not bool:
        raise ValueError('Opção de atalhos inválida.')
    geometry = result.get('overlay_geometry')
    if geometry is not None:
        import re
        if not isinstance(geometry, str) or not re.fullmatch(r'\d{2,5}x\d{2,5}[+-]\d{1,6}[+-]\d{1,6}', geometry):
            raise ValueError('Posição do painel inválida.')
    return result


def alert_key(boss):
    return json.dumps([item_profile(boss), boss['id']], ensure_ascii=False)


def alert_options(prefs, boss=None):
    result = {k: prefs.get(k, DEFAULTS[k]) for k in ('lead_seconds', 'volume', 'tone')}
    if boss:
        result.update(prefs.get('boss_alerts', {}).get(alert_key(boss), {}))
    return result


def tone_wave(volume, tone):
    """Amplitude changes only this app's sound, never the Windows mixer."""
    amplitude = int(12000 * max(0, min(100, volume)) / 100)
    frequency = {'Cristal': 880, 'Grave': 440, 'Duplo': 660}.get(tone, 880)
    rate, frames = 22050, bytearray()
    for i in range(int(rate * .36)):
        t = i / rate
        envelope = min(1, t / .015) * max(0, 1 - t / .36)
        if tone == 'Duplo' and .13 < t < .20:
            envelope = 0
        frames.extend(struct.pack('<h', int(amplitude * envelope * math.sin(2 * math.pi * frequency * t))))
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return out.getvalue()


def validate_backup(values):
    """Reject malformed archives before touching live data; loader must not drop rows."""
    if not {'bosses.json', 'history.json', 'profiles.json'} <= values.keys():
        raise ValueError('O backup precisa conter bosses, histórico e contas.')
    for name in values:
        if name not in DATA_NAMES:
            raise ValueError('Arquivo de backup desconhecido.')
    bosses, history, profiles = values['bosses.json'], values['history.json'], values['profiles.json']
    if not isinstance(bosses, list) or not isinstance(history, list) or not isinstance(profiles, dict):
        raise ValueError('Estrutura de backup inválida.')
    accounts = profiles.get('profiles')
    if not isinstance(accounts, list) or not accounts or any(not isinstance(p, dict) or not isinstance(p.get('id'), str) or not p['id'] or not isinstance(p.get('name'), str) or not p['name'].strip() or not isinstance(p.get('server', ''), str) or not isinstance(p.get('regions', []), list) or any(not isinstance(r, str) or not r.strip() for r in p.get('regions', [])) for p in accounts):
        raise ValueError('Contas inválidas no backup.')
    ids = [p['id'] for p in accounts]
    if len(set(ids)) != len(ids) or profiles.get('active') not in ids:
        raise ValueError('Conta ativa ou identificadores inválidos.')
    seen = set()
    for b in bosses:
        if not isinstance(b, dict) or not isinstance(b.get('name'), str) or not b['name'].strip() or not isinstance(b.get('id'), str) or not b['id']:
            raise ValueError('Boss inválido no backup.')
        if type(b.get('minutes')) is not int or not 1 <= b['minutes'] <= 10080 or item_profile(b) not in ids:
            raise ValueError('Tempo ou conta de boss inválidos.')
        if len(b['name']) > 60 or not isinstance(b.get('category', ''), str) or len(b.get('category', '')) > 60:
            raise ValueError('Nome/região de boss inválidos.')
        if not isinstance(b.get('respawn_samples', []), list) or clean_samples(b.get('respawn_samples', [])) != b.get('respawn_samples', []):
            raise ValueError('Amostras de respawn inválidas.')
        key = (item_profile(b), b['id'])
        if key in seen:
            raise ValueError('Boss duplicado no backup.')
        seen.add(key)
        for field in ('end', 'last_kill', 'warned_for', 'finished_for', 'spawn_for'):
            value = b.get(field, 0)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 4102444800:
                raise ValueError('Horário inválido no backup.')
    for h in history:
        if (not isinstance(h, dict) or type(h.get('killed_at')) not in (int, float)
                or not math.isfinite(h['killed_at']) or not all(k in h for k in ('name', 'category', 'respawn_at')) or type(h.get('respawn_at')) not in (int, float) or not math.isfinite(h['respawn_at']) or not 0 <= h['killed_at'] <= 4102444800 or not 0 <= h['respawn_at'] <= 4102444800 or item_profile(h) not in ids):
            raise ValueError('Histórico inválido no backup.')
        if h.get('observed_respawn_at') is not None:
            value = h['observed_respawn_at']
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 4102444800:
                raise ValueError('Horário observado inválido no histórico.')
    for name in ('updates.json', 'preferences.json'):
        if name in values and not isinstance(values[name], dict):
            raise ValueError('Configurações inválidas no backup.')
    if 'preferences.json' in values:
        validated_preferences(values['preferences.json'])
    return values


def read_backup(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > len(DATA_NAMES) or len({i.filename for i in infos}) != len(infos):
            raise ValueError('Conteúdo de backup inválido.')
        if any(i.filename not in DATA_NAMES or i.file_size > 20_000_000 for i in infos):
            raise ValueError('Arquivo inesperado ou muito grande no backup.')
        return validate_backup({i.filename: json.loads(archive.read(i).decode('utf-8')) for i in infos})


def restore_files(folder, values):
    """Rollback all originals if any write fails. Caller creates safety backup first."""
    validate_backup(values)
    originals = {n: (folder / n).read_bytes() if (folder / n).exists() else None for n in values}
    try:
        for name, data in values.items():
            atomic_json(folder / name, data)
    except Exception:
        for name, data in originals.items():
            path = folder / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
        raise


class GlobalHotkeys:
    """Own Windows message thread; Tk only receives commands via its existing queue."""
    KEYS = {1: ('overlay', 0x4F), 2: ('kill', 0x4B), 3: ('spawn', 0x52), 4: ('channel', 0x43)}

    def __init__(self, commands):
        self.commands, self.stop_event = commands, threading.Event()
        self.ready = threading.Event()
        self.thread_id = None
        self.registered = []
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered = []
        try:
            for key, (action, vk) in self.KEYS.items():
                if user32.RegisterHotKey(None, key, 0x4003, vk):
                    registered.append(key)
                else:
                    self.commands.put('hotkey-failed:' + action)
            self.registered = list(registered)
            self.ready.set()
            msg = wintypes.MSG()
            while not self.stop_event.wait(.04):
                while user32.PeekMessageW(ctypes.byref(msg), None, 0x312, 0x312, 1):
                    if msg.wParam in self.KEYS:
                        self.commands.put('hotkey:' + self.KEYS[msg.wParam][0])
        finally:
            for key in registered:
                user32.UnregisterHotKey(None, key)

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=1)


class ProductivityMixin:
    def init_productivity(self):
        from ymir_boss_timer import DATA_DIR
        self.preferences_path = DATA_DIR / 'preferences.json'
        self.preferences = copy.deepcopy(DEFAULTS)
        try:
            saved = json.loads(self.preferences_path.read_text(encoding='utf-8'))
            self.preferences = validated_preferences(saved)
        except (OSError, ValueError):
            pass
        self.quick_target = None
        self.hotkey_status = tk.StringVar(value='Atalhos globais desativados')
        self._hotkeys = None
        for key, action in (('o', 'overlay'), ('k', 'kill'), ('r', 'spawn'), ('c', 'channel')):
            self.bind('<Control-Alt-' + key + '>', lambda _e, a=action: self.quick_action(a) if self._hotkeys is None else None)
        self.configure_hotkeys()

    def save_preferences(self):
        atomic_json(self.preferences_path, self.preferences)

    def configure_hotkeys(self):
        if self._hotkeys:
            self._hotkeys.close()
            self._hotkeys = None
        if self.preferences.get('global_hotkeys') and os.name == 'nt':
            self._hotkeys = GlobalHotkeys(self.tray_commands)
            self.hotkey_status.set('Atalhos globais ativos: Ctrl+Alt+O / K / R / C')
        else:
            self.hotkey_status.set('Atalhos funcionam com o app em foco. Globais: Windows, ative abaixo.')

    def options_for_alert(self, boss=None):
        return alert_options(self.__dict__.get('preferences', DEFAULTS), boss)

    def alert_is_muted(self, boss):
        return bool(boss and self.__dict__.get('preferences', {}).get('muted_until', {}).get(item_profile(boss), 0) > time.time())

    def choose_quick_target(self, boss):
        self.quick_target = (item_profile(boss), boss['id'])
        self.hotkey_status.set("Selecionado: " + self.alert_identity(boss))
        self.refresh_overlay()

    def selected_quick_boss(self):
        return next((b for b in self.bosses if (item_profile(b), b['id']) == self.quick_target), None)

    def quick_action(self, action):
        if action == 'overlay':
            self.toggle_overlay()
            return
        if action == 'channel':
            self.choose_channel('CHN 2' if self.current_channel_view() != 'CHN 2' else 'CHN 1')
            self.quick_target = None
            return
        boss = self.selected_quick_boss()
        if boss is None:
            self.hotkey_status.set('Selecione um boss no mini painel antes de usar Matei / Reapareceu.')
            return
        try:
            if action == 'kill':
                # Protect against accidental double presses resetting a running timer.
                if time.time() - boss.get('last_kill', 0) < 3:
                    return
                self.start(boss)
            elif action == 'spawn':
                self.confirm_respawn(boss)
            self.hotkey_status.set(action + ': ' + self.alert_identity(boss))
        except ValueError as exc:
            self.hotkey_status.set(str(exc))
        self.refresh_overlay()

    def tools_dialog(self):
        win = tk.Toplevel(self)
        win.title('Ferramentas • Ymir')
        win.configure(bg=BG)
        win.geometry('650x610')
        tabs = ttk.Notebook(win)
        tabs.pack(fill='both', expand=True, padx=12, pady=12)
        alerts, shortcuts, backup, summary, cloud = [tk.Frame(tabs, bg=BG) for _ in range(5)]
        for frame, title in zip((alerts, shortcuts, backup, summary), ('Alertas', 'Atalhos', 'Backup', 'Contas / canais')):
            tabs.add(frame, text=title)
        tabs.add(cloud, text='Nuvem')
        self.build_cloud_settings(cloud)
        self.build_alert_settings(alerts)
        tk.Label(shortcuts, text='CTRL + ALT + O → abrir/fechar mini painel\nCTRL + ALT + K → Matei o boss selecionado\nCTRL + ALT + R → Reapareceu (boss variável)\nCTRL + ALT + C → trocar CHN 1 / CHN 2\n\nSelecione o boss clicando na linha do mini painel.\nA seleção inclui conta, servidor e canal.\nNenhuma ação usa automaticamente o próximo boss.', bg=BG, fg=TEXT, justify='left', wraplength=570).pack(anchor='w', padx=16, pady=20)
        enabled = tk.BooleanVar(value=self.preferences.get('global_hotkeys', False))
        def apply_hotkeys():
            self.preferences['global_hotkeys'] = enabled.get()
            self.save_preferences()
            self.configure_hotkeys()
        tk.Checkbutton(shortcuts, text='Ativar atalhos globais no Windows (mesmo no jogo)', variable=enabled,
                       command=apply_hotkeys, bg=BG, fg=TEXT, selectcolor=PANEL).pack(anchor='w', padx=16)
        tk.Label(shortcuts, textvariable=self.hotkey_status, bg=BG, fg=WARNING, wraplength=560, justify='left').pack(padx=16, pady=12)
        tk.Label(backup, text='Exporta todas as contas, bosses, timers, histórico e configurações.\nAntes de restaurar, cria uma cópia de segurança dos dados atuais.\nA restauração substitui os dados das contas pelo backup escolhido.', bg=BG, fg=TEXT, wraplength=570, justify='left').pack(padx=16, pady=20)
        for title, action in (('Exportar backup…', self.export_backup_dialog), ('Restaurar backup…', self.restore_backup_dialog), ('Abrir backups automáticos', self.open_backup_folder)):
            GamerButton(backup, text=title, command=action, bg=PANEL, fg=ACCENT, pady=10).pack(fill='x', padx=20, pady=8)
        self.build_account_summary(summary)

    def build_alert_settings(self, parent):
        pid = self.active_profile_id()
        entries = self.profile_bosses()
        labels = ['Padrão para todos'] + [f'{b["name"]} • {b.get("channel") or b.get("floor") or b.get("category")} • {b.get("kind", "Boss")} [{b["id"][:6]}]' for b in entries]
        choice = ttk.Combobox(parent, values=labels, state='readonly')
        choice.current(0)
        choice.pack(fill='x', padx=16, pady=12)
        lead, volume, tone = tk.IntVar(), tk.IntVar(), tk.StringVar()
        def target():
            return entries[choice.current() - 1] if choice.current() > 0 else None
        def load(_e=None):
            options = self.options_for_alert(target())
            lead.set(options['lead_seconds'] // 60)
            volume.set(options['volume'])
            tone.set(options['tone'])
        choice.bind('<<ComboboxSelected>>', load)
        tk.Label(parent, text='Antecedência (minutos, 0 = somente no respawn)', bg=BG, fg=TEXT).pack(anchor='w', padx=16)
        tk.Spinbox(parent, from_=0, to=60, textvariable=lead, width=8).pack(anchor='w', padx=16, pady=6)
        tk.Label(parent, text='Volume do aviso (0 = sem som)', bg=BG, fg=TEXT).pack(anchor='w', padx=16)
        tk.Scale(parent, from_=0, to=100, orient='horizontal', variable=volume, bg=BG, fg=TEXT, highlightthickness=0).pack(fill='x', padx=16)
        ttk.Combobox(parent, values=('Cristal', 'Grave', 'Duplo'), textvariable=tone, state='readonly').pack(fill='x', padx=16, pady=8)
        def apply():
            try:
                if not 0 <= lead.get() <= 60:
                    raise ValueError('Use de 0 a 60 minutos.')
                options = dict(lead_seconds=lead.get()*60, volume=volume.get(), tone=tone.get())
                if target():
                    self.preferences['boss_alerts'][alert_key(target())] = options
                else:
                    self.preferences.update(options)
                self.save_preferences()
                messagebox.showinfo('Alertas', 'Configuração salva. Timers mantidos.', parent=parent)
            except (ValueError, tk.TclError, OSError) as exc:
                messagebox.showerror('Não foi possível salvar', str(exc), parent=parent)
        def inherit():
            if target():
                self.preferences['boss_alerts'].pop(alert_key(target()), None)
                self.save_preferences()
                load()
        def preview():
            self._sound_options = dict(volume=volume.get(), tone=tone.get())
            self.sound()
        GamerButton(parent, text='Ouvir som escolhido', command=preview, bg=PANEL, fg=WARNING).pack(fill='x', padx=16, pady=4)
        GamerButton(parent, text='Salvar alerta', command=apply, bg=PANEL, fg=ACCENT).pack(fill='x', padx=16, pady=8)
        GamerButton(parent, text='Usar padrão neste boss', command=inherit, bg=PANEL, fg=TEXT).pack(fill='x', padx=16, pady=4)
        def mute(minutes):
            self.preferences['muted_until'][pid] = time.time() + minutes*60 if minutes else 0
            self.save_preferences()
            muted_status.set('Conta silenciada por 30 min (som e avisos).' if minutes else 'Alertas da conta reativados.')
        muted_status = tk.StringVar(value='Conta silenciada.' if self.preferences['muted_until'].get(pid, 0) > time.time() else 'Alertas da conta ativos.')
        tk.Label(parent, text=self.profile_identity(), bg=BG, fg=MUTED).pack(pady=(10, 2))
        row = tk.Frame(parent, bg=BG)
        row.pack()
        for title, minutes in (('Pausar conta por 30 min', 30), ('Reativar conta', 0)):
            GamerButton(row, text=title, command=lambda m=minutes: mute(m), bg=PANEL, fg=TEXT).pack(side='left', padx=4)
        tk.Label(parent, textvariable=muted_status, bg=BG, fg=WARNING).pack(pady=6)
        load()

    def build_account_summary(self, parent):
        tree = ttk.Treeview(parent, columns=('account', 'place', 'active', 'soon', 'ready'), show='headings', style='Ymir.Treeview')
        for key, text, width in (('account', 'CONTA / SERVIDOR', 180), ('place', 'REGIÃO / CANAL', 180), ('active', 'ATIVOS', 65), ('soon', 'ATÉ 5m', 65), ('ready', 'PREV./PRONTOS', 100)):
            tree.heading(key, text=text)
            tree.column(key, width=width, minwidth=45)
        tree.pack(fill='both', expand=True, padx=8, pady=8)
        sb = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        sb.pack(fill='x')
        tree.configure(xscrollcommand=sb.set)
        def refresh():
            if not tree.winfo_exists():
                return
            tree.delete(*tree.get_children())
            from ymir_features import location
            groups = {}
            now = time.time()
            for b in self.bosses:
                key = (item_profile(b), location(b))
                counts = groups.setdefault(key, [0, 0, 0])
                end = b.get('end', 0)
                counts[0] += end > now
                counts[1] += 0 < end-now <= 300
                counts[2] += 0 < end <= now
            for (pid, place), counts in sorted(groups.items()):
                p = self.profile_definition(pid)
                tree.insert('', 'end', values=(p['name'] + ' / ' + (p.get('server') or '—'), place, *counts))
            self.after(1000, refresh)
        refresh()

    def export_backup_dialog(self):
        from ymir_boss_timer import DATA_DIR
        path = filedialog.asksaveasfilename(parent=self, title='Exportar backup', defaultextension='.zip', initialfile='Ymir-backup.zip', filetypes=[('Backup Ymir', '*.zip')])
        if not path:
            return
        try:
            self.save()
            self.save_history()
            self.save_preferences()
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name in DATA_NAMES:
                    if (DATA_DIR / name).is_file():
                        archive.write(DATA_DIR / name, name)
            messagebox.showinfo('Backup', 'Backup exportado.', parent=self)
        except OSError as exc:
            messagebox.showerror('Backup não exportado', str(exc), parent=self)

    def restore_backup_dialog(self):
        from ymir_boss_timer import DATA_DIR, backup_data
        if self.update_busy:
            messagebox.showinfo('Aguarde', 'Aguarde a atualização terminar antes de restaurar.', parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title='Restaurar backup', filetypes=[('Backup Ymir', '*.zip')])
        if not path:
            return
        try:
            values = read_backup(path)
            if not messagebox.askyesno('Restaurar backup?', 'Substituir todas as contas, bosses, timers e histórico pelos dados deste backup? Uma cópia dos dados atuais será criada antes.', parent=self):
                return
            backup_data()
            restore_files(DATA_DIR, values)
            self.profile_state = read_profiles(DATA_DIR / 'profiles.json')
            self.bosses, self.history = self.load(), self.load_history()
            self.preferences = validated_preferences(values.get('preferences.json', {}))
            self.save_preferences()
            self.configure_hotkeys()
            self.quick_target = None
            panel = self.__dict__.get('_alert_panel')
            if panel:
                panel.dismiss()
            self.refresh_account_view()
            self.update_repo = self.read_update_repo()
            self.auto_update_enabled.set(self.read_auto_update())
            messagebox.showinfo('Backup restaurado', 'Dados restaurados. Contagens usam os horários originais do backup.', parent=self)
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
            messagebox.showerror('Backup não restaurado', str(exc), parent=self)
