"""Testes sem interface gráfica para proteger timers e migração do Ymir Boss Timer."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir


class ChannelTests(unittest.TestCase):
    def app(self):
        # Evita abrir janela Tkinter durante os testes de lógica.
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app._channel_migrated = False
        return app

    def test_legacy_myrkheimr_creates_only_one_inactive_chn2_copy(self):
        old = [{"id": "legacy1", "name": "Guardião", "minutes": 90,
                "category": ymir.MYRKHEIMR, "end": 5000.0, "last_kill": 100.0,
                "warned_for": 0, "finished_for": 0},
               {"id": "universal1", "name": "Outro", "minutes": 20,
                "category": ymir.CATEGORIES[0], "end": 0}]
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bosses.json"
            file.write_text(json.dumps(old), encoding="utf-8")
            with patch.object(ymir, "DATA_FILE", file):
                app = self.app()
                migrated = app.load()
                self.assertTrue(app._channel_migrated)
                self.assertEqual(len(migrated), 3)
                ch1 = next(b for b in migrated if b["category"] == ymir.MYRKHEIMR and b["channel"] == "CHN 1")
                ch2 = next(b for b in migrated if b["category"] == ymir.MYRKHEIMR and b["channel"] == "CHN 2")
                self.assertEqual(ch1["id"], "legacy1")
                self.assertEqual(ch1["end"], 5000)
                self.assertNotEqual(ch1["id"], ch2["id"])
                self.assertEqual((ch2["end"], ch2["last_kill"]), (0, 0))
                self.assertEqual(ch2["minutes"], ch1["minutes"])
                # Depois de salvar, o arquivo não deve se duplicar a cada reabertura.
                file.write_text(json.dumps(migrated), encoding="utf-8")
                again = self.app()
                reread = again.load()
                self.assertEqual(len(reread), 3)
                self.assertFalse(again._channel_migrated)

    def test_new_myrkheimr_boss_creates_both_channels(self):
        app = self.app()
        app.bosses = []
        app.name_entry = Mock()
        app.name_entry.get.return_value = "Chefe"
        app.minutes_entry = Mock()
        app.minutes_entry.get.return_value = "45"
        app.category_var = Mock()
        app.category_var.get.return_value = ymir.MYRKHEIMR
        app.save = Mock()
        app.render = Mock()
        app.add_boss()
        self.assertEqual(len(app.bosses), 2)
        self.assertEqual({b["channel"] for b in app.bosses}, {"CHN 1", "CHN 2"})
        self.assertEqual({b["minutes"] for b in app.bosses}, {45})
        self.assertEqual({b["end"] for b in app.bosses}, {0})
        self.assertNotEqual(app.bosses[0]["id"], app.bosses[1]["id"])

    def test_channel_timers_history_and_notifications_are_independent(self):
        app = self.app()
        first = {"id": "c1", "name": "Boss", "minutes": 10,
                 "category": ymir.MYRKHEIMR, "channel": "CHN 1",
                 "end": 0, "last_kill": 0, "warned_for": 0, "finished_for": 0}
        second = ymir.clone_for_channel(first, "CHN 2")
        app.bosses = [first, second]
        app.history = []
        app.alerted = set()
        app.warning_alerted = set()
        app.save_history = Mock()
        app.render_history = Mock()
        app.save = Mock()
        app.render = Mock()
        app.notify = Mock()

        with patch.object(ymir.time, "time", return_value=1000):
            app.start(first)
        self.assertEqual(first["end"], 1600)
        self.assertEqual(second["end"], 0)
        self.assertEqual(app.history[0]["channel"], "CHN 1")

        second["end"] = 1045  # faltam 45 segundos para o segundo canal.
        with patch.object(ymir.time, "time", return_value=1000):
            app.check_alerts()
        app.notify.assert_called_once()
        self.assertIn("CHN 2", app.notify.call_args.args[0])
        self.assertEqual(first["warned_for"], 0)
        self.assertEqual(second["warned_for"], 1045)


if __name__ == "__main__":
    unittest.main()
