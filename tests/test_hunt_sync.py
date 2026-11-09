import copy,unittest
from unittest.mock import Mock
from ymir_hunt_sync import HuntClient,SyncError,canonical,apply_death,ensure_catalog,event_id,fresh,validate_live
from ymir_cloud import apply_entities


def records():
    return {'p:default':dict(id='default',name='Scarlett',server='SA012',regions=[]),
      'b:["default","boss"]':dict(id='boss',profile_id='default',name='Boss',category='Mapa',minutes=10,
        channel='',floor='',kind='Boss',variable_respawn=False,respawn_samples=[],last_kill=0,end=0,spawn_for=0,warned_for=0,finished_for=0)}


def event():
    e=dict(profile_id='default',boss_id='boss',auto_key='mapa|Boss|1',when=2000.0,created_at=2010.0,source='estimada',lower=600,upper=600,fixed=True)
    e['id']=event_id('default','boss',e['auto_key'],e['when'],e['created_at']);return e


class HuntSyncModelTests(unittest.TestCase):
    def test_death_updates_exact_timer_and_has_estimated_source(self):
        source=records();updated,status=apply_death(source,event(),3000)
        self.assertEqual(status,'applied');b=updated['b:["default","boss"]']
        self.assertEqual(b['end'],2600);self.assertEqual(b['kill_source'],'auto_estimated')
        self.assertEqual(source['b:["default","boss"]']['last_kill'],0)
        self.assertEqual(sum(k.startswith('h:') for k in updated),1)
        apply_entities({'profiles':{'active':'default','profiles':[]},'bosses':[],'history':[],'preferences':{}},updated)
    def test_replay_is_idempotent(self):
        updated,_=apply_death(records(),event(),3000);twice,status=apply_death(updated,event(),3000)
        self.assertEqual(status,'duplicate');self.assertEqual(twice,updated)
    def test_other_profile_or_removed_timer_never_retargets_by_name(self):
        e=event();e['profile_id']='other';updated,status=apply_death(records(),e,3000)
        self.assertEqual(status,'missing');self.assertEqual(updated,records())
    def test_manual_correction_and_newer_kill_win(self):
        for changes in (dict(manual_updated_at=2015,last_kill=1500,end=2100),dict(last_kill=2050,end=2650)):
            data=records();data['b:["default","boss"]'].update(changes)
            self.assertEqual(apply_death(data,event(),3000),(data,'superseded'))
    def test_legacy_manual_same_cycle_is_preserved(self):
        data=records();data['b:["default","boss"]'].update(last_kill=1900,end=2500)
        self.assertEqual(apply_death(data,event(),3000),(data,'manual_priority'))
    def test_invalid_or_future_events_rejected(self):
        for field,value in [('when',4000),('when',float('nan')),('lower',0),('upper',604801)]:
            e=event();e[field]=value
            with self.assertRaises(ValueError):apply_death(records(),e,3000)
    def test_catalog_import_is_stable_per_channel_without_starting_timers(self):
        definitions=[dict(auto_key=f'arvore|Novo boss|{c}',name='Novo boss',channel=c,map='And. 2',map_id='arvore',seconds=600) for c in (1,2)]
        updated,mapping=ensure_catalog(records(),'default',definitions);again,second=ensure_catalog(updated,'default',definitions)
        self.assertEqual(again,updated);self.assertEqual(second,mapping);self.assertEqual(len(set(mapping.values())),2)
        for bid in mapping.values():self.assertEqual(updated['b:'+canonical(['default',bid])]['end'],0)
    def test_existing_myrk_channel_links_without_duplicate(self):
        data=records();data['b:["default","boss"]'].update(category='Bosses Myrkheimr',channel='CHN 1')
        updated,mapping=ensure_catalog(data,'default',[dict(auto_key='myrk|Boss|1',name='Boss',channel=1,map='Myrkheimr',map_id='myrk',seconds=3600)])
        self.assertEqual(len(updated),len(data));self.assertEqual(mapping['myrk|Boss|1'],'boss')
    def test_stale_status_is_explicit(self):
        self.assertTrue(fresh(100,150));self.assertFalse(fresh(100,191));self.assertFalse(fresh(500,100))
    def test_live_requires_explicit_state_and_bounded_text(self):
        value=dict(schema=1,device_id='a'*32,profile_id='default',running=True,paused=False,simulate=False,boss='Boss',map='Map',stage='Combate',next_visit='Outro',device_label='PC')
        self.assertEqual(validate_live(value),value);value['stage']='x'*501
        with self.assertRaises(ValueError):validate_live(value)


class HuntRestTests(unittest.TestCase):
    def client(self,transport):
        client=HuntClient(dict(project='ymir-test',api_key='a'*25,uid='owner',refresh='private'),transport)
        client._token='id-token';client._expires=float('inf');return client
    def doc(self,data,version='first'):
        return dict(updateTime=version,fields={'schema':{'integerValue':'1'},'payload':{'stringValue':canonical(data)}})
    def test_cas_conflict_reloads_preserving_new_manual_edit(self):
        edited=records();edited['b:["default","boss"]'].update(manual_updated_at=2020,last_kill=1800,end=2400)
        read=[self.doc(records()),self.doc(edited,'second')];calls=[]
        def transport(url,method='GET',data=None,token=None,form=False):
            calls.append((url,method))
            if method=='GET':return read.pop(0)
            raise SyncError(412)
        result,acks=self.client(transport).send_deaths([event()])
        self.assertEqual(result,edited);self.assertEqual(acks[event()['id']],'superseded')
        self.assertEqual(sum(method=='PATCH' for _,method in calls),1)
    def test_presence_uses_owner_and_server_time(self):
        transport=Mock(return_value={});client=self.client(transport)
        live=dict(schema=1,device_id='a'*32,profile_id='default',running=False,paused=False,simulate=False,boss='',map='',stage='',next_visit='',device_label='PC')
        client.publish(live);args=transport.call_args.args
        self.assertTrue(args[0].endswith('/documents:commit'));write=args[2]['writes'][0]
        self.assertIn('/users/owner/automation/',write['update']['name'])
        self.assertEqual(write['updateTransforms'][0]['setToServerValue'],'REQUEST_TIME')
    def test_refreshed_identity_cannot_change_account(self):
        client=HuntClient(dict(project='ymir-test',api_key='a'*25,uid='owner',refresh='private'),Mock(return_value={'user_id':'other','id_token':'x'}))
        with self.assertRaises(ValueError):client.token()
    def test_empty_queue_does_not_write_state(self):
        transport=Mock(return_value=self.doc(records()));_,acks=self.client(transport).send_deaths([])
        self.assertEqual(acks,{});self.assertEqual(transport.call_count,1)


@unittest.skipUnless(__import__('os').environ.get('YMIR_GUI_TESTS')=='1','Requires a desktop display')
class HuntWindowTests(unittest.TestCase):
    def test_panel_filters_account_and_marks_old_activity(self):
        import tkinter as tk
        import time
        from ymir_hunt_ui import open_hunt
        app=tk.Tk();app.withdraw();app.cloud_session={'project':'ymir-test','api_key':'a'*25,'uid':'owner','refresh':'fixture'}
        app.active_profile_id=lambda:'default'
        value=dict(schema=1,device_id='a'*32,profile_id='default',device_label='PC teste',running=True,paused=False,simulate=False,boss='Chefe atual',map='Mapa teste',channel=2,stage='Em combate',next_visit='Próximo chefe',received_at=time.time()-120)
        hidden=dict(value,profile_id='other',boss='Boss de outra conta')
        from unittest.mock import patch
        try:
            with patch('ymir_hunt_ui.HuntClient') as client:
                client.return_value.live.return_value=[value,hidden]
                open_hunt(app)
                until=time.monotonic()+3
                while time.monotonic()<until:
                    app.update();time.sleep(.02)
                labels=[];todo=[app.hunt_window]
                while todo:
                    widget=todo.pop();todo.extend(widget.winfo_children())
                    if isinstance(widget,tk.Label):labels.append(widget.cget('text'))
                text='\n'.join(labels)
                self.assertIn('Chefe atual',text);self.assertIn('SEM ATUALIZAÇÃO RECENTE',text)
                self.assertNotIn('Boss de outra conta',text)
        finally:app.destroy()
