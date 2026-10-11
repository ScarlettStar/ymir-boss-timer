"""Regressões para v2.0 sem abrir janela Tk."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import ymir_boss_timer as ymir


class FloorAndBackupTests(unittest.TestCase):
    def app(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app._channel_migrated = False
        app._floor_migrated = False
        return app

    def test_legacy_folkvangr_migrates_once_and_preserves_old_timer(self):
        previous = [{
            "id": "boss_old", "name": "Boss P", "minutes": 45,
            "category": ymir.FOLKVANGR, "end": 2222,
            "last_kill": 1111, "warned_for": 0, "finished_for": 0
        }]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bosses.json"
            path.write_text(json.dumps(previous), encoding="utf-8")
            with patch.object(ymir, "DATA_FILE", path):
                app = self.app()
                bosses = app.load()
                self.assertTrue(app._floor_migrated)
                self.assertEqual(len(bosses), 4)
                self.assertEqual({b["floor"] for b in bosses}, set(ymir.FLOORS))
                p1 = next(b for b in bosses if b["floor"] == "P1")
                self.assertEqual(p1["id"], "boss_old")
                self.assertEqual((p1["end"], p1["last_kill"]), (2222, 1111))
                for b in bosses:
                    if b["floor"] != "P1":
                        self.assertEqual((b["end"], b["last_kill"]), (0, 0))
                        self.assertNotEqual(b["id"], p1["id"])
                path.write_text(json.dumps(bosses), encoding="utf-8")
                again = self.app()
                reread = again.load()
                self.assertEqual(len(reread), 4)
                self.assertFalse(again._floor_migrated)

    def test_new_folkvangr_boss_creates_all_four_floors(self):
        app = self.app()
        app.bosses = []
        app.name_entry = Mock()
        app.name_entry.get.return_value = "Valquíria"
        app.minutes_entry = Mock()
        app.minutes_entry.get.return_value = "30"
        app.category_var = Mock()
        app.category_var.get.return_value = ymir.FOLKVANGR
        app.save = Mock()
        app.render = Mock()
        app.add_boss()
        self.assertEqual(len(app.bosses), 4)
        self.assertEqual({b["floor"] for b in app.bosses}, set(ymir.FLOORS))
        self.assertEqual(len({b["id"] for b in app.bosses}), 4)
        self.assertEqual({b["end"] for b in app.bosses}, {0})

    def test_timer_and_notice_identify_floor(self):
        app = self.app()
        p1 = {"id": "p1", "name": "V", "minutes": 20,
              "category": ymir.FOLKVANGR, "channel": "", "floor": "P1",
              "end": 0, "last_kill": 0, "warned_for": 0, "finished_for": 0}
        p4 = ymir.clone_for_floor(p1, "P4 UNIVERSAL")
        app.bosses = [p1, p4]
        app.history = []
        app.alerted = set()
        app.warning_alerted = set()
        app.save_history = Mock()
        app.render_history = Mock()
        app.save = Mock()
        app.render = Mock()
        app.notify = Mock()
        with patch.object(ymir.time, "time", return_value=1000):
            app.start(p1)
        self.assertEqual(p1["end"], 2200)
        self.assertEqual(p4["end"], 0)
        self.assertEqual(app.history[0]["floor"], "P1")
        p4["end"] = 1050
        with patch.object(ymir.time, "time", return_value=1000):
            app.check_alerts()
        self.assertIn("P4 UNIVERSAL", app.notify.call_args.args[0])

    def test_upcoming_order_by_deadline_and_region(self):
        app = self.app()
        app.bosses = [
            {"name": "Soon", "category": ymir.FOLKVANGR, "floor": "P2", "end": 1100},
            {"name": "Later", "category": ymir.MYRKHEIMR, "channel": "CHN 2", "end": 1300},
            {"name": "Unstarted", "category": ymir.CATEGORIES[0], "end": 0},
            {"name": "Ready", "category": ymir.CATEGORIES[0], "end": 900},
        ]
        data = app.upcoming_bosses(now=1000)
        self.assertEqual([b["name"] for b in data], ["Soon", "Later", "Ready"])
        self.assertIn("P2", ymir.boss_location(data[0]))
        self.assertIn("CHN 2", ymir.boss_location(data[1]))

    def test_backup_files_persist_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root)
            boss_file = data_dir / "bosses.json"
            history_file = data_dir / "history.json"
            boss_file.write_text('["safeguard"]', encoding="utf-8")
            history_file.write_text('[{"a": 1}]', encoding="utf-8")
            with patch.object(ymir, "DATA_DIR", data_dir), \
                 patch.object(ymir, "DATA_FILE", boss_file), \
                 patch.object(ymir, "HISTORY_FILE", history_file):
                folder = ymir.backup_data()
                self.assertIsNotNone(folder)
                self.assertEqual(json.loads((folder / "bosses.json").read_text(encoding="utf-8")), ["safeguard"])
                self.assertEqual(boss_file.read_text(encoding="utf-8"), '["safeguard"]')


if __name__ == "__main__":
    unittest.main()
