"""Tk integration. Network threads never touch widgets or live timer objects."""
import copy
import ctypes
import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from ymir_cloud import DEFAULT_CONFIG, config, login, exchange, entities, merge, apply_entities
from ymir_models import atomic_json
from ymir_theme import BG, TEXT, MUTED, ACCENT, GamerButton


def protect(raw, decrypt=False):
    if os.name != 'nt':
        raise ValueError('Sessão persistente protegida disponível no Windows.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), 'Ymir', None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise OSError('Não foi possível proteger a sessão no Windows.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


class CloudMixin:
    def init_cloud(self):
        from ymir_boss_timer import DATA_DIR
        self.cloud_session_file = DATA_DIR / 'cloud-session.bin'
        self.cloud_base_file = DATA_DIR / 'cloud-base.json'
        self.cloud_session = None
        self.cloud_queue = queue.SimpleQueue()
        self.cloud_busy = False
        self.cloud_next = 0
        self.cloud_status = tk.StringVar(value='Nuvem desconectada • dados locais preservados')
        try:
            self.cloud_session = json.loads(protect(self.cloud_session_file.read_bytes(), True))
            self.cloud_status.set('Nuvem conectada • aguardando sincronização')
        except (OSError, ValueError, KeyError):
            pass
        self.after(1000, self.cloud_poll)

    def cloud_snapshot(self):
        return copy.deepcopy({'bosses': self.bosses, 'history': self.history,
                              'profiles': self.profile_state, 'preferences': self.preferences})

    def cloud_baseline(self, session):
        try:
            data = json.loads(self.cloud_base_file.read_text(encoding='utf-8'))
            if data['identity'] == [session['project'], session['uid']]:
                return data
        except (OSError, ValueError, KeyError):
            pass
        return {'base': {}, 'conflicts': []}

    def cloud_poll(self):
        try:
            while True:
                kind, value = self.cloud_queue.get_nowait()
                self.cloud_busy = False
                if kind == 'login':
                    raw = protect(json.dumps(value).encode())
                    temp = self.cloud_session_file.with_suffix('.tmp')
                    temp.write_bytes(raw)
                    temp.replace(self.cloud_session_file)
                    self.cloud_session = value
                    self.cloud_next = 0
                    self.cloud_status.set('Conectado • preparando sincronização')
                elif kind == 'sync':
                    session, snapshot, remote, conflicts = value
                    if self.cloud_session != session:
                        continue
                    current = self.cloud_snapshot()
                    rebased, _ = merge(entities(snapshot), entities(current), remote, prefer_local=True)
                    updated = apply_entities(current, rebased)
                    if updated != current:
                        from ymir_boss_timer import DATA_DIR, backup_data
                        from ymir_productivity import restore_files
                        backup_data()
                        restore_files(DATA_DIR, {k + '.json': updated[k] for k in ('bosses', 'history', 'profiles')})
                        self.bosses, self.history, self.profile_state = updated['bosses'], updated['history'], updated['profiles']
                        self.refresh_account_view()
                    old = self.cloud_baseline(session)
                    atomic_json(self.cloud_base_file, {'identity': [session['project'], session['uid']], 'base': remote,
                                                      'conflicts': (old['conflicts'] + conflicts)[-100:]})
                    self.cloud_status.set('Sincronizado às ' + time.strftime('%H:%M:%S') +
                                          (' • conflito: mantida a alteração já na nuvem; cópia local guardada' if conflicts else ''))
                else:
                    self.cloud_status.set(str(value))
        except queue.Empty:
            pass
        except Exception as exc:
            self.cloud_busy = False
            self.cloud_status.set('Sincronização pendente: ' + str(exc))
        if self.cloud_session and not self.cloud_busy and time.time() >= self.cloud_next and not self.update_busy:
            self.cloud_sync_now()
        self.after(1000, self.cloud_poll)

    def cloud_sync_now(self):
        if self.cloud_busy or not self.cloud_session:
            return
        snapshot, session = self.cloud_snapshot(), copy.deepcopy(self.cloud_session)
        baseline = self.cloud_baseline(session)['base']
        self.cloud_busy = True
        self.cloud_next = time.time() + 60
        self.cloud_status.set('Sincronizando…')
        def work():
            try:
                remote, conflicts = exchange(session, baseline, entities(snapshot))
                self.cloud_queue.put(('sync', (session, snapshot, remote, conflicts)))
            except Exception as exc:
                self.cloud_queue.put(('error', exc))
        threading.Thread(target=work, daemon=True).start()

    def build_cloud_settings(self, frame):
        tk.Label(frame, text='SINCRONIZAR PC E CELULAR', bg=BG, fg=ACCENT).pack(anchor='w', padx=16, pady=12)
        tk.Label(frame, textvariable=self.cloud_status, bg=BG, fg=TEXT, wraplength=550).pack(anchor='w', padx=16, pady=5)
        tk.Label(frame, text='Use o mesmo login do Ymir Boss Timer no PC e no Android. Todas as contas do jogo deste aparelho serão sincronizadas.\n\nAlertas e aparência são locais. Sem internet, as marcações ficam pendentes. No celular, abra o app para receber os últimos horários antes de depender dos alertas.', bg=BG, fg=MUTED, justify='left', wraplength=550).pack(padx=16, pady=8)
        fields = {}
        for key, label in (('email', 'E-mail'), ('password', 'Senha do Ymir Boss Timer')):
            tk.Label(frame, text=label, bg=BG, fg=TEXT).pack(anchor='w', padx=16)
            entry = ttk.Entry(frame, show='•' if key == 'password' else '')
            if self.cloud_session and key in self.cloud_session:
                entry.insert(0, self.cloud_session[key])
            entry.pack(fill='x', padx=16, pady=(0, 5))
            fields[key] = entry
        def connect(create=False):
            if self.cloud_busy:
                return
            try:
                settings = dict(DEFAULT_CONFIG)
                email, password = fields['email'].get(), fields['password'].get()
                if not email.strip() or len(password) < 6:
                    raise ValueError('Informe e-mail e senha de pelo menos 6 caracteres.')
                if not messagebox.askyesno('Conectar dados à nuvem?', 'Todas as contas, bosses e histórico locais serão associados a este login. Em conflitos, a alteração já na nuvem tem prioridade e uma cópia da alteração local fica guardada. Continuar?', parent=frame):
                    return
                fields['password'].delete(0, 'end')
                self.cloud_busy = True
                self.cloud_status.set('Conectando…')
                def work():
                    try:
                        self.cloud_queue.put(('login', login(settings, email, password, create)))
                    except Exception as exc:
                        self.cloud_queue.put(('error', exc))
                threading.Thread(target=work, daemon=True).start()
            except Exception as exc:
                messagebox.showerror('Nuvem', str(exc), parent=frame)
        row = tk.Frame(frame, bg=BG)
        row.pack(fill='x', padx=16, pady=8)
        for text, action in (('Entrar', connect), ('Criar login', lambda: connect(True)), ('Sincronizar agora', self.cloud_sync_now)):
            GamerButton(row, text=text, command=action).pack(side='left', padx=3)
        def disconnect():
            if self.cloud_busy:
                return
            self.cloud_session_file.unlink(missing_ok=True)
            self.cloud_session = None
            self.cloud_status.set('Desconectado • timers locais continuam ativos')
        GamerButton(frame, text='Desconectar este aparelho', command=disconnect).pack(anchor='w', padx=16)
