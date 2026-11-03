"""Regression checks for presentation without touching the user's saved data."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import ymir_boss_timer as ymir
from ymir_theme import dashboard_counts, respawn_progress


class DashboardTests(unittest.TestCase):
    def test_counts_include_hidden_regions_and_ready_bosses(self):
        bosses = [{"end": 0}, {"end": 999}, {"end": 1000},
                  {"end": 1300}, {"end": 1301}]
        self.assertEqual(dashboard_counts(bosses, 1000), (5, 2, 1, 2))
        self.assertEqual(dashboard_counts([], 1000), (0, 0, 0, 0))

    def test_progress_tracks_elapsed_duration_and_clamps(self):
        boss = {"end": 1600, "minutes": 10}
        self.assertEqual(respawn_progress(boss, 1000), 0)
        self.assertEqual(respawn_progress(boss, 1300), 50)
        self.assertEqual(respawn_progress(boss, 1800), 100)
        self.assertEqual(respawn_progress(boss, 900), 0)
        self.assertEqual(respawn_progress({"end": 0, "minutes": 10}, 1000), 0)


@unittest.skipUnless(os.environ.get("YMIR_GUI_TESTS") == "1", "Requires a desktop display")
class GamerUISmokeTests(unittest.TestCase):
    def test_full_interface_navigation_and_timer_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch.multiple(ymir, DATA_DIR=folder, DATA_FILE=folder / "bosses.json",
                                HISTORY_FILE=folder / "history.json",
                                UPDATE_SETTINGS=folder / "updates.json"), \
                    patch.object(ymir.BossTimerApp, "init_tray"), \
                    patch.object(ymir.BossTimerApp, "check_updates"), \
                    patch.object(ymir.BossTimerApp, "notify"):
                app = ymir.BossTimerApp()
                try:
                    app.update_idletasks()
                    for category in ymir.CATEGORIES:
                        app.category_var.set(category)
                        app.name_entry.insert(0, "Boss de teste")
                        app.minutes_entry.insert(0, "10")
                        app.add_boss()
                    self.assertEqual(len(app.bosses), 7)
                    boss = app.bosses[0]
                    app.start(boss)
                    app.refresh_times()
                    self.assertEqual(app.dashboard_labels[1].cget("text"), "1")
                    self.assertGreater(boss["end"], time.time())
                    self.assertIn(boss["id"], app.progress_bars)
                    for tab in ("upcoming", "history", "timers"):
                        app.switch_tab(tab)
                        app.update_idletasks()
                    app.toggle_overlay()
                    app.refresh_overlay()
                    app.close_overlay()
                    app.open_compact()
                    app.refresh_compact()
                    app.close_compact()
                    app.reset(boss)
                    self.assertEqual(boss["end"], 0)
                    self.assertEqual(len(app.history), 1)
                    app.geometry("820x640")
                    app.update_idletasks()
                finally:
                    app.quit_app()
