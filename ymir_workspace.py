"""Account controls, custom catalogs and explicit respawn observations."""
import copy
import time
import tkinter as tk
from tkinter import ttk, messagebox
from ymir_theme import BG, PANEL, TEXT, MUTED, ACCENT, PURPLE, WARNING, GamerButton
from ymir_models import (DEFAULT_PROFILE, DEFAULT_REGIONS, item_profile, add_profile, uses_channels, channel_region, TOMB_REGION,
                         copy_boss_definitions, observe_respawn, respawn_statistics, respawn_seconds, missing_tomb_channel_copies)


class WorkspaceMixin:
    def active_profile_id(self):
        return self.__dict__.get("profile_state", {}).get("active", DEFAULT_PROFILE)

    def profile_bosses(self, all_profiles=False):
        return list(self.bosses) if all_profiles else [b for b in self.bosses if item_profile(b) == self.active_profile_id()]

    def profile_history(self):
        return [h for h in self.history if item_profile(h) == self.active_profile_id()]

    def profile_definition(self, pid=None):
        pid = pid or self.active_profile_id()
        return next((p for p in self.__dict__.get("profile_state", {}).get("profiles", []) if p["id"] == pid),
                    {"id": pid, "name": "Conta principal", "server": "", "regions": []})

    def profile_identity(self, boss=None):
        profile = self.profile_definition(item_profile(boss) if boss is not None else None)
        return profile["name"] + (" / " + profile["server"] if profile.get("server") else "")

    def category_choices(self):
        result = list(DEFAULT_REGIONS)
        candidates = self.profile_definition().get("regions", []) + [b.get("category", "") for b in self.profile_bosses()]
        if any(channel_region(r) == TOMB_REGION for r in candidates) and TOMB_REGION not in candidates:
            result.remove(TOMB_REGION)
        for region in candidates:
            if region and region not in result:
                result.append(region)
        return tuple(result)

    def kind_choices(self):
        return tuple(dict.fromkeys(["Boss", "Elite", "Evento"] + [b.get("kind", "Boss") for b in self.profile_bosses()]))

    def alert_identity(self, boss):
        from ymir_features import location
        return f"{self.profile_identity(boss)} • {boss['name']} • {location(boss)}"

    def build_profile_controls(self, heading):
        row = tk.Frame(heading, bg=BG)
        row.pack(fill="x", pady=(0, 3))
        tk.Label(row, text="CONTA / SERVIDOR", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 8))
        self.profile_selection = tk.StringVar()
        self.profile_selector = ttk.Combobox(row, textvariable=self.profile_selection,
                                            state="readonly", width=24, font=("Segoe UI", 9))
        self.profile_selector.pack(side="left", fill="x", expand=True)
        self.profile_selector.bind("<<ComboboxSelected>>", lambda _e: self.switch_profile(self._profile_labels[self.profile_selection.get()]))
        GamerButton(row, text="Contas", command=self.profiles_dialog, bg=PANEL, fg=PURPLE,
                    padx=8, pady=3).pack(side="left", padx=5)
        GamerButton(row, text="Regiões", command=self.regions_dialog, bg=PANEL, fg=ACCENT,
                    padx=8, pady=3).pack(side="left")
        self.refresh_profile_selector()

    def refresh_profile_selector(self):
        profiles = self.profile_state["profiles"]
        self._profile_labels = {f"{i + 1} · {p['name']}" + (f" / {p['server']}" if p.get("server") else ""): p["id"]
                                for i, p in enumerate(profiles)}
        self.profile_selector.configure(values=tuple(self._profile_labels))
        self.profile_selection.set(next(label for label, pid in self._profile_labels.items() if pid == self.active_profile_id()))

    def switch_profile(self, pid):
        if pid not in {p["id"] for p in self.profile_state["profiles"]}:
            raise ValueError("Conta não encontrada.")
        candidate = copy.deepcopy(self.profile_state)
        candidate["active"] = pid
        try:
            self.persist_profile_state(candidate)
        except OSError as exc:
            messagebox.showerror("Conta não alterada", str(exc), parent=self)
            self.refresh_profile_selector()
            return
        self.refresh_account_view()

    def refresh_account_view(self):
        self.refresh_profile_selector()
        self.collapsed.update({key: False for key in self.collapsed})
        self.collapsed.update({region: False for region in self.category_choices()})
        self.category_select.configure(values=self.category_choices())
        self.category_var.set(self.category_choices()[0])
        self.boss_kind_select.configure(values=self.kind_choices())
        self.boss_kind_var.set("Boss")
        self.variable_respawn_var.set(False)
        # Do not accidentally submit an unfinished form into another account.
        self.name_entry.delete(0, "end")
        self.minutes_entry.delete(0, "end")
        self._filter_options = (self.category_choices(), self._filter_options[1])
        if self._filter_window is not None and self._filter_window.winfo_exists():
            self._filter_window.destroy()
        self.collapsed.update({f"{region} • {ch}": False for region in self.category_choices()
                               if uses_channels(region) for ch in ("CHN 1", "CHN 2")})
        self.clear_filters(reset_channel=False)
        self.render_history()
        self.render_upcoming()
        self.refresh_overlay()
        if self.compact is not None and self.compact.winfo_exists():
            self.compact.title("Ymir • " + self.profile_identity())

    def create_account(self, name, server, copy_catalog=False):
        source = self.profile_definition()
        candidate, pid = add_profile(self.profile_state, name, server, source if copy_catalog else None)
        copies = copy_boss_definitions(self.profile_bosses(), pid) if copy_catalog else []
        self.persist_profile_state(candidate)
        self.bosses.extend(copies)
        self.save()
        self.refresh_account_view()
        return pid

    def rename_account(self, name, server):
        name, server = name.strip(), server.strip()
        if not name or not server or len(name) > 60 or len(server) > 60:
            raise ValueError("Informe nome da conta e servidor, com até 60 caracteres cada.")
        candidate = copy.deepcopy(self.profile_state)
        for profile in candidate["profiles"]:
            if profile["id"] != self.active_profile_id() and (profile["name"].casefold(), profile.get("server", "").casefold()) == (name.casefold(), server.casefold()):
                raise ValueError("Já existe uma conta com esse nome nesse servidor.")
        profile = next(p for p in candidate["profiles"] if p["id"] == self.active_profile_id())
        profile.update(name=name, server=server)
        self.persist_profile_state(candidate)
        self.refresh_account_view()

    def profiles_dialog(self):
        win = tk.Toplevel(self)
        win.title("Contas e servidores")
        win.configure(bg=BG)
        win.geometry("440x345")
        win.transient(self)
        win.grab_set()
        profile = self.profile_definition()
        tk.Label(win, text="CONTAS E SERVIDORES", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(18, 10))
        values = []
        for title, initial in (("Nome da conta (apelido, sem senha)", profile["name"]), ("Servidor", profile.get("server", ""))):
            tk.Label(win, text=title, bg=BG, fg=MUTED).pack(anchor="w", padx=18)
            entry = tk.Entry(win, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat")
            entry.insert(0, initial)
            entry.pack(fill="x", padx=18, ipady=7, pady=(3, 10))
            values.append(entry)
        together = tk.BooleanVar(value=True)
        tk.Checkbutton(win, text="Ao adicionar: copiar cadastros e regiões desta conta",
                       variable=together, bg=BG, fg=TEXT, selectcolor=PANEL,
                       activebackground=BG, activeforeground=TEXT).pack(anchor="w", padx=18)
        tk.Label(win, text="Timers, histórico e médias não são copiados.\nA outra conta continua sendo monitorada ao trocar de tela.",
                 justify="left", bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(4, 12))
        def save(create):
            try:
                if create:
                    self.create_account(values[0].get(), values[1].get(), together.get())
                else:
                    self.rename_account(values[0].get(), values[1].get())
            except (ValueError, OSError) as exc:
                messagebox.showerror("Conta não salva", str(exc), parent=win)
                return
            win.destroy()
        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=18)
        GamerButton(actions, text="Salvar conta atual", command=lambda: save(False), bg=PANEL,
                    fg=TEXT, pady=7).pack(side="left")
        GamerButton(actions, text="Adicionar conta", command=lambda: save(True), bg=ACCENT,
                    fg=BG, pady=7).pack(side="right")

    def add_custom_region(self, name):
        name = name.strip()
        if (not name or len(name) > 60 or " • " in name or any(name.casefold() == r.casefold() for r in self.category_choices())
                or (channel_region(name) and any(channel_region(r) == channel_region(name) for r in self.category_choices()))):
            raise ValueError("Use um nome único de 1 a 60 caracteres, sem o separador •.")
        candidate = copy.deepcopy(self.profile_state)
        profile = next(p for p in candidate["profiles"] if p["id"] == self.active_profile_id())
        profile.setdefault("regions", []).append(name)
        self.persist_profile_state(candidate)
        self.collapsed[name] = False
        self.category_select.configure(values=self.category_choices())
        self.category_var.set(name)
        self._filter_options = (self.category_choices(), self._filter_options[1])
        self.render()

    def regions_dialog(self):
        win = tk.Toplevel(self)
        win.title("Adicionar região")
        win.configure(bg=BG)
        win.geometry("420x240")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="NOVA REGIÃO", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(win, text=self.profile_identity(), bg=BG, fg=MUTED, wraplength=380).pack(anchor="w", padx=18)
        entry = tk.Entry(win, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat")
        entry.pack(fill="x", padx=18, pady=12, ipady=7)
        entry.focus_set()
        tk.Label(win, text="Depois, cadastre bosses nessa região.\nA categoria do boss aceita nomes como Elite ou Evento.",
                 bg=BG, fg=MUTED, justify="left").pack(anchor="w", padx=18, pady=(0, 12))
        def submit():
            try:
                self.add_custom_region(entry.get())
            except (ValueError, OSError) as exc:
                messagebox.showwarning("Região não adicionada", str(exc), parent=win)
                return
            win.destroy()
            self.focus_boss_form()
        GamerButton(win, text="Adicionar região", command=submit, bg=ACCENT,
                    fg=BG, pady=6).pack(fill="x", padx=18)
        win.bind("<Return>", lambda _e: submit())

    def complete_tomb_channel2(self):
        copies = missing_tomb_channel_copies(self.bosses, profile_id=self.active_profile_id())
        changed = bool(copies)
        for boss in self.profile_bosses():
            if (channel_region(boss.get("category")) == TOMB_REGION and boss.get("channel") == "CHN 1"
                    and not boss.get("tomb_channel_copy_v1")):
                boss["tomb_channel_copy_v1"] = True
                changed = True
        if changed:
            self.bosses.extend(copies)
            self.save()
            self.render()
            self.render_upcoming()
            self.refresh_overlay()
        return len(copies)

    def complete_tomb_dialog(self):
        copied = self.complete_tomb_channel2()
        message = (f"{copied} boss(es) do Túmulo copiados para CHN 2.\nAs novas contagens estão zeradas e as médias são independentes."
                   if copied else "Nenhuma cópia necessária: os bosses já estão no CHN 2 ou o CHN 1 está vazio.")
        messagebox.showinfo("Túmulo • CHN 2", self.profile_identity() + "\n\n" + message, parent=self)

    def set_variable_respawn(self, boss, enabled):
        boss["variable_respawn"] = bool(enabled)
        killed_at, old_end = boss.get("last_kill", 0), boss.get("end", 0)
        if killed_at and old_end and boss.get("spawn_for") != killed_at:
            now = time.time()
            end = boss["end"] = killed_at + respawn_seconds(boss)
            boss["warned_for"] = 0 if end > now else end
            boss["finished_for"] = 0 if end > now or old_end > now else end
            for record in reversed(self.history):
                if (record.get("boss_id") == boss["id"] and item_profile(record) == item_profile(boss)
                        and record["killed_at"] == killed_at):
                    record.update(respawn_at=end, variable_respawn=boss["variable_respawn"])
                    self.save_history()
                    self.render_history()
                    break
        self.save()
        self.render()
        self.render_upcoming()
        self.refresh_overlay()

    def learning_description(self, boss):
        if not boss.get("variable_respawn"):
            return "Respawn fixo • categoria: " + boss.get("kind", "Boss")
        stats = respawn_statistics(boss)
        if stats is None:
            return f"Variável • sem observações: usa {boss['minutes']} min como referência. Confirme quando reaparecer."
        return (f"Variável • média {stats['mean'] / 60:.1f} min • {stats['count']} observações • "
                f"mín./máx. observado {stats['minimum'] / 60:.1f}–{stats['maximum'] / 60:.1f} min")

    def confirm_respawn(self, boss, spawned_at=None):
        now = time.time()
        updated = observe_respawn(boss, now if spawned_at is None else spawned_at, now)
        boss.update(updated)
        for record in reversed(self.history):
            if (record.get("boss_id") == boss["id"] and item_profile(record) == item_profile(boss)
                    and record["killed_at"] == boss["last_kill"]):
                record["observed_respawn_at"] = boss["end"]
                break
        self.save()
        self.save_history()
        self.render()
        self.render_history()
        self.render_upcoming()
        return respawn_statistics(boss)

    def observation_dialog(self, boss):
        win = tk.Toplevel(self)
        win.title("Confirmar reaparecimento")
        win.configure(bg=BG)
        win.geometry("430x315")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="REAPARECIMENTO OBSERVADO", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(win, text=boss["name"] + " • " + self.profile_identity(boss), bg=BG, fg=TEXT,
                 wraplength=390, justify="left").pack(anchor="w", padx=18)
        tk.Label(win, text="Apareceu há quantos minutos? Use 0 para agora.", bg=BG, fg=MUTED).pack(anchor="w", padx=18, pady=(12, 4))
        entry = tk.Entry(win, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 16))
        entry.insert(0, "0")
        entry.pack(fill="x", padx=18, ipady=6)
        entry.focus_set()
        entry.select_range(0, "end")
        tk.Label(win, text="Registre a hora em que viu o boss reaparecer.\nMortes sozinhas não medem o respawn.\nA média usa até 20 ciclos desta conta e deste canal/piso.",
                 bg=BG, fg=MUTED, justify="left").pack(anchor="w", padx=18, pady=12)
        def submit():
            try:
                raw = entry.get().strip()
                if not raw.isdecimal() or not 0 <= int(raw) <= 10080:
                    raise ValueError("Informe de 0 a 10080 minutos inteiros.")
                self.confirm_respawn(boss, time.time() - int(raw) * 60)
            except ValueError as exc:
                messagebox.showwarning("Observação não registrada", str(exc), parent=win)
                return
            win.destroy()
        GamerButton(win, text="Confirmar reaparecimento", command=submit, bg=ACCENT,
                    fg=BG, pady=8).pack(fill="x", padx=18)
        win.bind("<Return>", lambda _e: submit())
        win.bind("<Escape>", lambda _e: win.destroy())
