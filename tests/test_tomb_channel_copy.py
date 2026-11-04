import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir
from ymir_models import default_profiles, missing_tomb_channel_copies, TOMB_REGION


def boss(bid="a", pid="default", channel="CHN 1", **fields):
    return {"id": bid, "profile_id": pid, "name": "Sentinela", "category": TOMB_REGION,
            "kind": "Boss", "channel": channel, "minutes": 180, "end": 20800,
            "last_kill": 10000, "warned_for": 20800, "finished_for": 0,
            "variable_respawn": True, "respawn_samples": [{"killed_at": 100, "spawned_at": 9700}],
            "spawn_for": 0, **fields}


class TombChannelCopyTests(unittest.TestCase):
    def app(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.profile_state = default_profiles()
        app.bosses = []
        app._channel_migrated = app._floor_migrated = app._myrk_variable_migrated = False
        for method in ("save", "render", "render_upcoming", "refresh_overlay"):
            setattr(app, method, Mock())
        return app

    def test_copies_same_definition_with_new_identity_and_independent_state(self):
        source = boss()
        before = copy.deepcopy(source)
        copied = missing_tomb_channel_copies([source])[0]
        self.assertEqual(source, before)
        self.assertNotEqual(copied["id"], source["id"])
        self.assertEqual(copied["channel"], "CHN 2")
        for key in ("name", "category", "kind", "minutes", "variable_respawn", "profile_id"):
            self.assertEqual(copied[key], source[key])
        for key in ("end", "last_kill", "warned_for", "finished_for", "spawn_for"):
            self.assertEqual(copied[key], 0)
        self.assertEqual(copied["respawn_samples"], [])

    def test_existing_chn2_timer_and_learning_are_never_overwritten(self):
        source = boss()
        existing = boss("b", channel="CHN 2", end=30000)
        rows = [source, existing]
        before = copy.deepcopy(rows)
        self.assertEqual(missing_tomb_channel_copies(rows), [])
        self.assertEqual(rows, before)

    def test_copy_is_scoped_by_account_and_kind_and_recognizes_tomb_aliases(self):
        rows = [boss(), boss("other-account", pid="second"),
                boss("elite", kind="Elite"), boss("alias", channel="CHN 2", category="Bosses Tumulo do Rei")]
        copied = missing_tomb_channel_copies(rows, profile_id="default")
        self.assertEqual(len(copied), 1)
        self.assertEqual(copied[0]["kind"], "Elite")
        all_copies = missing_tomb_channel_copies(rows)
        self.assertEqual(len(all_copies), 2)
        self.assertEqual({b["profile_id"] for b in all_copies}, {"default", "second"})

    def test_startup_completes_explicit_chn1_and_is_idempotent(self):
        app = self.app()
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bosses.json"
            file.write_text(json.dumps([boss()]))
            with patch.object(ymir, "DATA_FILE", file):
                rows = app.load()
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["id"], "a")
                self.assertEqual(rows[0]["end"], 20800)
                self.assertEqual(rows[1]["end"], 0)
                self.assertTrue(app._channel_migrated)
                file.write_text(json.dumps(rows))
                app._channel_migrated = False
                self.assertEqual(app.load(), rows)
                self.assertFalse(app._channel_migrated)

    def test_explicit_button_can_restore_a_deleted_copy_without_auto_resurrection(self):
        source = boss(tomb_channel_copy_v1=True)
        self.assertEqual(missing_tomb_channel_copies([source], unmigrated_only=True), [])
        app = self.app()
        app.bosses = [source]
        self.assertEqual(app.complete_tomb_channel2(), 1)
        self.assertEqual(app.complete_tomb_channel2(), 0)
        self.assertEqual(len(app.bosses), 2)
        self.assertEqual(app.bosses[0]["end"], 20800)

    def test_manual_action_only_completes_the_selected_account(self):
        app = self.app()
        app.bosses = [boss(), boss("second-account", pid="other")]
        self.assertEqual(app.complete_tomb_channel2(), 1)
        self.assertEqual(len([b for b in app.bosses if b["profile_id"] == "other"]), 1)
