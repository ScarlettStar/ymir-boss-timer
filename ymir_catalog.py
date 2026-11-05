"""Repair the legacy Fólkvangr catalog without mixing accounts or guessing timers."""
import copy
import unicodedata
from collections import defaultdict
from ymir_models import item_profile, channel_region, clean_samples

FOLK = 'Bosses Fólkvangr'
MYRK = 'Bosses Myrkheimr'
FLOORS = ('P1', 'P2', 'P3', 'P4 UNIVERSAL')
ROLES = ('Guerreiro', 'Lanceiro', 'Maga', 'Escald')
MARKER = 'folk_catalog_repair_v1'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower())
                   if not unicodedata.combining(c)).strip()


def is_folk(category):
    return normalized(category) in ('folk', 'folkvangr', 'bosses folkvangr')


def role_of(boss):
    return next((role for role in ROLES if normalized(boss.get('name', '')) == normalized(role)), None)


def ordered_folk_bosses(bosses):
    """Guerreiro → Lanceiro → Maga → Escald, independent of UUIDs and favorites."""
    def key(boss):
        name = normalized(boss.get('name', ''))
        rank = next((i for i, role in enumerate(ROLES) if normalized(role) == name), len(ROLES))
        return rank, name
    return sorted(bosses, key=key)


def repair_folk_catalog(bosses, history):
    """Use explicit historical floors; retain latest cycle (including intentional reset).

    Only repair profiles with all four known role names already in Fólkvangr.
    Foreign role copies are removed only when completely unused and a full
    four-floor catalog exists. Every removed/changed record is returned for
    archival. Other names, regions and accounts remain unchanged.
    """
    source = copy.deepcopy(bosses)
    report = {'removed': [], 'changed': [], 'created': [], 'unresolved': []}
    historical = {}
    used_ids = set()
    for row in history:
        key = (item_profile(row), row.get('boss_id'))
        used_ids.add(key)
        if is_folk(row.get('category', '')) and row.get('floor') in FLOORS:
            previous = historical.get(key)
            if previous is None or row.get('killed_at', 0) >= previous.get('killed_at', 0):
                historical[key] = row
    profiles = sorted({item_profile(b) for b in source})
    for pid in profiles:
        roles = {role_of(b) for b in source if item_profile(b) == pid and is_folk(b.get('category'))}
        if not set(ROLES) <= roles:
            continue
        # Restore the floor saved with the latest observed death for this ID.
        for b in source:
            key = (pid, b['id'])
            if item_profile(b) != pid or not role_of(b):
                continue
            row = historical.get(key)
            if row is not None:
                old = copy.deepcopy(b)
                b.update(category=FOLK, floor=row['floor'], channel='')
                if b != old:
                    report['changed'].append({'before': old, 'after': copy.deepcopy(b), 'reason': 'Piso confirmado no histórico'})
        groups = defaultdict(list)
        for b in source:
            if item_profile(b) == pid and is_folk(b.get('category')) and role_of(b):
                groups[(b.get('floor') or 'P1', role_of(b))].append(b)
        # Unknown floors are not silently assigned or deleted.
        for (floor, _role), entries in groups.items():
            if floor not in FLOORS:
                report['unresolved'].extend(copy.deepcopy(entries))
        for floor in FLOORS:
            for role in ROLES:
                entries = groups.get((floor, role), [])
                if not entries:
                    # No invented death/respawn: clone only the catalog definition.
                    template = next(b for b in source if item_profile(b) == pid
                                    and is_folk(b.get('category')) and role_of(b) == role)
                    import uuid
                    new = copy.deepcopy(template)
                    new.update(id=uuid.uuid4().hex, name=role, category=FOLK, floor=floor, channel='',
                               end=0, last_kill=0, warned_for=0, finished_for=0, spawn_for=0, respawn_samples=[])
                    source.append(new)
                    report['created'].append(copy.deepcopy(new))
                    continue
                # Latest kill wins; a reset end=0 on that same cycle stays reset.
                winner = max(entries, key=lambda b: (b.get('last_kill', 0),
                             (pid, b['id']) in used_ids, len(b.get('respawn_samples', [])),
                             bool(b.get('favorite')), b['id']))
                old_winner = copy.deepcopy(winner)
                samples = {}
                for b in entries:
                    for sample in clean_samples(b.get('respawn_samples', [])):
                        samples[(sample['killed_at'], sample['spawned_at'])] = sample
                winner['respawn_samples'] = clean_samples(sorted(samples.values(), key=lambda s: (s['killed_at'], s['spawned_at']), reverse=True))
                if any(b.get('favorite') for b in entries):
                    winner['favorite'] = True
                winner.update(name=role, category=FOLK, floor=floor, channel='')
                if winner != old_winner:
                    report['changed'].append({'before': old_winner, 'after': copy.deepcopy(winner), 'reason': 'Cadastro consolidado'})
                for b in entries:
                    if b is not winner:
                        report['removed'].append({'boss': copy.deepcopy(b), 'reason': 'Cópia duplicada no mesmo piso',
                                                  'kept_id': winner['id']})
                        source.remove(b)
        # Delete only unused copies of the four Fólkvangr roles outside Fólkvangr.
        # Historical or active foreign records without proof stay for review.
        for b in list(source):
            if item_profile(b) != pid or not role_of(b) or is_folk(b.get('category')):
                continue
            unused = not b.get('last_kill') and not b.get('end') and not b.get('respawn_samples') and (pid, b['id']) not in used_ids
            if unused:
                report['removed'].append({'boss': copy.deepcopy(b), 'reason': 'Cópia não utilizada fora de Fólkvangr'})
                source.remove(b)
            else:
                report['unresolved'].append(copy.deepcopy(b))
        # A known Myrk boss accidentally moved to Folk can be placed in a
        # missing channel only when this same account already has its Myrk twin.
        names = sorted({b['name'] for b in source if item_profile(b) == pid and is_folk(b.get('category')) and not role_of(b)})
        for name in names:
            misplaced = [b for b in source if item_profile(b) == pid and is_folk(b.get('category')) and b['name'] == name]
            twins = [b for b in source if item_profile(b) == pid and channel_region(b.get('category')) == MYRK and normalized(b['name']) == normalized(name)]
            if not twins:
                report['unresolved'].extend(copy.deepcopy(misplaced))
                continue
            # Do not discard meaningful records whose channel cannot be inferred.
            occupied = {b.get('channel') for b in twins}
            for b in sorted(misplaced, key=lambda b: b['id']):
                unused = not b.get('last_kill') and not b.get('end') and not b.get('respawn_samples') and (pid, b['id']) not in used_ids
                missing = next((c for c in ('CHN 1', 'CHN 2') if c not in occupied), None)
                if unused and missing:
                    old = copy.deepcopy(b)
                    b.update(category=MYRK, floor='', channel=missing, variable_respawn=True, myrk_variable_v1=True)
                    occupied.add(missing)
                    report['changed'].append({'before': old, 'after': copy.deepcopy(b), 'reason': 'Canal ausente do mesmo boss em Myrkheimr'})
                elif unused:
                    report['removed'].append({'boss': copy.deepcopy(b), 'reason': 'Cópia não utilizada de Myrkheimr em Fólkvangr'})
                    source.remove(b)
                else:
                    report['unresolved'].append(copy.deepcopy(b))
    return source, report


class CatalogMixin:
    def repair_catalog_once(self):
        from ymir_boss_timer import DATA_DIR, DATA_FILE, backup_data
        from ymir_models import atomic_json
        from ymir_productivity import validate_backup
        from tkinter import messagebox
        try:
            if not self.preferences.get(MARKER):
                candidate, report = repair_folk_catalog(self.bosses, self.history)
            else:
                candidate, report = copy.deepcopy(self.bosses), {'removed': [], 'changed': [], 'created': [], 'unresolved': []}
            candidate, duplicates = dedupe_channel_bosses(candidate)
            report['removed'].extend(duplicates)
            validate_backup({'bosses.json': candidate, 'history.json': self.history,
                             'profiles.json': self.profile_state})
            if candidate != self.bosses:
                backup_data()
                # Write recovery before altering any live record; never overwrite it.
                recovery = DATA_DIR / 'folkvangr-before-repair-v1.json'
                if not recovery.exists():
                    atomic_json(recovery, {'bosses': self.bosses, 'history': self.history, 'report': report})
                # A later sync can contain new duplicates: archive every discarded version.
                if duplicates:
                    import time
                    atomic_json(DATA_DIR / 'backups' / ('channel-duplicates-' + str(time.time_ns()) + '.json'), duplicates)
                atomic_json(DATA_FILE, candidate)
                self.bosses = candidate
            self.preferences[MARKER] = True
            self.save_preferences()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror('Organização de Fólkvangr pendente',
                                 'Não foi possível concluir a organização. Os dados anteriores foram preservados em backup.\n' + str(exc), parent=self)


def channel_identity(boss):
    region = channel_region(boss.get('category'))
    channel = boss.get('channel')
    if not region or channel not in ('CHN 1', 'CHN 2'):
        return None
    return (item_profile(boss), region, normalized(boss.get('name', '')),
            normalized(boss.get('kind', 'Boss')), channel)


def dedupe_channel_bosses(bosses):
    """One boss per account/region/kind/channel, even when IDs came from two devices."""
    result = copy.deepcopy(bosses)
    groups = defaultdict(list)
    for boss in result:
        identity = channel_identity(boss)
        if identity:
            groups[identity].append(boss)
    removed = []
    for entries in groups.values():
        if len(entries) < 2:
            continue
        winner = max(entries, key=lambda b: (b.get('last_kill', 0),
                     len(clean_samples(b.get('respawn_samples', []))), bool(b.get('favorite')), b['id']))
        samples = {}
        for b in entries:
            for sample in clean_samples(b.get('respawn_samples', [])):
                samples[(sample['killed_at'], sample['spawned_at'])] = sample
        winner['respawn_samples'] = clean_samples(sorted(samples.values(), key=lambda s: (s['killed_at'], s['spawned_at']), reverse=True))
        if any(b.get('favorite') for b in entries):
            winner['favorite'] = True
        for marker in ('myrk_variable_v1', 'tomb_channel_copy_v1'):
            if any(b.get(marker) for b in entries):
                winner[marker] = True
        for b in entries:
            if b is not winner:
                removed.append({'boss': copy.deepcopy(b), 'kept_id': winner['id'],
                                'reason': 'Mesmo boss na mesma conta, região e canal'})
                result.remove(b)
    return result, removed
