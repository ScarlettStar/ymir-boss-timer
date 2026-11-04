import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir
from ymir_models import default_profiles, add_profile, uses_channels, TOMB_REGION
from ymir_channels import channel_view_items


def entry(bid="a", region=TOMB_REGION, channel="", pid="default", **extra):
    return {"id": bid, "name": "Guardião", "category": region, "channel": channel,
            "profile_id": pid, "minutes": 180, "end": 20800, "last_kill": 10000, **extra}


class QuickChannelTests(unittest.TestCase):
    def app(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.profile_state = default_profiles()
        app.bosses = []
        app._channel_migrated = app._floor_migrated = app._myrk_variable_migrated = False
        app.save = app.render = app.apply_filters = Mock()
        app.filter_place = Mock()
        app.filter_place.get.return_value = "Todos"
        return app

    def load(self, entries):
        app = self.app()
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bosses.json"
            file.write_text(json.dumps(entries), encoding="utf-8")
            with patch.object(ymir, "DATA_FILE", file):
                app.bosses = app.load()
        return app

    def test_tomb_aliases_with_or_without_accents_use_channels(self):
        for region in (TOMB_REGION, "Tumulo do Rei", "Bosses Túmulo do Rei", ymir.MYRKHEIMR):
            self.assertTrue(uses_channels(region))
        self.assertFalse(uses_channels(ymir.FOLKVANGR))
        self.assertFalse(uses_channels("Nidavellir"))

    def test_tomb_migrates_both_accounts_without_starting_new_channel(self):
        rows = [entry(pid="default", variable_respawn=True,
                      respawn_samples=[{"killed_at": 100, "spawned_at": 10100}]),
                entry("b", pid="second")]
        app = self.load(rows)
        self.assertTrue(app._channel_migrated)
        self.assertEqual(len(app.bosses), 4)
        self.assertEqual(len({b["id"] for b in app.bosses}), 4)
        for pid in ("default", "second"):
            first = next(b for b in app.bosses if b["profile_id"] == pid and b["channel"] == "CHN 1")
            second = next(b for b in app.bosses if b["profile_id"] == pid and b["channel"] == "CHN 2")
            self.assertEqual(first["end"], 20800)
            self.assertEqual(first["last_kill"], 10000)
            self.assertEqual(second["end"], 0)
            self.assertEqual(second["last_kill"], 0)
            self.assertEqual(second["respawn_samples"], [])
        self.assertEqual(app.bosses[0]["respawn_samples"], rows[0]["respawn_samples"])
        reread = self.load(app.bosses)
        self.assertEqual(reread.bosses, app.bosses)
        self.assertFalse(reread._channel_migrated)

    def test_existing_tomb_chn2_is_not_duplicated_and_its_timer_is_preserved(self):
        app = self.load([entry(), entry("second-channel", channel="CHN 2", end=22000)])
        self.assertEqual(len(app.bosses), 2)
        self.assertEqual(app.bosses[0]["channel"], "CHN 1")
        self.assertEqual(app.bosses[1]["end"], 22000)

    def test_legacy_tomb_spelling_and_ids_are_kept(self):
        app = self.load([entry(region="Bosses Tumulo do Rei")])
        self.assertEqual(app.bosses[0]["id"], "a")
        self.assertEqual(app.bosses[0]["category"], "Bosses Tumulo do Rei")
        self.assertIn("Bosses Tumulo do Rei", app.category_choices())
        self.assertNotIn(TOMB_REGION, app.category_choices())
        self.assertIn("CHN 1", ymir.boss_location(app.bosses[0]))

    def test_new_tomb_boss_creates_two_independent_channels(self):
        app = self.app()
        app.name_entry, app.minutes_entry, app.category_var = Mock(), Mock(), Mock()
        app.name_entry.get.return_value = "Sentinela"
        app.minutes_entry.get.return_value = "180"
        app.category_var.get.return_value = TOMB_REGION
        app.add_boss()
        self.assertEqual(len(app.bosses), 2)
        self.assertEqual({b["channel"] for b in app.bosses}, {"CHN 1", "CHN 2"})
        self.assertTrue(all(b["end"] == 0 for b in app.bosses))
        self.assertFalse(any(b["variable_respawn"] for b in app.bosses))

    def test_view_switch_only_hides_other_channel_in_myrk_and_tomb(self):
        rows = [entry("m1", ymir.MYRKHEIMR, "CHN 1"), entry("m2", ymir.MYRKHEIMR, "CHN 2"),
                entry("t1", TOMB_REGION, "CHN 1"), entry("t2", TOMB_REGION, "CHN 2"),
                entry("floor", ymir.FOLKVANGR), entry("universal", ymir.CATEGORIES[0])]
        original = copy.deepcopy(rows)
        self.assertEqual([b["id"] for b in channel_view_items(rows, "CHN 1")], ["m1", "t1", "floor", "universal"])
        self.assertEqual([b["id"] for b in channel_view_items(rows, "CHN 2")], ["m2", "t2", "floor", "universal"])
        self.assertEqual(channel_view_items(rows, "Todos"), rows)
        self.assertEqual(rows, original)

    def test_channel_choice_is_persisted_per_account_without_touching_bosses(self):
        app = self.app()
        state, second = add_profile(app.profile_state, "Conta 2", "EU005")
        state["active"] = "default"
        app.profile_state = state
        app.bosses = [entry(channel="CHN 1"), entry("b", channel="CHN 2", pid=second)]
        original = copy.deepcopy(app.bosses)
        with tempfile.TemporaryDirectory() as tmp, patch.object(ymir, "DATA_DIR", Path(tmp)):
            app.choose_channel("CHN 2")
            self.assertEqual(app.current_channel_view(), "CHN 2")
            state = copy.deepcopy(app.profile_state)
            state["active"] = second
            app.persist_profile_state(state)
            self.assertEqual(app.current_channel_view(), "Todos")
            app.choose_channel("CHN 1")
            state = copy.deepcopy(app.profile_state)
            state["active"] = "default"
            app.persist_profile_state(state)
            self.assertEqual(app.current_channel_view(), "CHN 2")
        self.assertEqual(app.bosses, original)

    def test_tomb_alerts_and_history_identify_both_channels(self):
        app = self.app()
        app.bosses = [entry(channel="CHN 1", end=999), entry("b", channel="CHN 2", end=1030)]
        app.history = []
        app.alerted, app.warning_alerted = set(), set()
        app.notify = Mock()
        app.save_history = app.render_history = Mock()
        with patch.object(ymir.time, "time", return_value=1000):
            app.check_alerts()
            self.assertIn("CHN 1", app.notify.call_args_list[0].args[0])
            self.assertIn("CHN 2", app.notify.call_args_list[1].args[0])
            app.start(app.bosses[1])
        self.assertEqual(app.history[0]["channel"], "CHN 2")

    def test_batch_duration_edit_is_scoped_to_account_in_tomb(self):
        app = self.app()
        first, second = entry(channel="CHN 1"), entry("b", channel="CHN 2")
        other_account = entry("c", channel="CHN 1", pid="other")
        app.bosses = [first, second, other_account]
        app.history = []
        app.alerted, app.warning_alerted = set(), set()
        app.change_respawn_duration(first, 200, all_copies=True)
        self.assertEqual([b["minutes"] for b in app.bosses], [200, 200, 180])
