import contextlib
import copy
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir
from ymir_alerts import countdown_text


class VisibleAlertTests(unittest.TestCase):
    def test_popup_and_sound_are_not_replaced_by_successful_native_toast(self):
        for success in (True, False):
            app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
            app.sound = Mock()
            app.show_respawn_alert = Mock()
            app.send_native_toast = Mock(return_value=success)
            sample = {"id": "boss", "end": 12345}
            app.notify("Guardião • SA012 • CHN 1", "Falta 1 minuto!", "Previsão em breve", boss=sample)
            app.sound.assert_called_once()
            app.show_respawn_alert.assert_called_once_with("Guardião • SA012 • CHN 1", "Falta 1 minuto!",
                                                          "Previsão em breve", boss=sample)
            app.send_native_toast.assert_called_once()

    def test_countdown_distinguishes_estimated_and_confirmed_deadlines(self):
        self.assertEqual(countdown_text(1060, 1000), "NASCE EM 01:00")
        self.assertEqual(countdown_text(1060, 1000, True), "PREVISÃO EM ~01:00")
        self.assertEqual(countdown_text(1000, 1001), "BOSS DISPONÍVEL")
        self.assertEqual(countdown_text(1000, 1001, True), "PREVISÃO / CONFIRA NO JOGO")

    def test_preview_does_not_modify_saved_timers_or_history(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = [{"id": "a", "name": "Guardião", "minutes": 180, "category": ymir.MYRKHEIMR,
                       "channel": "CHN 2", "end": 20000, "last_kill": 9200}]
        app.history = [{"boss_id": "a", "killed_at": 9200}]
        app.notify = Mock()
        before = copy.deepcopy((app.bosses, app.history))
        app.test_respawn_alert()
        self.assertEqual((app.bosses, app.history), before)
        self.assertEqual(app.notify.call_args.kwargs["boss"]["id"], "alert-preview")
        self.assertIn("CHN 2", app.notify.call_args.args[0])


@unittest.skipUnless(os.environ.get("YMIR_GUI_TESTS") == "1", "Requires a desktop display")
class VisibleAlertUITests(unittest.TestCase):
    def test_panel_shows_while_app_is_hidden_and_combines_alerts(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            folder = Path(tmp)
            stack.enter_context(patch.multiple(ymir, DATA_DIR=folder, DATA_FILE=folder / "bosses.json",
                                              HISTORY_FILE=folder / "history.json", UPDATE_SETTINGS=folder / "updates.json"))
            for method in ("init_tray", "check_updates", "sound", "send_native_toast"):
                stack.enter_context(patch.object(ymir.BossTimerApp, method))
            app = ymir.BossTimerApp()
            try:
                app.rename_account("Völva", "SA012")
                second_pid = app.create_account("Conta 2", "EU005")
                now = time.time()
                first = {"id": "one", "profile_id": "default", "name": "Guardião do Túmulo",
                         "category": ymir.TOMB_REGION, "channel": "CHN 1", "end": now + 60}
                second = {"id": "two", "profile_id": second_pid, "name": "Guardião de Myrkheimr",
                          "category": ymir.MYRKHEIMR, "channel": "CHN 2", "end": now + 45,
                          "variable_respawn": True, "last_kill": now - 100, "spawn_for": 0}
                app.withdraw()
                app.update()
                foreground = None
                if os.name == "nt":
                    import ctypes
                    get_foreground = ctypes.windll.user32.GetForegroundWindow
                    get_foreground.argtypes, get_foreground.restype = [], ctypes.c_void_p
                    foreground = get_foreground()
                app.notify(app.alert_identity(first), "Falta 1 minuto!", "O boss está para nascer.", boss=first)
                app.notify(app.alert_identity(second), "Previsão de respawn em 1 minuto", "Previsão pela média.", boss=second)
                app.update()
                panel = app._alert_panel
                self.assertEqual(app.state(), "withdrawn")
                self.assertTrue(panel.window.winfo_viewable())
                if foreground:
                    self.assertEqual(get_foreground(), foreground)
                self.assertTrue(panel.window.attributes("-topmost"))
                self.assertEqual(len(panel.entries), 2)
                self.assertIn("EU005", panel.entries[0]["context"])
                self.assertIn("CHN 2", panel.entries[0]["context"])
                self.assertIn("SA012", panel.entries[1]["context"])
                self.assertIn("CHN 1", panel.entries[1]["context"])
                self.assertIn("PREVISÃO", panel.countdown_labels[0][1].cget("text"))
                self.assertEqual(app.sound.call_count, 2)
                app.notify(app.alert_identity(first), "Atualizado", "Mesmo ciclo, um único card", boss=first)
                app.update()
                self.assertEqual(len(panel.entries), 2)
                screenshot_dir = os.environ.get("YMIR_UI_SCREENSHOT_DIR")
                if screenshot_dir:
                    from PIL import ImageGrab
                    output = Path(screenshot_dir)
                    output.mkdir(parents=True, exist_ok=True)
                    ImageGrab.grab(bbox=(panel.window.winfo_rootx(), panel.window.winfo_rooty(),
                                        panel.window.winfo_rootx() + panel.window.winfo_width(),
                                        panel.window.winfo_rooty() + panel.window.winfo_height())).save(output / "alert-panel.png")
                panel.close_at = time.monotonic() - 1
                panel._tick()
                self.assertEqual(panel.window.state(), "withdrawn")
                self.assertEqual(panel.entries, [])
            finally:
                app.quit_app()
