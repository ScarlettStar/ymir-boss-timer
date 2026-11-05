import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from ymir_catalog import repair_folk_catalog, dedupe_channel_bosses, CatalogMixin, FOLK, FLOORS, ROLES
from ymir_models import default_profiles, channel_copy_id
from ymir_cloud import entities, merge, apply_entities
from test_cloud_sync import state


def boss(bid, name='Guerreiro', floor='P1', category=FOLK, pid='default', **options):
    return dict(id=bid, name=name, floor=floor, category=category, profile_id=pid,
                channel=options.pop('channel',''), minutes=120, kind='Boss',
                last_kill=options.pop('last_kill',0), end=options.pop('end',0),
                respawn_samples=options.pop('respawn_samples',[]), **options)


def catalog(pid='default'):
    return [boss(pid+role+floor,name=role,floor=floor,pid=pid) for floor in FLOORS for role in ROLES]


class CatalogRepairTests(unittest.TestCase):
    def test_restore_floor_from_history_and_keep_latest_timer_per_slot(self):
        rows=catalog();old=copy.deepcopy(rows)
        source=next(b for b in rows if b['name']=='Guerreiro' and b['floor']=='P2')
        source.update(floor='P1',last_kill=1000,end=8200)
        rows.extend([boss('extra-p1',last_kill=900,end=8100),boss('wrong-tomb',category='Túmulo do Rei',channel='CHN 2')])
        history=[dict(boss_id=source['id'],profile_id='default',category=FOLK,floor='P2',killed_at=1000)]
        original=copy.deepcopy(rows);saved_history=copy.deepcopy(history)
        repaired,report=repair_folk_catalog(rows,history)
        self.assertEqual(len(repaired),16)
        self.assertEqual(rows,original);self.assertEqual(history,saved_history)
        restored=next(b for b in repaired if b['id']==source['id'])
        self.assertEqual((restored['floor'],restored['end']),('P2',8200))
        self.assertFalse(any(b['id']=='wrong-tomb' for b in repaired))
        self.assertEqual(repair_folk_catalog(repaired,history)[0],repaired)

    def test_preserve_reset_and_do_not_recreate_countdown_from_history(self):
        rows=catalog();source=next(b for b in rows if b['name']=='Escald' and b['floor']=='P2');source.update(floor='P1',last_kill=1000,end=0)
        history=[dict(boss_id=source['id'],category=FOLK,floor='P2',killed_at=1000,respawn_at=8200)]
        repaired,_=repair_folk_catalog(rows,history)
        fixed=next(b for b in repaired if b['id']==source['id'])
        self.assertEqual((fixed['floor'],fixed['last_kill'],fixed['end']),('P2',1000,0))

    def test_accounts_independent_unknown_or_active_foreign_boss_not_deleted(self):
        rows=catalog('one')+catalog('two')+[boss('uncertain',category='Túmulo do Rei',pid='one',last_kill=100,end=7300),boss('custom',name='Personalizado',pid='one')]
        repaired,report=repair_folk_catalog(rows,[])
        self.assertEqual(len(repaired),34)
        self.assertEqual([b['id'] for b in report['unresolved']],['uncertain','custom'])

    def test_rehome_unused_myrk_clone_only_with_evidence_in_same_account(self):
        rows=catalog()+[boss('myrk',name='Capitão',category='Bosses Myrkheimr',floor='',channel='CHN 1')]
        rows.extend(boss('accidental'+f,name='Capitão',floor=f) for f in FLOORS)
        repaired,report=repair_folk_catalog(rows,[])
        self.assertEqual(len(repaired),18)
        channels=[b for b in repaired if b['name']=='Capitão']
        self.assertEqual({b['channel'] for b in channels},{'CHN 1','CHN 2'})
        self.assertTrue(all(b['category']=='Bosses Myrkheimr' for b in channels))
        self.assertEqual(len(report['removed']),3)

    def test_abort_before_data_change_if_recovery_write_fails(self):
        class Host(CatalogMixin):pass
        app=Host();app.preferences={};app.profile_state=default_profiles();app.bosses=catalog()+[boss('duplicate')];app.history=[];app.save_preferences=Mock()
        before=copy.deepcopy(app.bosses)
        with tempfile.TemporaryDirectory() as folder,patch('ymir_boss_timer.DATA_DIR',Path(folder)),patch('ymir_boss_timer.DATA_FILE',Path(folder)/'bosses.json'),patch('ymir_boss_timer.backup_data'),patch('ymir_models.atomic_json',side_effect=OSError('disk full')),patch('tkinter.messagebox.showerror'):
            app.repair_catalog_once()
        self.assertEqual(app.bosses,before);self.assertFalse(app.preferences.get('folk_catalog_repair_v1'))
        app.save_preferences.assert_not_called()


class ChannelDeduplicationTests(unittest.TestCase):
    def test_same_channel_collapses_but_other_channel_region_and_account_survive(self):
        rows=[boss('old',category='Túmulo do Rei',floor='',channel='CHN 1',last_kill=100,end=7300),boss('new',category='Bosses Tumulo do Rei',floor='',channel='CHN 1',last_kill=200,end=7400),boss('ch2',category='Túmulo do Rei',floor='',channel='CHN 2'),boss('other-account',category='Túmulo do Rei',floor='',channel='CHN 1',pid='two'),boss('myrk',category='Bosses Myrkheimr',floor='',channel='CHN 1')]
        original=copy.deepcopy(rows);repaired,removed=dedupe_channel_bosses(rows)
        self.assertEqual(rows,original);self.assertEqual(len(repaired),4)
        self.assertEqual(removed[0]['boss']['id'],'old')
        self.assertEqual(next(b for b in repaired if b['id']=='new')['end'],7400)
        self.assertEqual(dedupe_channel_bosses(repaired),(repaired,[]))

    def test_newer_reset_wins_and_samples_favorites_are_preserved(self):
        rows=[boss('a',category='Bosses Myrkheimr',floor='',channel='CHN 1',last_kill=100,end=7300,respawn_samples=[{'killed_at':10,'spawned_at':60}],favorite=True),boss('b',category='Bosses Myrkheimr',floor='',channel='CHN 1',last_kill=200,end=0,respawn_samples=[{'killed_at':80,'spawned_at':140}])]
        repaired,_=dedupe_channel_bosses(rows)
        self.assertEqual((repaired[0]['id'],repaired[0]['end']),('b',0))
        self.assertTrue(repaired[0]['favorite']);self.assertEqual(len(repaired[0]['respawn_samples']),2)

    def test_two_devices_generate_identical_missing_channel_id(self):
        a=boss('source-a',category='Túmulo do Rei',channel='CHN 1')
        b=dict(a,id='source-b',category='Bosses Tumulo do Rei')
        self.assertEqual(channel_copy_id(a,'CHN 2'),channel_copy_id(b,'CHN 2'))
        self.assertNotEqual(channel_copy_id(a,'CHN 2'),channel_copy_id(dict(a,profile_id='two'),'CHN 2'))

    def test_cloud_repeated_sync_does_not_union_same_boss_different_ids(self):
        before=state();local=copy.deepcopy(before);remote=copy.deepcopy(before)
        remote['bosses'][0].update(id='other-id',last_kill=3000,end=6600)
        records,conflicts=merge({},entities(local),entities(remote))
        self.assertEqual(len(apply_entities(before,records)['bosses']),1)
        self.assertEqual(len(conflicts),1)
        self.assertEqual(merge(records,records,records),(records,[]))

class RepeatedRegistrationTests(unittest.TestCase):
    def app(self, rows):
        import ymir_boss_timer as ymir
        app=ymir.BossTimerApp.__new__(ymir.BossTimerApp)
        app.profile_state=default_profiles();app.bosses=rows
        app.name_entry=Mock();app.name_entry.get.return_value='Sentinela'
        app.minutes_entry=Mock();app.minutes_entry.get.return_value='120'
        app.category_var=Mock();app.category_var.get.return_value='Bosses Myrkheimr'
        app.save=Mock();app.render=Mock()
        return app

    def test_repeat_registration_does_not_create_more_channel_rows(self):
        import ymir_boss_timer as ymir
        app=self.app([])
        with patch('tkinter.messagebox.showinfo'):
            app.add_boss();first=copy.deepcopy(app.bosses);app.add_boss()
        self.assertEqual(len(first),2);self.assertEqual(app.bosses,first)

    def test_only_missing_channel_is_added_without_altering_existing_timer(self):
        source=boss('existing',name='Sentinela',category='Bosses Myrkheimr',floor='',channel='CHN 2',last_kill=100,end=7300)
        app=self.app([source]);before=copy.deepcopy(source);app.add_boss()
        self.assertEqual(source,before);self.assertEqual(len(app.bosses),2)
        self.assertEqual({b['channel'] for b in app.bosses},{'CHN 1','CHN 2'})


@unittest.skipUnless(__import__('os').environ.get('YMIR_GUI_TESTS')=='1','Requires desktop display')
class CatalogRepairUITests(unittest.TestCase):
    def test_startup_repairs_once_preserves_history_and_locks_card_area(self):
        import ymir_boss_timer as ymir
        from tkinter import ttk
        rows=catalog();rows.append(boss('duplicate'))
        rows.append(boss('foreign',category='Túmulo do Rei',floor='',channel='CHN 2'))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'bosses.json').write_text(json.dumps(rows),encoding='utf-8');(root/'profiles.json').write_text(json.dumps(default_profiles()),encoding='utf-8');(root/'history.json').write_text('[]',encoding='utf-8')
            with patch.multiple(ymir,DATA_DIR=root,DATA_FILE=root/'bosses.json',HISTORY_FILE=root/'history.json',UPDATE_SETTINGS=root/'updates.json'),patch.object(ymir.BossTimerApp,'init_tray'),patch.object(ymir.BossTimerApp,'check_updates'):
                app=ymir.BossTimerApp()
                try:
                    app.update_idletasks();self.assertEqual(len(app.bosses),16)
                    self.assertTrue((root/'folkvangr-before-repair-v1.json').exists())
                    pending=[app.cards]
                    while pending:
                        widget=pending.pop();self.assertNotIsInstance(widget,ttk.Combobox);pending.extend(widget.winfo_children())
                    self.assertIsInstance(app.category_select,ttk.Combobox)
                    first=copy.deepcopy(app.bosses)
                finally:app.destroy()
                again=ymir.BossTimerApp()
                try:self.assertEqual(again.bosses,first)
                finally:again.destroy()
