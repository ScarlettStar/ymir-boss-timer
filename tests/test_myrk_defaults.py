import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir


class MyrkVariableDefaultsTests(unittest.TestCase):
    def app(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app._channel_migrated = app._floor_migrated = app._myrk_variable_migrated = False
        return app

    def load(self, entries):
        app = self.app()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bosses.json"
            path.write_text(json.dumps(entries), encoding="utf-8")
            with patch.object(ymir, "DATA_FILE", path):
                loaded = app.load()
        return app, loaded

    def test_all_accounts_and_channels_migrate_without_changing_running_times(self):
        entries = [dict(id=f"{pid}-{channel}", profile_id=pid, name="Chefe", minutes=180,
                        category=ymir.MYRKHEIMR, channel=channel, end=20000, last_kill=9200,
                        warned_for=0, finished_for=0, variable_respawn=False)
                   for pid in ("default", "second") for channel in ymir.CHANNELS]
        before = copy.deepcopy(entries)
        app, loaded = self.load(entries)
        self.assertEqual(len(loaded), 4)
        self.assertTrue(app._myrk_variable_migrated)
        for original, changed in zip(before, loaded):
            self.assertTrue(changed["variable_respawn"])
            self.assertTrue(changed["myrk_variable_v1"])
            for key in ("id", "profile_id", "minutes", "end", "last_kill", "channel"):
                self.assertEqual(changed[key], original[key])

    def test_observations_and_confirmed_spawn_are_preserved(self):
        entry = dict(id="a", name="Chefe", minutes=180, category=ymir.MYRKHEIMR,
                     channel="CHN 1", end=19600, last_kill=10000, spawn_for=10000,
                     respawn_samples=[{"killed_at": 10000, "spawned_at": 19600}])
        _, loaded = self.load([entry])
        self.assertEqual(loaded[0]["respawn_samples"], entry["respawn_samples"])
        self.assertEqual(loaded[0]["spawn_for"], 10000)
        self.assertEqual(loaded[0]["end"], 19600)

    def test_migration_is_not_repeated_on_later_opens(self):
        entry = dict(id="a", name="Chefe", minutes=180, category=ymir.MYRKHEIMR, channel="CHN 1")
        _, once = self.load([entry])
        app, twice = self.load(once)
        self.assertFalse(app._myrk_variable_migrated)
        self.assertEqual(once, twice)

    def test_other_regions_are_not_changed(self):
        entries = [dict(id=str(i), name="Outro", minutes=90, category=region,
                        variable_respawn=False, floor="P1")
                   for i, region in enumerate((ymir.CATEGORIES[0], ymir.FOLKVANGR, "Nidavellir"))]
        app, loaded = self.load(entries)
        self.assertFalse(app._myrk_variable_migrated)
        self.assertFalse(any(b["variable_respawn"] for b in loaded))

    def test_new_myrk_boss_always_starts_variable_in_both_channels(self):
        app = self.app()
        app.bosses = []
        app.name_entry = Mock()
        app.name_entry.get.return_value = "Chefe novo"
        app.minutes_entry = Mock()
        app.minutes_entry.get.return_value = "180"
        app.category_var = Mock()
        app.category_var.get.return_value = ymir.MYRKHEIMR
        app.variable_respawn_var = Mock()
        app.variable_respawn_var.get.return_value = False
        app.save = app.render = Mock()
        app.add_boss()
        self.assertEqual(len(app.bosses), 2)
        self.assertEqual({b["channel"] for b in app.bosses}, set(ymir.CHANNELS))
        self.assertTrue(all(b["variable_respawn"] and b["myrk_variable_v1"] for b in app.bosses))
        self.assertTrue(all(b["end"] == 0 for b in app.bosses))
