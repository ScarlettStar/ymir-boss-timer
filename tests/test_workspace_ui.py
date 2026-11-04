import contextlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import ymir_boss_timer as ymir
from ymir_models import read_profiles, respawn_statistics


@unittest.skipUnless(os.environ.get("YMIR_GUI_TESTS") == "1", "Requires a desktop display")
class WorkspaceUITests(unittest.TestCase):
    def test_account_switch_custom_region_and_learning_across_restart(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            folder = Path(tmp)
            stack.enter_context(patch.multiple(ymir, DATA_DIR=folder, DATA_FILE=folder / "bosses.json",
                                              HISTORY_FILE=folder / "history.json", UPDATE_SETTINGS=folder / "updates.json"))
            for method in ("init_tray", "check_updates", "notify"):
                stack.enter_context(patch.object(ymir.BossTimerApp, method))
            app = ymir.BossTimerApp()
            try:
                app.update()
                app.rename_account("Völva", "SA012")
                app.add_custom_region("Nidavellir")
                app.name_entry.insert(0, "Guardião de teste")
                app.minutes_entry.insert(0, "180")
                app.boss_kind_var.set("Elite")
                app.variable_respawn_var.set(True)
                app.add_boss()
                first = app.profile_bosses()[0]
                self.assertEqual(first["category"], "Nidavellir")
                self.assertEqual(first["kind"], "Elite")
                now = time.time()
                app.record_kill(first, now - 160 * 60)
                app.observation_dialog(first)
                observation = next(w for w in app.winfo_children()
                                   if isinstance(w, ymir.tk.Toplevel) and w.title() == "Confirmar reaparecimento")
                confirm = next(w for w in observation.winfo_children()
                               if isinstance(w, ymir.tk.Button) and w.cget("text") == "Confirmar reaparecimento")
                confirm.invoke()
                self.assertFalse(observation.winfo_exists())
                self.assertEqual(respawn_statistics(first)["count"], 1)
                self.assertAlmostEqual(respawn_statistics(first)["mean"], 160 * 60, delta=5)
                app.start(first)
                first_end = first["end"]
                other_pid = app.create_account("Conta 2", "EU005", copy_catalog=True)
                self.assertEqual(app.active_profile_id(), other_pid)
                second = app.profile_bosses()[0]
                self.assertNotEqual(first["id"], second["id"])
                self.assertEqual(second["end"], 0)
                self.assertEqual(second["respawn_samples"], [])
                self.assertEqual(app.profile_history(), [])
                self.assertIn("Nidavellir", app.category_choices())
                app.start(second)
                self.assertAlmostEqual(second["end"] - time.time(), 180 * 60, delta=5)
                app.filter_kind.set("Elite")
                app.apply_filters()
                self.assertEqual(list(app.time_labels), [second["id"]])
                app.switch_tab("upcoming")
                self.assertEqual(len(app.upcoming_table.get_children()), 1)
                app.switch_tab("timers")
                app.toggle_overlay()
                app.refresh_overlay()
                self.assertIn("SA012", app.overlay_rows[0][1].cget("text"))
                self.assertIn("EU005", app.overlay_rows[1][1].cget("text"))
                app.close_overlay()
                app.switch_profile("default")
                self.assertEqual(first["end"], first_end)
                self.assertEqual(list(app.time_labels), [first["id"]])
                self.assertEqual(len(app.profile_history()), 2)
                for geometry in ("820x640+5+5", f"{min(1180, app.winfo_screenwidth() - 20)}x{min(850, app.winfo_screenheight() - 80)}+5+5"):
                    app.geometry(geometry)
                    app.update()
                    self.assertGreater(app.canvas.winfo_height(), 150)
                screenshot_dir = os.environ.get("YMIR_UI_SCREENSHOT_DIR")
                if screenshot_dir:
                    from PIL import ImageGrab
                    out = Path(screenshot_dir)
                    out.mkdir(parents=True, exist_ok=True)
                    app.update()
                    ImageGrab.grab(bbox=(app.winfo_rootx(), app.winfo_rooty(),
                                        app.winfo_rootx() + app.winfo_width(),
                                        app.winfo_rooty() + app.winfo_height())).save(out / "profiles-learning.png")
            finally:
                app.quit_app()
            # A fresh instance must restore both accounts and every independent timer.
            reopened = ymir.BossTimerApp()
            try:
                self.assertEqual(reopened.active_profile_id(), "default")
                self.assertEqual(len(reopened.bosses), 2)
                self.assertEqual(respawn_statistics(reopened.profile_bosses()[0])["count"], 1)
                self.assertEqual(reopened.profile_bosses()[0]["end"], first_end)
                reopened.switch_profile(other_pid)
                self.assertGreater(reopened.profile_bosses()[0]["end"], time.time())
                self.assertIsNone(respawn_statistics(reopened.profile_bosses()[0]))
                self.assertEqual(read_profiles(folder / "profiles.json")["active"], other_pid)
            finally:
                reopened.quit_app()
