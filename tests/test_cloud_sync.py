import copy
import json
import unittest
from unittest.mock import patch
from ymir_cloud import entities, merge, apply_entities, exchange, CloudError, validate_pairing


def state():
    return {'profiles': {'version': 1, 'active': 'default', 'profiles': [
        {'id': 'default', 'name': 'Conta principal', 'server': 'SA012', 'regions': [], 'channel_view': 'CHN 1'}]},
        'bosses': [{'id': 'boss-1', 'profile_id': 'default', 'name': 'Árvore', 'category': 'Túmulo do Rei',
                    'minutes': 60, 'channel': 'CHN 1', 'end': 2000, 'last_kill': 1000,
                    'warned_for': 2000, 'finished_for': 0, 'respawn_samples': []}],
        'history': [], 'preferences': {'lead_seconds': 180, 'volume': 30}, 'updates': {}}


class CloudSyncTests(unittest.TestCase):
    def test_roundtrip_preserves_device_settings_and_alert_delivery(self):
        source = state()
        self.assertEqual(apply_entities(source, entities(source)), source)
        shared = json.dumps(entities(source))
        self.assertNotIn('warned_for', shared)
        self.assertNotIn('channel_view', shared)
        self.assertNotIn('preferences', shared)

    def test_different_bosses_and_channels_compose(self):
        original = state()
        second = copy.deepcopy(original['bosses'][0]);second.update(id='boss-2', channel='CHN 2')
        original['bosses'].append(second)
        local, remote = copy.deepcopy(original), copy.deepcopy(original)
        local['bosses'][0]['end'] = 3000
        remote['bosses'][1]['end'] = 4000
        result, conflicts = merge(entities(original), entities(local), entities(remote))
        merged = apply_entities(original, result)
        self.assertEqual([b['end'] for b in merged['bosses']], [3000, 4000])
        self.assertEqual(conflicts, [])
        self.assertEqual(merged['bosses'][0]['warned_for'], 0)

    def test_offline_conflict_does_not_overwrite_new_cloud_timer(self):
        original = state();local=copy.deepcopy(original);remote=copy.deepcopy(original)
        local['bosses'][0]['end']=3500;remote['bosses'][0]['end']=4000
        out, conflicts=merge(entities(original),entities(local),entities(remote))
        self.assertEqual(apply_entities(original,out)['bosses'][0]['end'],4000)
        self.assertEqual(conflicts[0]['local']['end'],3500)

    def test_remote_delete_not_resurrected_by_unchanged_offline_device(self):
        base=entities(state());remote={k:v for k,v in base.items() if not k.startswith('b:')}
        self.assertEqual(merge(base,base,remote)[0],remote)

    def test_local_delete_and_remote_new_profile(self):
        source=state();base=entities(source);local=copy.deepcopy(source);local['bosses']=[]
        remote=copy.deepcopy(base);remote['p:second']={'id':'second','name':'Conta 2','server':'SA013','regions':[]}
        out,_=merge(base,entities(local),remote)
        self.assertEqual(len(apply_entities(source,out)['profiles']['profiles']),2)
        self.assertFalse(any(k.startswith('b:') for k in out))

    def test_new_edits_during_network_roundtrip_remain_pending(self):
        before=state();current=copy.deepcopy(before);current['bosses'][0]['end']=5000
        remote=copy.deepcopy(before);remote['bosses'][0]['end']=4000
        out,_=merge(entities(before),entities(current),entities(remote),prefer_local=True)
        self.assertEqual(apply_entities(current,out)['bosses'][0]['end'],5000)
        self.assertNotEqual(out,entities(remote))

    def test_profile_deletion_removes_orphans_and_active_falls_back(self):
        s=state();s['profiles']['profiles'].append({'id':'second','name':'Other','regions':[]})
        base=entities(s);remote={k:v for k,v in base.items() if k=='p:second'}
        out,_=merge(base,base,remote);applied=apply_entities(s,out)
        self.assertEqual(applied['profiles']['active'],'second');self.assertEqual(applied['bosses'],[])

    def test_empty_and_invalid_cloud_rejected(self):
        with self.assertRaises(ValueError):apply_entities(state(),{})
        bad=entities(state());next(v for k,v in bad.items() if k.startswith('b:'))['minutes']=-1
        with self.assertRaises(ValueError):apply_entities(state(),bad)

    def test_first_pairing_unions_catalogs_and_prefers_cloud_profile(self):
        local=state();remote=state();remote['profiles']['profiles'][0]['name']='Conta no PC';remote['bosses'][0]['id']='different'
        out,_=merge({},entities(local),entities(remote))
        applied=apply_entities(local,out)
        self.assertEqual(len(applied['bosses']),2)
        self.assertEqual(applied['profiles']['profiles'][0]['name'],'Conta no PC')

    def test_cas_retries_with_new_remote_state(self):
        source=state();local=entities(source);settings={'project':'ymir-test','api_key':'x'*30,'uid':'u','refresh':'s'}
        doc=lambda end,revision:{'fields':{'schema':{'integerValue':'1'},'payload':{'stringValue':json.dumps({})}},'updateTime':revision}
        calls=[]
        def transport(url,method='GET',data=None,token=None,form=False):
            calls.append((url,method))
            if 'securetoken' in url:return {'user_id':'u','id_token':'id'}
            if method=='GET':return doc(0,'r'+str(len(calls)))
            if len([c for c in calls if c[1]=='PATCH'])==1:raise CloudError('412')
            return {}
        with patch('ymir_cloud.request',side_effect=transport):
            result,_=exchange(settings,{},local)
        self.assertEqual(result,local)
        patches=[url for url,method in calls if method=='PATCH']
        self.assertEqual(len(patches),2);self.assertNotEqual(patches[0],patches[1])

    def test_unchanged_document_never_written(self):
        local=entities(state());settings={'project':'ymir-test','api_key':'x'*30,'uid':'u','refresh':'s'}
        def transport(url,method='GET',data=None,**kwargs):
            if 'securetoken' in url:return {'user_id':'u','id_token':'id'}
            self.assertEqual(method,'GET')
            return {'fields':{'schema':{'integerValue':'1'},'payload':{'stringValue':json.dumps(local)}},'updateTime':'r'}
        with patch('ymir_cloud.request',side_effect=transport):self.assertEqual(exchange(settings,local,local)[0],local)

class CloudApplyTests(unittest.TestCase):
    def test_failed_local_write_does_not_advance_acknowledged_baseline(self):
        import tempfile
        import queue
        from pathlib import Path
        from unittest.mock import Mock
        from ymir_cloud_ui import CloudMixin
        source=state();remote=copy.deepcopy(source);remote['bosses'][0]['end']=4000
        class Host(CloudMixin):
            pass
        app=Host();app.bosses=source['bosses'];app.history=source['history'];app.profile_state=source['profiles'];app.preferences=source['preferences']
        session={'project':'project','uid':'user'}
        app.cloud_session=session;app.cloud_busy=True;app.cloud_next=float('inf');app.cloud_status=Mock();app.after=Mock();app.update_busy=False;app.refresh_account_view=Mock()
        app.cloud_queue=queue.SimpleQueue();app.cloud_queue.put(('sync',(session,source,entities(remote),[])))
        with tempfile.TemporaryDirectory() as folder:
            app.cloud_base_file=Path(folder)/'cloud-base.json'
            with patch('ymir_boss_timer.backup_data'),patch('ymir_productivity.restore_files',side_effect=OSError('disk full')):
                app.cloud_poll()
            self.assertFalse(app.cloud_base_file.exists())
            self.assertEqual(app.bosses[0]['end'],2000)
            app.refresh_account_view.assert_not_called()

    def test_successful_apply_keeps_edits_made_during_request_pending(self):
        import tempfile
        import queue
        from pathlib import Path
        from unittest.mock import Mock
        from ymir_cloud_ui import CloudMixin
        source=state();remote=copy.deepcopy(source);remote['bosses'][0]['end']=4000
        class Host(CloudMixin):
            pass
        app=Host();app.bosses=copy.deepcopy(source['bosses']);app.bosses[0]['end']=5000
        app.history=source['history'];app.profile_state=source['profiles'];app.preferences=source['preferences']
        session={'project':'project','uid':'user'}
        app.cloud_session=session;app.cloud_busy=True;app.cloud_next=float('inf');app.cloud_status=Mock();app.after=Mock();app.update_busy=False;app.refresh_account_view=Mock()
        app.cloud_queue=queue.SimpleQueue();app.cloud_queue.put(('sync',(session,source,entities(remote),[])))
        with tempfile.TemporaryDirectory() as folder:
            app.cloud_base_file=Path(folder)/'cloud-base.json'
            with patch('ymir_boss_timer.backup_data'),patch('ymir_productivity.restore_files'):
                app.cloud_poll()
            baseline=json.loads(app.cloud_base_file.read_text(encoding='utf-8'))['base']
            self.assertEqual(next(v for k,v in baseline.items() if k.startswith('b:'))['end'],4000)
            self.assertEqual(app.bosses[0]['end'],5000)

    @unittest.skipUnless(__import__('os').name=='nt','DPAPI requires Windows')
    def test_windows_session_protection_roundtrip(self):
        from ymir_cloud_ui import protect
        raw=b'{"refresh":"private-session-token"}'
        encrypted=protect(raw)
        self.assertNotIn(b'private-session-token',encrypted)
        self.assertEqual(protect(encrypted,True),raw)

class CloudPairingTests(unittest.TestCase):
    def test_independent_default_accounts_cannot_mix_different_servers(self):
        local=state();remote=state();remote['profiles']['profiles'][0]['server']='SA099'
        with self.assertRaises(ValueError):validate_pairing({},entities(local),entities(remote))
        # Once paired, renaming the server is a normal tracked edit, not a fresh collision.
        validate_pairing(entities(local),entities(local),entities(remote))

    def test_empty_phone_can_receive_existing_desktop_catalog(self):
        local=state();local['bosses']=[];local['profiles']['profiles'][0]['server']=''
        validate_pairing({},entities(local),entities(state()))
