import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir
from ymir_smart import select_bosses, previous_death_timestamp
from ymir_updates import can_auto_install


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.bosses = [
            dict(id="a", name="Guardião", category=ymir.MYRKHEIMR, channel="CHN 1", end=1300),
            dict(id="b", name="Guardião", category=ymir.MYRKHEIMR, channel="CHN 2", end=1000, favorite=True),
            dict(id="c", name="Dragão", category=ymir.FOLKVANGR, floor="P2", end=0),
        ]

    def ids(self, **kwargs):
        return [b["id"] for b in select_bosses(self.bosses, 1000, **kwargs)]

    def test_search_ignores_accents_and_matches_location(self):
        self.assertEqual(self.ids(query="GUARDIAO chn 2"), ["b"])
        self.assertEqual(self.ids(query="dragao"), ["c"])
        self.assertEqual(self.ids(query="inexistente"), [])

    def test_region_place_and_favorites_combine_without_mutating_data(self):
        snapshot = json.dumps(self.bosses)
        self.assertEqual(self.ids(region=ymir.MYRKHEIMR, place="CHN 1"), ["a"])
        self.assertEqual(self.ids(place="P2"), ["c"])
        self.assertEqual(self.ids(favorites=True), ["b"])
        self.assertEqual(self.ids(region=ymir.FOLKVANGR, place="CHN 1"), [])
        self.assertEqual(json.dumps(self.bosses), snapshot)

    def test_status_boundaries_and_stable_favorite_priority(self):
        self.assertEqual(self.ids(), ["b", "a", "c"])
        self.assertEqual(self.ids(status="Ativos"), ["a"])
        self.assertEqual(self.ids(status="Disponíveis"), ["b"])
        self.assertEqual(self.ids(status="Aguardando"), ["c"])
        self.assertEqual(self.ids(status="Em até 5 min"), ["a"])
        self.bosses[0]["end"] = 1301
        self.assertEqual(self.ids(status="Em até 5 min"), [])

    def test_overlay_prioritizes_favorites_without_changing_global_chronology(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = self.bosses
        self.assertEqual([b["id"] for b in app.upcoming_bosses(1000)], ["a", "b"])
        self.assertEqual([b["id"] for b in app.overlay_bosses(1000)], ["b", "a"])

    def test_favorite_survives_save_and_load_with_backward_compatibility(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app._channel_migrated = app._floor_migrated = False
        app.bosses = [dict(id="x", name="Boss", minutes=10, end=0, category=ymir.CATEGORIES[0])]
        app.render = app.refresh_overlay = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch.object(ymir, "DATA_DIR", folder), patch.object(ymir, "DATA_FILE", folder / "bosses.json"):
                app.toggle_favorite(app.bosses[0])
                self.assertTrue(app.load()[0]["favorite"])
                self.assertEqual(app.load()[0]["id"], "x")
                app.toggle_favorite(app.bosses[0])
                self.assertFalse(app.load()[0]["favorite"])


class PreviousDeathTests(unittest.TestCase):
    def app(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = [dict(id="one", name="Boss", minutes=10, end=0,
                           category=ymir.MYRKHEIMR, channel="CHN 1")]
        app.bosses.append(ymir.clone_for_channel(app.bosses[0], "CHN 2"))
        app.history = []
        app.alerted = set()
        app.warning_alerted = set()
        for method in ("save", "save_history", "render", "render_history", "notify"):
            setattr(app, method, Mock())
        return app

    def test_seven_minutes_ago_preserves_independent_channel_and_history(self):
        app = self.app()
        with patch.object(ymir.time, "time", return_value=10000):
            app.record_kill(app.bosses[0], previous_death_timestamp(7, 10000))
        self.assertEqual(app.bosses[0]["end"], 10180)
        self.assertEqual(app.bosses[1]["end"], 0)
        self.assertEqual(app.history[0]["killed_at"], 9580)
        self.assertEqual(app.history[0]["respawn_at"], 10180)
        self.assertEqual(app.history[0]["channel"], "CHN 1")

    def test_already_expired_respawn_does_not_replay_old_alerts(self):
        app = self.app()
        with patch.object(ymir.time, "time", return_value=10000):
            app.record_kill(app.bosses[0], previous_death_timestamp(20, 10000))
            app.check_alerts()
        app.notify.assert_not_called()
        self.assertEqual(app.bosses[0]["end"], 9400)

    def test_new_one_minute_timer_still_issues_its_normal_warning(self):
        app = self.app()
        app.bosses[0]["minutes"] = 1
        with patch.object(ymir.time, "time", return_value=10000):
            app.start(app.bosses[0])
            app.check_alerts()
        app.notify.assert_called_once()

    def test_invalid_times_leave_boss_and_history_unchanged(self):
        app = self.app()
        original = json.dumps(app.bosses)
        for value in (True, -1, 10081, 1.5, "7"):
            with self.assertRaises(ValueError):
                previous_death_timestamp(value, 10000)
        with patch.object(ymir.time, "time", return_value=10000):
            for value in (10001, 0, float("nan"), True):
                with self.assertRaises(ValueError):
                    app.record_kill(app.bosses[0], value)
        self.assertEqual(json.dumps(app.bosses), original)
        self.assertEqual(app.history, [])

    def test_retroactive_history_is_chronological_and_other_boss_alerts_stay_global(self):
        app = self.app()
        with patch.object(ymir.time, "time", return_value=10000):
            app.start(app.bosses[1])
            app.record_kill(app.bosses[0], 9580)
            app.bosses[1]["end"] = 10030
            app.check_alerts()
        self.assertEqual([r["killed_at"] for r in app.history], [9580, 10000])
        self.assertIn("CHN 2", app.notify.call_args.args[0])


class AutomaticUpdateTests(unittest.TestCase):
    def test_no_install_with_active_timer_or_recent_activity(self):
        self.assertFalse(can_auto_install([{"end": 1001}], 1000, 0))
        self.assertFalse(can_auto_install([], 1000, 881))
        self.assertTrue(can_auto_install([{"end": 999}], 1000, 880))

    def test_boss_started_during_download_prevents_restart_and_removes_stage(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = [{"end": 2000}]
        app.auto_update_idle_since = 0
        app.auto_update_enabled = Mock()
        app.auto_update_enabled.get.return_value = True
        app.update_busy = True
        app.update_status = Mock()
        app._launch_update = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "test.exe.new"
            stage.write_bytes(b"verified-stage")
            with patch.object(ymir.time, "time", return_value=1000):
                app._apply_downloaded_update(stage, Path(tmp) / "test.exe", auto=True)
            self.assertFalse(stage.exists())
        self.assertFalse(app.update_busy)
        app._launch_update.assert_not_called()

    def test_manual_or_idle_verified_update_can_launch(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = []
        app.auto_update_idle_since = 0
        app.auto_update_enabled = Mock()
        app.auto_update_enabled.get.return_value = True
        app._launch_update = Mock()
        with patch.object(ymir.time, "time", return_value=1000):
            app._apply_downloaded_update("stage", "target", auto=True)
        app._launch_update.assert_called_once_with("stage", "target")

    def test_disabling_automatic_updates_during_download_cancels_install(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = []
        app.auto_update_idle_since = 0
        app.auto_update_enabled = Mock()
        app.auto_update_enabled.get.return_value = False
        app.update_status = Mock()
        app._launch_update = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "test.exe.new"
            stage.write_bytes(b"verified")
            with patch.object(ymir.time, "time", return_value=1000):
                app._apply_downloaded_update(stage, Path(tmp) / "test.exe", auto=True)
            self.assertFalse(stage.exists())
        app._launch_update.assert_not_called()

    def test_background_download_error_is_logged_without_repeated_popup(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app._install_is_automatic = True
        app.update_status = Mock()
        with tempfile.TemporaryDirectory() as tmp, patch.object(ymir, "DATA_DIR", Path(tmp)), \
                patch.object(ymir.messagebox, "showerror") as popup, \
                patch.object(ymir.time, "time", return_value=1000):
            app._update_failed("network unavailable")
            self.assertEqual(app.update_retry_after, 2800)
            self.assertIn("network unavailable", (Path(tmp) / "update.log").read_text())
            popup.assert_not_called()

    def test_rollback_marker_blocks_same_version_in_auto_mode(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.latest_release = {"version": "v3.1.0"}
        app.update_busy = False
        app.bosses = []
        app.auto_update_idle_since = 0
        app.auto_update_enabled = Mock()
        app.auto_update_enabled.get.return_value = True
        app.update_retry_after = 0
        app.failed_update_version = Mock(return_value="3.1.0")
        with patch.object(ymir.sys, "frozen", True, create=True), \
                patch.object(ymir.os, "name", "nt"), \
                patch.object(ymir.time, "time", return_value=1000), \
                patch.object(ymir.threading, "Thread") as thread:
            app.install_update(auto=True)
            thread.assert_not_called()
