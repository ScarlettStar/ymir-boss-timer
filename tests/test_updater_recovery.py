"""Regressão do atualizador PowerShell contra falsas falhas do PyInstaller."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import ymir_boss_timer as ymir


class UpdaterRecoveryTest(unittest.TestCase):
    def test_external_script_waits_version_marker_and_writes_log(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.latest_release = {"version": "v2.1.1"}
        app.quit_app = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ymir.tempfile, "gettempdir", return_value=tmp), \
                 patch.object(ymir.subprocess, "Popen", return_value=Mock()):
                app._launch_update(Path(tmp) / "YmirBossTimer.exe.new",
                                   Path(tmp) / "YmirBossTimer.exe")
                scripts = list(Path(tmp).glob("ymir-update-*.ps1"))
                self.assertEqual(len(scripts), 1)
                raw = scripts[0].read_bytes()
                self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
                script = raw.decode("utf-8-sig")
                self.assertIn("$expected = '2.1.1'", script)
                self.assertIn("$written -eq $expected", script)
                self.assertIn("Get-FileHash", script)
                self.assertIn("update.log", script)
                self.assertIn("A nova versão não iniciou corretamente", script)
                self.assertNotIn("if ($child.HasExited) { break }", script)
        app.quit_app.assert_called_once()


if __name__ == "__main__":
    unittest.main()
