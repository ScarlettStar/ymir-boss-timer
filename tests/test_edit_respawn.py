"""Testes de edição de duração do respawn (v2.1)."""
import unittest
from unittest.mock import Mock, patch
import ymir_boss_timer as ymir


def boss(name, cat, ident, minutes=45, killed=1000, end=3700, channel="", floor=""):
    return {"id": ident, "name": name, "category": cat, "minutes": minutes,
            "last_kill": killed, "end": end, "warned_for": end,
            "finished_for": 0, "channel": channel, "floor": floor}


class EditRespawnTests(unittest.TestCase):
    def app(self, bosses):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = bosses
        app.history = []
        app.save = Mock()
        app.save_history = Mock()
        app.render_history = Mock()
        app.render = Mock()
        app.alerted = set()
        app.warning_alerted = set()
        return app

    def test_corrects_running_timer_from_kill_time_not_edit_time(self):
        b = boss("Valquíria", ymir.FOLKVANGR, "p1", 45, 1000, 3700, floor="P1")
        app = self.app([b])
        app.history.append({"boss_id": "p1", "killed_at": 1000, "respawn_at": 3700})
        with patch.object(ymir.time, "time", return_value=1500):
            updated = app.change_respawn_duration(b, 60, all_copies=False)
        self.assertEqual(updated, 1)
        self.assertEqual(b["end"], 4600)
        self.assertEqual(b["minutes"], 60)
        self.assertEqual(b["last_kill"], 1000)
        self.assertEqual(app.history[0]["respawn_at"], 4600)
        self.assertEqual(b["warned_for"], 0)
        app.save.assert_called_once()
        app.save_history.assert_called_once()

    def test_each_channel_uses_its_own_death_time(self):
        c1 = boss("Fera", ymir.MYRKHEIMR, "c1", killed=1000, end=3700, channel="CHN 1")
        c2 = boss("Fera", ymir.MYRKHEIMR, "c2", killed=1400, end=4100, channel="CHN 2")
        other = boss("Outro", ymir.MYRKHEIMR, "other", channel="CHN 2")
        app = self.app([c1, c2, other])
        with patch.object(ymir.time, "time", return_value=1800):
            updated = app.change_respawn_duration(c1, 70, all_copies=True)
        self.assertEqual(updated, 2)
        self.assertEqual((c1["end"], c2["end"]), (5200, 5600))
        self.assertEqual((c1["minutes"], c2["minutes"]), (70, 70))
        self.assertEqual(other["minutes"], 45)

    def test_all_four_floors_can_be_changed_without_starting_inactive_timers(self):
        p1 = boss("Wyvern", ymir.FOLKVANGR, "p1", floor="P1")
        others = [ymir.clone_for_floor(p1, floor) for floor in ymir.FLOORS[1:]]
        app = self.app([p1, *others])
        with patch.object(ymir.time, "time", return_value=1200):
            count = app.change_respawn_duration(p1, 50, all_copies=True)
        self.assertEqual(count, 4)
        self.assertEqual({b["minutes"] for b in app.bosses}, {50})
        self.assertEqual(p1["end"], 4000)
        self.assertEqual([b["end"] for b in others], [0, 0, 0])

    def test_edit_one_floor_only(self):
        p1 = boss("Boss", ymir.FOLKVANGR, "p1", floor="P1")
        p2 = boss("Boss", ymir.FOLKVANGR, "p2", floor="P2")
        app = self.app([p1, p2])
        with patch.object(ymir.time, "time", return_value=1200):
            changed = app.change_respawn_duration(p2, 38, all_copies=False)
        self.assertEqual(changed, 1)
        self.assertEqual(p1["minutes"], 45)
        self.assertEqual(p2["minutes"], 38)

    def test_old_expired_timers_do_not_duplicate_an_old_notice(self):
        b = boss("Fera", ymir.CATEGORIES[0], "u1", killed=1000, end=3700)
        app = self.app([b])
        with patch.object(ymir.time, "time", return_value=6000):
            app.change_respawn_duration(b, 50)
        self.assertEqual(b["end"], 4000)
        self.assertEqual(b["finished_for"], 4000)

    def test_reset_boss_stays_unstarted_after_edit(self):
        b = boss("Fera", ymir.CATEGORIES[0], "u1", killed=1000, end=0)
        app = self.app([b])
        with patch.object(ymir.time, "time", return_value=1200):
            app.change_respawn_duration(b, 65)
        self.assertEqual(b["end"], 0)
        self.assertEqual(b["minutes"], 65)

    def test_rejects_invalid_durations_without_mutation(self):
        b = boss("Fera", ymir.CATEGORIES[0], "u1")
        app = self.app([b])
        for invalid in (0, -1, 10081, 1.5, "xx", True):
            with self.assertRaises(ValueError):
                app.change_respawn_duration(b, invalid)
        self.assertEqual(b["minutes"], 45)
        app.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
