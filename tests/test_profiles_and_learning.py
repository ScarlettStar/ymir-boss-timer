import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir
from ymir_models import (default_profiles, read_profiles, reconcile_profiles, add_profile,
                         copy_boss_definitions, trim_history, respawn_statistics,
                         respawn_seconds, observe_respawn, clean_samples, atomic_json)
from ymir_smart import select_bosses
from ymir_updates import can_auto_install


def bare_app():
    app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
    app.profile_state = default_profiles()
    app.profile_state["profiles"][0].update(name="Völva", server="SA012")
    app.profile_state, _ = add_profile(app.profile_state, "Segunda conta", "EU005")
    app.profile_state["active"] = "default"
    app.bosses = []
    app.history = []
    app.alerted = set()
    app.warning_alerted = set()
    app._channel_migrated = app._floor_migrated = False
    for method in ("save", "save_history", "render", "render_history", "render_upcoming",
                   "refresh_overlay", "notify", "refresh_account_view"):
        setattr(app, method, Mock())
    return app


def boss(pid="default", bid="a", **extra):
    return {"id": bid, "profile_id": pid, "name": "Mesmo chefe", "minutes": 180,
            "category": ymir.MYRKHEIMR, "channel": "CHN 1", "kind": "Boss",
            "end": 0, "last_kill": 0, "warned_for": 0, "finished_for": 0,
            "respawn_samples": [], "spawn_for": 0, **extra}


class ProfileTests(unittest.TestCase):
    def test_legacy_data_is_assigned_once_without_changing_timer_or_id(self):
        app = bare_app()
        legacy = boss(end=11000, last_kill=200)
        legacy.pop("profile_id")
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bosses.json"
            file.write_text(json.dumps([legacy]))
            with patch.object(ymir, "DATA_FILE", file):
                entries = app.load()
                self.assertEqual(len(entries), 1)
                self.assertEqual((entries[0]["profile_id"], entries[0]["id"], entries[0]["end"]), ("default", "a", 11000))
                file.write_text(json.dumps(entries))
                self.assertEqual(app.load(), entries)

    def test_copying_catalog_never_copies_running_timers_or_learning(self):
        original = boss(end=11000, last_kill=200, variable_respawn=True,
                        respawn_samples=[{"killed_at": 10, "spawned_at": 600}])
        copies = copy_boss_definitions([original], "second")
        self.assertNotEqual(copies[0]["id"], original["id"])
        self.assertEqual(copies[0]["profile_id"], "second")
        self.assertEqual(copies[0]["end"], 0)
        self.assertEqual(copies[0]["last_kill"], 0)
        self.assertEqual(copies[0]["respawn_samples"], [])
        self.assertEqual(original["end"], 11000)
        self.assertEqual(len(original["respawn_samples"]), 1)

    def test_two_accounts_same_name_bosses_have_independent_timers_and_history(self):
        app = bare_app()
        second = app.profile_state["profiles"][1]["id"]
        app.bosses = [boss(), boss(second, "b")]
        with patch.object(ymir.time, "time", return_value=10000):
            app.start(app.bosses[0])
        self.assertEqual(app.bosses[0]["end"], 20800)
        self.assertEqual(app.bosses[1]["end"], 0)
        self.assertEqual(app.history[0]["profile_id"], "default")
        app.profile_state["active"] = second
        self.assertEqual(app.profile_bosses(), [app.bosses[1]])
        self.assertEqual(app.profile_history(), [])
        with patch.object(ymir.time, "time", return_value=11000):
            app.start(app.bosses[1])
        self.assertEqual(app.bosses[0]["end"], 20800)
        self.assertEqual(app.profile_history()[0]["profile_id"], second)

    def test_edit_all_copies_is_restricted_to_account_region_and_kind(self):
        app = bare_app()
        second = app.profile_state["profiles"][1]["id"]
        first = boss()
        ch2 = ymir.clone_for_channel(first, "CHN 2")
        other = boss(second, "b")
        elite = boss(bid="elite", kind="Elite")
        app.bosses = [first, ch2, other, elite]
        app.change_respawn_duration(first, 200, all_copies=True)
        self.assertEqual([b["minutes"] for b in app.bosses], [200, 200, 180, 180])

    def test_global_alerts_identify_inactive_account_and_server(self):
        app = bare_app()
        second = app.profile_state["profiles"][1]["id"]
        app.bosses = [boss(end=1030), boss(second, "b", end=999)]
        with patch.object(ymir.time, "time", return_value=1000):
            app.check_alerts()
            app.check_alerts()
        self.assertEqual(app.notify.call_count, 2)
        self.assertIn("SA012", app.notify.call_args_list[0].args[0])
        self.assertIn("EU005", app.notify.call_args_list[1].args[0])
        self.assertEqual(app.profile_bosses(), [app.bosses[0]])

    def test_updates_wait_for_timers_on_both_accounts(self):
        app = bare_app()
        second = app.profile_state["profiles"][1]["id"]
        app.bosses = [boss(), boss(second, "b", end=2000)]
        self.assertFalse(can_auto_install(app.bosses, 1000, 0))

    def test_creating_account_and_switching_persists_stable_ids(self):
        app = bare_app()
        app.bosses = [boss(end=11000, last_kill=200)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(ymir, "DATA_DIR", Path(tmp)):
            pid = app.create_account("Arqueiro", "SA099", copy_catalog=True)
            reread = read_profiles(Path(tmp) / "profiles.json")
            self.assertEqual(reread["active"], pid)
            self.assertEqual(len(app.profile_bosses()), 1)
            self.assertEqual(app.profile_bosses()[0]["end"], 0)
            app.switch_profile("default")
            self.assertEqual(app.profile_bosses()[0]["end"], 11000)
            self.assertEqual(read_profiles(Path(tmp) / "profiles.json")["active"], "default")

    def test_clear_history_only_clears_selected_account(self):
        app = bare_app()
        other = app.profile_state["profiles"][1]["id"]
        app.history = [{"profile_id": "default", "killed_at": 1}, {"profile_id": other, "killed_at": 2}]
        with patch.object(ymir.messagebox, "askyesno", return_value=True):
            app.clear_history()
        self.assertEqual(app.history, [{"profile_id": other, "killed_at": 2}])

    def test_history_limit_is_per_account(self):
        records = [{"profile_id": "a", "killed_at": i} for i in range(5)] + [{"profile_id": "b", "killed_at": 10}]
        trimmed = trim_history(records, 2)
        self.assertEqual([(r["profile_id"], r["killed_at"]) for r in trimmed], [("a", 3), ("a", 4), ("b", 10)])

    def test_invalid_metadata_does_not_silently_reassign_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "profiles.json"
            file.write_text('{"profiles": "bad"}')
            with self.assertRaises(ValueError):
                read_profiles(file)
            self.assertEqual(file.read_text(), '{"profiles": "bad"}')
        recovered = reconcile_profiles(default_profiles(), [{"profile_id": "orphan"}])
        self.assertIn("orphan", [p["id"] for p in recovered["profiles"]])
        self.assertEqual(recovered["active"], "default")

    def test_atomic_metadata_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "profiles.json"
            atomic_json(file, default_profiles())
            before = file.read_text()
            with patch.object(Path, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    atomic_json(file, {"changed": True})
            self.assertEqual(file.read_text(), before)

    def test_duplicate_account_identity_is_rejected(self):
        state, _ = add_profile(default_profiles(), "Conta 2", "SA099")
        with self.assertRaises(ValueError):
            add_profile(state, "conta 2", "sa099")

    def test_custom_region_and_boss_kind_survive_loading_and_filtering(self):
        app = bare_app()
        entry = boss(category="Nidavellir", channel="", kind="Elite")
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bosses.json"
            file.write_text(json.dumps([entry]))
            with patch.object(ymir, "DATA_FILE", file):
                app.bosses = app.load()
        self.assertEqual(app.bosses[0]["category"], "Nidavellir")
        self.assertIn("Nidavellir", app.category_choices())
        self.assertEqual(ymir.boss_location(app.bosses[0]), "Nidavellir")
        self.assertEqual(select_bosses(app.bosses, 1000, kind="Elite"), app.bosses)
        self.assertEqual(select_bosses(app.bosses, 1000, kind="Boss"), [])

    def test_backups_include_profile_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "profiles.json").write_text(json.dumps(default_profiles()))
            with patch.multiple(ymir, DATA_DIR=folder, DATA_FILE=folder / "bosses.json",
                                HISTORY_FILE=folder / "history.json", UPDATE_SETTINGS=folder / "updates.json"):
                backup = ymir.backup_data()
            self.assertEqual(json.loads((backup / "profiles.json").read_text()), default_profiles())


class RespawnLearningTests(unittest.TestCase):
    def test_average_is_based_on_observed_kill_to_spawn_not_kill_intervals(self):
        first = boss(variable_respawn=True, last_kill=100000, end=110800)
        first = observe_respawn(first, 109600, 109600)  # 160 minutes
        first.update(last_kill=120000, end=130800)
        first = observe_respawn(first, 132000, 132000)  # 200 minutes
        stats = respawn_statistics(first)
        self.assertEqual(stats, {"count": 2, "mean": 10800, "minimum": 9600, "maximum": 12000})
        self.assertEqual(respawn_seconds(first), 10800)

    def test_death_records_alone_do_not_train_average(self):
        app = bare_app()
        entry = boss(variable_respawn=True)
        app.bosses = [entry]
        for now in (100000, 200000):
            with patch.object(ymir.time, "time", return_value=now):
                app.start(entry)
        self.assertIsNone(respawn_statistics(entry))
        self.assertEqual(entry["end"], 210800)

    def test_confirmation_is_not_duplicated_and_invalid_observations_do_not_mutate(self):
        original = boss(variable_respawn=True, last_kill=100000, end=110800)
        snapshot = copy.deepcopy(original)
        for invalid in (99999, 100000, 120001, float("nan"), True):
            with self.assertRaises(ValueError):
                observe_respawn(original, invalid, 120000)
        self.assertEqual(original, snapshot)
        updated = observe_respawn(original, 110000, 120000)
        with self.assertRaises(ValueError):
            observe_respawn(updated, 111000, 120000)
        self.assertEqual(len(updated["respawn_samples"]), 1)

    def test_reset_and_unstarted_bosses_cannot_produce_samples(self):
        entry = boss(variable_respawn=True, last_kill=100000, end=0)
        with self.assertRaises(ValueError):
            observe_respawn(entry, 110000, 110000)
        with self.assertRaises(ValueError):
            observe_respawn(boss(), 110000, 110000)

    def test_bad_samples_are_ignored_and_last_twenty_valid_cycles_are_used(self):
        samples = [{"killed_at": i * 10000, "spawned_at": i * 10000 + 1000} for i in range(1, 25)]
        samples += [{"killed_at": 1, "spawned_at": float("inf")}, {}, {"killed_at": 1, "spawned_at": 99999999}]
        cleaned = clean_samples(samples)
        self.assertEqual(len(cleaned), 20)
        self.assertEqual(cleaned[0]["killed_at"], 50000)

    def test_learned_estimates_do_not_leak_between_profiles_or_channels(self):
        app = bare_app()
        second = app.profile_state["profiles"][1]["id"]
        learned = boss(variable_respawn=True, respawn_samples=[{"killed_at": 10000, "spawned_at": 16000}])
        other = boss(second, "b", variable_respawn=True)
        channel2 = ymir.clone_for_channel(learned, "CHN 2")
        app.bosses = [learned, other, channel2]
        with patch.object(ymir.time, "time", return_value=100000):
            for entry in app.bosses:
                app.start(entry)
        self.assertEqual([b["end"] for b in app.bosses], [106000, 110800, 110800])

    def test_observation_updates_matching_history_and_marks_available_without_alert_replay(self):
        app = bare_app()
        entry = boss(variable_respawn=True)
        app.bosses = [entry]
        with patch.object(ymir.time, "time", return_value=100000):
            app.start(entry)
        with patch.object(ymir.time, "time", return_value=109600):
            app.confirm_respawn(entry)
            app.check_alerts()
        self.assertEqual(app.history[0]["observed_respawn_at"], 109600)
        self.assertEqual(app.history[0]["respawn_at"], 110800)
        app.notify.assert_not_called()

    def test_samples_survive_save_and_load(self):
        app = bare_app()
        entry = observe_respawn(boss(variable_respawn=True, last_kill=100000, end=110800), 109600, 109600)
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bosses.json"
            file.write_text(json.dumps([entry]))
            with patch.object(ymir, "DATA_FILE", file):
                loaded = app.load()[0]
        self.assertEqual(respawn_statistics(loaded)["mean"], 9600)
        self.assertEqual(loaded["spawn_for"], 100000)

    def test_variable_alert_is_explicitly_an_estimate(self):
        app = bare_app()
        app.bosses = [boss(variable_respawn=True, last_kill=100, end=1000)]
        with patch.object(ymir.time, "time", return_value=1000):
            app.check_alerts()
        self.assertEqual(app.notify.call_args.args[1], "Janela estimada de respawn")
        self.assertIn("não garante", app.notify.call_args.args[2])

    def test_confirmed_spawn_time_is_not_overwritten_by_editing_reference_duration(self):
        app = bare_app()
        entry = observe_respawn(boss(variable_respawn=True, last_kill=100000, end=110800), 109600, 109600)
        app.bosses = [entry]
        with patch.object(ymir.time, "time", return_value=120000):
            app.change_respawn_duration(entry, 200)
        self.assertEqual(entry["end"], 109600)
        self.assertEqual(respawn_seconds(entry), 9600)
