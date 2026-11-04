import contextlib
import copy
import io
import json
import os
import queue
import tempfile
import time
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
import ymir_boss_timer as ymir
import ymir_productivity as productivity
from ymir_models import default_profiles, atomic_json
from ymir_productivity import (alert_key, alert_options, tone_wave, read_backup,
                               restore_files, validate_backup, validated_preferences, DEFAULTS)


def sample_backup():
    return {'bosses.json': [{'id': 'a', 'name': 'Guardião', 'minutes': 180,
                             'category': ymir.MYRKHEIMR, 'channel': 'CHN 1',
                             'myrk_variable_v1': True, 'end': 123456, 'last_kill': 100000}],
            'history.json': [{'name': 'Guardião', 'category': ymir.MYRKHEIMR,
                              'killed_at': 100000, 'respawn_at': 123456}],
            'profiles.json': default_profiles(), 'preferences.json': copy.deepcopy(DEFAULTS)}


class ProductivityTests(unittest.TestCase):
    def test_per_boss_options_never_cross_accounts_or_channels(self):
        prefs = copy.deepcopy(DEFAULTS)
        first = {'id': 'a', 'profile_id': 'one'}
        prefs['boss_alerts'][alert_key(first)] = {'lead_seconds': 300, 'volume': 0, 'tone': 'Grave'}
        self.assertEqual(alert_options(prefs, first)['lead_seconds'], 300)
        self.assertEqual(alert_options(prefs, {'id': 'a', 'profile_id': 'two'})['lead_seconds'], 60)
        self.assertEqual(alert_options(prefs, {'id': 'b', 'profile_id': 'one'})['volume'], 70)

    def test_configurable_warning_and_zero_disables_only_early_warning(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.preferences = copy.deepcopy(DEFAULTS)
        boss = {'id': 'a', 'name': 'Guardião', 'end': 1200, 'category': ymir.CATEGORIES[0]}
        app.bosses = [boss]
        app.save = Mock()
        app.notify = Mock()
        with patch('ymir_boss_timer.time.time', return_value=1000):
            app.check_alerts()
            app.notify.assert_not_called()
            app.preferences['lead_seconds'] = 300
            app.check_alerts()
            app.check_alerts()
            self.assertEqual(app.notify.call_count, 1)
        app.preferences['lead_seconds'] = 0
        boss.update(end=1001, warned_for=0)
        app.notify.reset_mock()
        with patch('ymir_boss_timer.time.time', return_value=1000):
            app.check_alerts()
            app.notify.assert_not_called()
        with patch('ymir_boss_timer.time.time', return_value=1001):
            app.check_alerts()
            app.notify.assert_called_once()

    def test_mute_expires_and_other_account_keeps_sound_and_popup(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.preferences = copy.deepcopy(DEFAULTS)
        app.preferences['muted_until']['one'] = 1100
        app.sound, app.show_respawn_alert, app.send_native_toast = Mock(), Mock(), Mock()
        with patch('ymir_productivity.time.time', return_value=1000):
            app.notify('Boss', 'Aviso', '...', boss={'id': 'a', 'profile_id': 'one'})
            app.sound.assert_not_called()
            app.notify('Boss', 'Aviso', '...', boss={'id': 'a', 'profile_id': 'two'})
            app.sound.assert_called_once()
        with patch('ymir_productivity.time.time', return_value=1101):
            app.notify('Boss', 'Aviso', '...', boss={'id': 'a', 'profile_id': 'one'})
            self.assertEqual(app.show_respawn_alert.call_count, 2)

    def test_volume_changes_only_generated_wave_amplitude(self):
        import array
        amplitudes = []
        for volume in (0, 25, 100):
            with wave.open(io.BytesIO(tone_wave(volume, 'Cristal'))) as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getframerate(), 22050)
                amplitudes.append(max(abs(n) for n in array.array('h', wav.readframes(wav.getnframes()))))
        self.assertEqual(amplitudes[0], 0)
        self.assertGreater(amplitudes[2], amplitudes[1]*3)
        self.assertNotEqual(tone_wave(70, 'Grave'), tone_wave(70, 'Duplo'))

    def test_quick_actions_require_explicit_target_and_do_not_change_account(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.bosses = [{'id': 'a', 'name': 'Boss', 'profile_id': 'one'}, {'id': 'a', 'name': 'Boss', 'profile_id': 'two'}]
        app.quick_target = None
        app.start, app.confirm_respawn, app.refresh_overlay = Mock(), Mock(), Mock()
        app.hotkey_status = Mock()
        app.quick_action('kill')
        app.start.assert_not_called()
        app.choose_quick_target(app.bosses[1])
        app.quick_action('kill')
        app.start.assert_called_once_with(app.bosses[1])
        app.quick_action('spawn')
        app.confirm_respawn.assert_called_once_with(app.bosses[1])
        app.bosses[1]['last_kill'] = time.time()
        app.quick_action('kill')
        self.assertEqual(app.start.call_count, 1)
        app.bosses.pop()
        app.quick_action('kill')
        self.assertEqual(app.start.call_count, 1)

    def test_backup_roundtrip_preserves_profiles_timers_and_configuration(self):
        values = sample_backup()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / 'backup.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                for name, data in values.items():
                    archive.writestr(name, json.dumps(data))
            loaded = read_backup(path)
            restore_files(folder, loaded)
            for name, value in values.items():
                self.assertEqual(json.loads((folder/name).read_text(encoding="utf-8")), value)

    def test_invalid_backups_are_rejected_before_live_write(self):
        changes = [lambda v: v['bosses.json'][0].update(minutes=0),
                   lambda v: v['bosses.json'][0].update(end=float('nan')),
                   lambda v: v['bosses.json'][0].update(respawn_samples='bad'),
                   lambda v: v['profiles.json']['profiles'][0].update(regions='bad'),
                   lambda v: v['history.json'][0].pop('respawn_at'),
                   lambda v: v['preferences.json'].update(volume=101),
                   lambda v: v['preferences.json'].update(boss_alerts=[])]
        for change in changes:
            values = sample_backup()
            change(values)
            with self.assertRaises(ValueError):
                validate_backup(values)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'evil.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('../bosses.json', '[]')
            with self.assertRaises(ValueError):
                read_backup(path)

    def test_restore_rolls_back_every_file_after_partial_write_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'bosses.json').write_text('["original"]')
            calls = 0
            def fail_second(path, value):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('disk full')
                atomic_json(path, value)
            with patch.object(productivity, 'atomic_json', side_effect=fail_second):
                with self.assertRaises(OSError):
                    restore_files(folder, sample_backup())
            self.assertEqual((folder/'bosses.json').read_text(), '["original"]')
            self.assertFalse((folder/'history.json').exists())
            self.assertFalse((folder/'profiles.json').exists())


    def test_observed_window_reports_sample_count_and_uncertainty(self):
        app = ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        boss = {'variable_respawn': True, 'minutes': 180, 'last_kill': 100000,
                'respawn_samples': [{'killed_at': 10000, 'spawned_at': 16000},
                                    {'killed_at': 20000, 'spawned_at': 27200}]}
        text = app.learning_description(boss)
        self.assertIn('110.0 min', text)
        self.assertIn('2 observações', text)
        self.assertIn('faixa observada deste ciclo', text)
        self.assertIn('poucas amostras', text)
        self.assertIn('sem garantia', text)

    @unittest.skipUnless(os.name == 'nt', 'Windows hotkey message queue')
    def test_windows_global_message_thread_routes_actions_and_releases_keys(self):
        import ctypes
        commands = queue.SimpleQueue()
        worker = productivity.GlobalHotkeys(commands)
        try:
            self.assertTrue(worker.ready.wait(3))
            self.assertTrue(worker.thread.is_alive())
            # Actual thread message, without synthesizing user input into the desktop.
            self.assertTrue(ctypes.windll.user32.PostThreadMessageW(worker.thread_id, 0x312, 2, 0))
            received = []
            until = time.monotonic() + 3
            while time.monotonic() < until:
                try:
                    received.append(commands.get(timeout=.2))
                except queue.Empty:
                    continue
                if 'hotkey:kill' in received:
                    break
            self.assertIn('hotkey:kill', received)
        finally:
            worker.close()
        self.assertFalse(worker.thread.is_alive())


@unittest.skipUnless(os.environ.get('YMIR_GUI_TESTS') == '1', 'Requires desktop display')
class ProductivityUITests(unittest.TestCase):
    def test_tools_overlay_export_and_restore_keep_independent_data(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            folder = Path(tmp)
            stack.enter_context(patch.multiple(ymir, DATA_DIR=folder, DATA_FILE=folder/'bosses.json', HISTORY_FILE=folder/'history.json', UPDATE_SETTINGS=folder/'updates.json'))
            for method in ('init_tray', 'check_updates', 'notify', 'send_native_toast'):
                stack.enter_context(patch.object(ymir.BossTimerApp, method))
            app = ymir.BossTimerApp()
            try:
                app.rename_account('Völva', 'SA012')
                app.name_entry.insert(0, 'Guardião')
                app.minutes_entry.insert(0, '180')
                app.add_boss()
                first = app.bosses[0]
                app.choose_quick_target(first)
                app.quick_action('kill')
                end = first['end']
                app.create_account('Conta 2', 'EU005', copy_catalog=True)
                second = app.profile_bosses()[0]
                app.choose_quick_target(second)
                app.quick_action('kill')
                self.assertEqual(first['end'], end)
                app.tools_dialog()
                tools = next(w for w in app.winfo_children() if isinstance(w, ymir.tk.Toplevel) and w.title() == 'Ferramentas • Ymir')
                notebook = next(w for w in tools.winfo_children() if isinstance(w, ymir.ttk.Notebook))
                for tab in notebook.tabs():
                    notebook.select(tab)
                    app.update()
                app.toggle_overlay()
                app.update()
                self.assertTrue(app.overlay.attributes('-topmost'))
                app.overlay.geometry('460x600+50+60')
                app.update()
                app.close_overlay()
                self.assertIn('460x600', app.preferences['overlay_geometry'])
                app.toggle_overlay()
                app.update()
                backup = folder/'export.zip'
                with patch.object(productivity.filedialog, 'asksaveasfilename', return_value=str(backup)), patch.object(productivity.messagebox, 'showinfo'):
                    app.export_backup_dialog()
                original = copy.deepcopy(app.bosses)
                self.assertEqual(read_backup(backup)['bosses.json'], original)
                app.bosses = []
                app.save()
                tools.destroy()
                with patch.object(productivity.filedialog, 'askopenfilename', return_value=str(backup)), patch.object(productivity.messagebox, 'askyesno', return_value=True), patch.object(productivity.messagebox, 'showinfo'), patch.object(productivity.messagebox, 'showerror') as error:
                    app.restore_backup_dialog()
                    error.assert_not_called()
                self.assertEqual(len(app.bosses), len(original))
                for actual, expected in zip(app.bosses, original):
                    self.assertEqual({k: actual[k] for k in expected}, expected)
                self.assertEqual(len(app.profile_state['profiles']), 2)
                self.assertTrue(list((folder/'backups').iterdir()))
                app.update()
                if os.environ.get('YMIR_UI_SCREENSHOT_DIR'):
                    from PIL import ImageGrab
                    out = Path(os.environ['YMIR_UI_SCREENSHOT_DIR'])
                    out.mkdir(exist_ok=True, parents=True)
                    ImageGrab.grab().save(out/'productivity-panel.png')
            finally:
                app.quit_app()
