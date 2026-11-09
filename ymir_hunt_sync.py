"""Boss Auto bridge protocol. Authenticated clients only; no administrator keys."""
import copy
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

SCHEMA = 1
STALE_SECONDS = 90
LIVE_LIMIT = 60000
STATE_LIMIT = 850000


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def event_id(profile, boss_id, auto_key, when, created_at):
    return hashlib.sha256(canonical([profile,boss_id,auto_key,when,created_at]).encode()).hexdigest()


def apply_death(records, event, now=None):
    """CAS caller owns atomicity. Acknowledging a rejected event never invents a death."""
    now=time.time() if now is None else now
    for key in ('when','created_at','lower','upper'):
        if not number(event.get(key)):
            raise ValueError('Evento de morte inválido.')
    when=event['when'];created=event['created_at']
    if not 0<when<=created+60 or created>now+60 or not 60<=event['lower']<=event['upper']<=604800:
        raise ValueError('Horários do evento inválidos.')
    pid,bid=event['profile_id'],event['boss_id']
    profile=records.get('p:'+pid)
    key='b:'+canonical([pid,bid]);old=records.get(key)
    if not profile or not old or old.get('profile_id','default')!=pid:
        return records,'missing'
    if event['id']==old.get('hunt_event_id'):
        return records,'duplicate'
    last=float(old.get('last_kill',0));manual=float(old.get('manual_updated_at',0))
    if manual>=created or last>when:
        return records,'superseded'
    # Older Timer clients do not have an edit timestamp. Protect the same cycle.
    if event.get('source')!='manual' and last and old.get('kill_source')!='auto_estimated' and not manual:
        if when<last+max(60,float(old.get('minutes',1))*60):
            return records,'manual_priority'
    hkey='h:'+canonical([pid,bid,int(when*1000)])
    if hkey in records:
        return records,'duplicate'
    result=copy.deepcopy(records);boss=result[key]
    end=when+(event['lower']+event['upper'])/2
    source='manual' if event.get('source')=='manual' else 'auto_estimated'
    boss.update(last_kill=when,end=end,spawn_for=0,warned_for=0,finished_for=0,
                kill_source=source,hunt_event_id=event['id'],hunt_lower=event['lower'],hunt_upper=event['upper'])
    if source=='manual':boss['manual_updated_at']=created
    if event.get('fixed'):
        boss.update(minutes=max(1,round(event['lower']/60)),variable_respawn=False)
    history={k:boss.get(k,'') for k in ('name','category','channel','floor','kind','hunt_channel','hunt_map_id')}
    history.update(profile_id=pid,boss_id=bid,killed_at=when,respawn_at=end,
                   variable_respawn=bool(boss.get('variable_respawn')),kill_source=source,hunt_event_id=event['id'])
    result[hkey]=history
    histories=sorted((k for k in result if k.startswith('h:')),key=lambda k:result[k]['killed_at'])
    for k in histories[:-1000]:result.pop(k,None)
    return result,'applied'


def validate_live(value):
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA or len(canonical(value).encode())>LIVE_LIMIT:
        raise ValueError('Estado de caça inválido.')
    if not isinstance(value.get('profile_id'),str) or not value['profile_id'] or not isinstance(value.get('device_id'),str):
        raise ValueError('Identidade da caça inválida.')
    for key in ('running','paused','simulate'):
        if type(value.get(key)) is not bool:raise ValueError('Estado inválido.')
    for key in ('boss','map','stage','next_visit','device_label'):
        if not isinstance(value.get(key,''),str) or len(value.get(key,''))>500:raise ValueError('Texto inválido.')
    return value


def fresh(received_at, now=None):
    now=time.time() if now is None else now
    return number(received_at) and -60<=now-received_at<=STALE_SECONDS


class SyncError(Exception):
    def __init__(self,code):
        self.code=str(code)
        super().__init__({'401':'Entre novamente na nuvem.','403':'Acesso negado: publique as regras de integração do Timer.',
            '404':'Dados ainda não encontrados na nuvem.','429':'Limite temporário; nova tentativa depois.',
            'OFFLINE':'Sem conexão; dados locais preservados.','CONFLICT':'Outro aparelho alterou os horários; nova tentativa pendente.'}.get(self.code,'Não foi possível sincronizar.'))


def request(url,method='GET',data=None,token=None,form=False):
    body=None if data is None else (urllib.parse.urlencode(data).encode() if form else canonical(data).encode())
    headers={'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json'}
    if token:headers['Authorization']='Bearer '+token
    try:
        with urllib.request.urlopen(urllib.request.Request(url,body,headers,method=method),timeout=8) as response:
            raw=response.read(2000001)
            if len(raw)>2000000:raise ValueError('Resposta muito grande.')
            return json.loads(raw)
    except urllib.error.HTTPError as exc:raise SyncError(exc.code) from None
    except (OSError,TimeoutError):raise SyncError('OFFLINE') from None


class HuntClient:
    def __init__(self,session,transport=request):
        self.session=dict(session);self.request=transport;self._token=None;self._expires=0
        if not re.fullmatch(r'[a-z][a-z0-9-]{4,62}',session.get('project','')):raise ValueError('Projeto inválido.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}',session.get('api_key','')):raise ValueError('Configuração inválida.')
        self.root='https://firestore.googleapis.com/v1/projects/'+session['project']+'/databases/(default)/documents'
        self.user=self.root+'/users/'+urllib.parse.quote(session['uid'],safe='')
    @staticmethod
    def login(settings,email,password,transport=request):
        data=transport('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key='+settings['api_key'],
            'POST',{'email':email.strip(),'password':password,'returnSecureToken':True})
        return dict(settings,uid=data['localId'],refresh=data['refreshToken'],email=email.strip())
    def token(self):
        if not self._token or time.monotonic()>=self._expires:
            auth=self.request('https://securetoken.googleapis.com/v1/token?key='+self.session['api_key'],'POST',
                {'grant_type':'refresh_token','refresh_token':self.session['refresh']},form=True)
            if auth['user_id']!=self.session['uid']:raise ValueError('Sessão de outra conta.')
            self._token=auth['id_token'];self._expires=time.monotonic()+3000
        return self._token
    def read_records(self):
        doc=self.request(self.user+'/sync/state',token=self.token());fields=doc['fields']
        payload=fields['payload']['stringValue']
        if fields['schema']['integerValue']!='1' or len(payload.encode())>STATE_LIMIT:raise ValueError('Nuvem incompatível.')
        records=json.loads(payload)
        if not isinstance(records,dict):raise ValueError('Nuvem inválida.')
        return records,doc['updateTime']
    def send_deaths(self,events):
        for _ in range(4):
            records,version=self.read_records();updated=records;acks={}
            for event in events:
                updated,result=apply_death(updated,event)
                if result!='missing':acks[event['id']]=result
            if updated==records:return records,acks
            payload=canonical(updated)
            if len(payload.encode())>STATE_LIMIT:raise ValueError('Nuvem excede 850 KB.')
            try:
                self.request(self.user+'/sync/state?'+urllib.parse.urlencode({'currentDocument.updateTime':version}),'PATCH',
                    {'fields':{'schema':{'integerValue':'1'},'payload':{'stringValue':payload}}},self.token())
                return updated,acks
            except SyncError as exc:
                if exc.code not in ('400','409','412'):raise
        raise SyncError('CONFLICT')
    def publish(self,live):
        validate_live(live)
        if not re.fullmatch(r'[a-f0-9]{32}',live['device_id']):raise ValueError('Aparelho inválido.')
        name=self.user.removeprefix('https://firestore.googleapis.com/v1/')+'/automation/'+live['device_id']
        url=self.root.removesuffix('/documents')+'/documents:commit'
        fields={'schema':{'integerValue':'1'},'payload':{'stringValue':canonical(live)}}
        self.request(url,'POST',{'writes':[{'update':{'name':name,'fields':fields},
            'updateTransforms':[{'fieldPath':'receivedAt','setToServerValue':'REQUEST_TIME'}]}]},self.token())
    def live(self):
        doc=self.request(self.user+'/automation?'+urllib.parse.urlencode({'pageSize':20,'orderBy':'receivedAt desc'}),token=self.token())
        result=[]
        for record in doc.get('documents',[]):
            try:
                fields=record['fields'];value=validate_live(json.loads(fields['payload']['stringValue']))
                stamp=fields['receivedAt']['timestampValue']
                value=dict(value,received_at=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp())
                result.append(value)
            except (KeyError,ValueError,TypeError):continue
        return result


def ensure_catalog(records, profile_id, definitions):
    """Explicit import only. Stable IDs keep repeat imports idempotent."""
    import uuid
    import unicodedata
    def norm(value):
        text="".join(c for c in unicodedata.normalize("NFKD",str(value).casefold()) if not unicodedata.combining(c)).strip()
        return text.removeprefix("bosses ")
    result=copy.deepcopy(records);profile=result.get('p:'+profile_id)
    if not profile:raise ValueError('Conta do Timer não encontrada.')
    mapping={}
    for definition in definitions:
        key=definition['auto_key'];channel=definition['channel'];name=definition['name'];region=definition['map'][:60]
        if not isinstance(name,str) or not 0<len(name)<=60 or type(channel) is not int or not 1<=channel<=3:
            raise ValueError('Boss/canal inválido para importar.')
        candidates=[b for k,b in result.items() if k.startswith('b:') and b.get('profile_id','default')==profile_id
                    and (b.get('hunt_auto_key')==key)]
        if not candidates and region in ('Myrkheimr','Túmulo do Rei'):
            candidates=[b for k,b in result.items() if k.startswith('b:') and b.get('profile_id','default')==profile_id
                and norm(b.get('category',''))==norm(region) and norm(b.get('name',''))==norm(name) and b.get('channel')=='CHN '+str(channel)]
            if len(candidates)>1:raise ValueError('Há timers duplicados deste boss/canal; vincule manualmente.')
        if candidates:
            mapping[key]=candidates[0]['id'];continue
        bid='hunt_'+uuid.uuid5(uuid.NAMESPACE_URL,canonical([profile_id,key])).hex
        known_channel='CHN '+str(channel) if region in ('Myrkheimr','Túmulo do Rei') and channel<=2 else ''
        boss=dict(id=bid,name=name,category=region,kind='Boss',profile_id=profile_id,
            minutes=max(1,min(10080,round(definition['seconds']/60))),channel=known_channel,floor='',favorite=False,
            variable_respawn=False,respawn_samples=[],end=0,last_kill=0,spawn_for=0,warned_for=0,finished_for=0,
            hunt_auto_key=key,hunt_map_id=definition['map_id'],hunt_channel=channel)
        result['b:'+canonical([profile_id,bid])]=boss;mapping[key]=bid
        if region not in profile.setdefault('regions',[]):profile['regions'].append(region)
    return result,mapping


def _import_catalog(self,profile_id,definitions):
    for _ in range(4):
        records,version=self.read_records();updated,mapping=ensure_catalog(records,profile_id,definitions)
        if updated==records:return records,mapping
        payload=canonical(updated)
        if len(payload.encode())>STATE_LIMIT:raise ValueError('Nuvem excede 850 KB.')
        try:
            self.request(self.user+'/sync/state?'+urllib.parse.urlencode({'currentDocument.updateTime':version}),'PATCH',
                {'fields':{'schema':{'integerValue':'1'},'payload':{'stringValue':payload}}},self.token())
            return updated,mapping
        except SyncError as exc:
            if exc.code not in ('400','409','412'):raise
    raise SyncError('CONFLICT')

HuntClient.import_catalog=_import_catalog
