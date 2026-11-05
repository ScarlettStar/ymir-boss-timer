"""Spark-only sync: user ID tokens, CAS writes, three-way entity merge.
No admin credentials, functions, storage buckets or paid scheduling services.
"""
import copy
import json
import re
import urllib.request
import urllib.error
import urllib.parse

# Firebase public client configuration, supplied by the project owner.
DEFAULT_CONFIG = {'project': 'ymir-boss-timer-b4dfe',
                  'api_key': 'AIzaSyAlSZrr7nMctIzLR9qx2o6UxnCZnYY_xwQ'}
LIMIT = 850_000
LOCAL_BOSS = ('warned_for', 'finished_for')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def entities(state):
    result = {}
    for p in state['profiles']['profiles']:
        result['p:' + p['id']] = {k: v for k, v in p.items() if k != 'channel_view'}
    for b in state['bosses']:
        result['b:' + canonical([b.get('profile_id', 'default'), b['id']])] = {
            k: v for k, v in b.items() if k not in LOCAL_BOSS}
    for h in state['history']:
        key = [h.get('profile_id', 'default'), h.get('boss_id', h['name']), int(h['killed_at'] * 1000)]
        result['h:' + canonical(key)] = copy.deepcopy(h)
    return result


def merge(base, local, remote, prefer_local=False):
    """Changes to different entities compose; conflicting offline edits keep remote.
    Missing entities represent deletions only when present in baseline.
    """
    out, conflicts = copy.deepcopy(remote), []
    missing = object()
    for key in sorted(set(base) | set(local)):
        old, new, other = base.get(key, missing), local.get(key, missing), remote.get(key, missing)
        if old == new:
            continue
        if other != old and other != new:
            conflicts.append({'key': key, 'local': None if new is missing else new})
            if not prefer_local:
                continue
        if new is missing:
            out.pop(key, None)
        else:
            out[key] = copy.deepcopy(new)
    # Profile removals cannot leave dangling timers/history.
    profiles = {k[2:] for k in out if k.startswith('p:')}
    out = {k: v for k, v in out.items() if k.startswith('p:') or v.get('profile_id', 'default') in profiles}
    return out, conflicts


def validate_pairing(base, local, remote):
    # Independent installs reuse "default"; never attach an existing catalog to
    # the other device's different server just because that ID matches.
    for key, profile in local.items():
        if not key.startswith('p:') or key in base or key not in remote:
            continue
        if profile.get('server', '').strip().casefold() != remote[key].get('server', '').strip().casefold():
            if any(k.startswith('b:') and b.get('profile_id', 'default') == profile['id'] for k, b in local.items()):
                raise ValueError('As contas locais e da nuvem usam o mesmo ID em servidores diferentes. Exporte um backup e importe o backup do PC no Android antes de conectar, ou use outro login para manter os conjuntos separados.')


def apply_entities(state, records):
    if not isinstance(records, dict) or len(records) > 10000:
        raise ValueError('Estrutura de nuvem inválida.')
    for key, value in records.items():
        if not isinstance(value, dict):
            raise ValueError('Registro de nuvem inválido.')
        if key.startswith('p:'):
            expected = 'p:' + value['id']
        elif key.startswith('b:'):
            expected = 'b:' + canonical([value.get('profile_id', 'default'), value['id']])
        elif key.startswith('h:'):
            expected = 'h:' + canonical([value.get('profile_id', 'default'), value.get('boss_id', value['name']), int(value['killed_at'] * 1000)])
        else:
            raise ValueError('Registro de nuvem desconhecido.')
        if expected != key:
            raise ValueError('Identidade de nuvem inconsistente.')
    result = copy.deepcopy(state)
    result['profiles']['profiles'] = [copy.deepcopy(records[k]) for k in sorted(records) if k.startswith('p:')]
    ids = {p['id'] for p in result['profiles']['profiles']}
    if not ids:
        raise ValueError('A nuvem não contém uma conta válida.')
    old_profiles = {p['id']: p for p in state['profiles']['profiles']}
    for p in result['profiles']['profiles']:
        if 'channel_view' in old_profiles.get(p['id'], {}):
            p['channel_view'] = old_profiles[p['id']]['channel_view']
    if result['profiles']['active'] not in ids:
        result['profiles']['active'] = result['profiles']['profiles'][0]['id']
    old_bosses = {(b.get('profile_id', 'default'), b['id']): b for b in state['bosses']}
    result['bosses'] = []
    for k in sorted(records):
        if not k.startswith('b:'):
            continue
        b = copy.deepcopy(records[k])
        old = old_bosses.get((b.get('profile_id', 'default'), b['id']), {})
        for field in LOCAL_BOSS:
            b[field] = old.get(field, 0) if old.get('end') == b.get('end') else 0
        result['bosses'].append(b)
    result['history'] = sorted((copy.deepcopy(v) for k, v in records.items() if k.startswith('h:')),
                               key=lambda h: h['killed_at'])[-1000:]
    from ymir_productivity import validate_backup
    validate_backup({k + '.json': v for k, v in result.items() if k in ('profiles', 'bosses', 'history', 'preferences')})
    return result


class CloudError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__({'401': 'Sessão expirada. Entre novamente.', '403': 'Acesso negado. Confira as regras do Firebase.',
                          '429': 'Limite temporário atingido. A sincronização tentará depois.',
                          'OFFLINE': 'Sem conexão. Marcações permanecem neste aparelho.',
                          'AUTH': 'Não foi possível entrar. Confira e-mail, senha e configuração.',
                          'CONFLICT': 'Outro aparelho alterou os dados. Tentaremos novamente.'}.get(str(code),
                          'Não foi possível sincronizar. Seus dados locais foram mantidos.'))


def request(url, method='GET', data=None, token=None, form=False):
    body = None if data is None else (urllib.parse.urlencode(data).encode() if form else canonical(data).encode())
    headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with urllib.request.urlopen(urllib.request.Request(url, body, headers, method=method), timeout=20) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Resposta da nuvem muito grande.')
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise CloudError(str(exc.code)) from None
    except (OSError, TimeoutError):
        raise CloudError('OFFLINE') from None


def config(project, api_key):
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,62}', project) or not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', api_key):
        raise ValueError('Informe o ID do projeto e a chave Web API do Firebase.')
    return {'project': project, 'api_key': api_key}


def login(settings, email, password, create=False):
    config(settings['project'], settings['api_key'])
    action = 'signUp' if create else 'signInWithPassword'
    try:
        data = request('https://identitytoolkit.googleapis.com/v1/accounts:' + action + '?key=' + settings['api_key'],
                       'POST', {'email': email.strip(), 'password': password, 'returnSecureToken': True})
    except CloudError:
        raise CloudError('AUTH') from None
    return dict(settings, uid=data['localId'], refresh=data['refreshToken'], email=email.strip())


def exchange(session, base, local):
    """Return acknowledged entities; caller durably applies them before baseline advance."""
    config(session['project'], session['api_key'])
    auth = request('https://securetoken.googleapis.com/v1/token?key=' + session['api_key'], 'POST',
                   {'grant_type': 'refresh_token', 'refresh_token': session['refresh']}, form=True)
    if auth['user_id'] != session['uid']:
        raise ValueError('Identidade da sessão alterada.')
    token = auth['id_token']
    url = ('https://firestore.googleapis.com/v1/projects/' + session['project'] +
           '/databases/(default)/documents/users/' + urllib.parse.quote(session['uid'], safe='') + '/sync/state')
    for _ in range(4):
        try:
            document = request(url, token=token)
            if document['fields']['schema']['integerValue'] != '1':
                raise ValueError('Versão da nuvem incompatível.')
            payload = document['fields']['payload']['stringValue']
            if len(payload.encode()) > LIMIT:
                raise ValueError('Dados excedem o limite gratuito por sincronização.')
            remote = json.loads(payload)
            precondition = {'currentDocument.updateTime': document['updateTime']}
        except CloudError as exc:
            if exc.code != '404':
                raise
            remote, precondition = {}, {'currentDocument.exists': 'false'}
        validate_pairing(base, local, remote)
        merged, conflicts = merge(base, local, remote)
        # Validate untrusted records before publishing or applying.
        if merged:
            apply_entities({'bosses': [], 'history': [], 'profiles': {'active': 'default', 'profiles': []}, 'preferences': {}}, merged)
        if merged == remote:
            return merged, conflicts
        payload = canonical(merged)
        if len(payload.encode()) > LIMIT:
            raise ValueError('Dados excedem 850 KB. Exporte um backup e reduza o histórico.')
        try:
            request(url + '?' + urllib.parse.urlencode(precondition), 'PATCH',
                    {'fields': {'schema': {'integerValue': '1'}, 'payload': {'stringValue': payload}}}, token)
            return merged, conflicts
        except CloudError as exc:
            if exc.code not in ('409', '412', '400'):  # Firestore FAILED_PRECONDITION can be HTTP 400.
                raise
    raise CloudError('CONFLICT')
