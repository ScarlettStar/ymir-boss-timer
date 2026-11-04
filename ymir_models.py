"""Account isolation and empirical respawn estimates, independent of Tk."""
import copy
import json
import math
import uuid
import unicodedata
from collections import defaultdict

DEFAULT_PROFILE = "default"
TOMB_REGION = "Túmulo do Rei"
DEFAULT_REGIONS = ("Bosses Universais", "Bosses Myrkheimr", "Bosses Fólkvangr", TOMB_REGION)
MAX_SAMPLE_SECONDS = 10080 * 60



def channel_region(category):
    key = "".join(c for c in unicodedata.normalize("NFKD", str(category or "").casefold())
                  if not unicodedata.combining(c)).strip()
    if key.startswith("bosses "):
        key = key[7:].strip()
    if key == "myrkheimr":
        return "Bosses Myrkheimr"
    if key == "tumulo do rei":
        return TOMB_REGION
    return None


def uses_channels(category):
    return channel_region(category) is not None


def region_label(category):
    value = str(category)
    return value[7:] if value.casefold().startswith("bosses ") else value


def item_profile(item):
    value = item.get("profile_id")
    return value if isinstance(value, str) and value.strip() else DEFAULT_PROFILE


def default_profiles():
    return {"version": 1, "active": DEFAULT_PROFILE,
            "profiles": [{"id": DEFAULT_PROFILE, "name": "Conta principal", "server": "", "regions": []}]}


def read_profiles(path):
    if not path.exists():
        return default_profiles()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list) or not data["profiles"]:
        raise ValueError("O arquivo de contas está inválido. Restaure profiles.json a partir de um backup.")
    ids = set()
    for profile in data["profiles"]:
        if (not isinstance(profile, dict) or not isinstance(profile.get("id"), str)
                or not profile["id"] or profile["id"] in ids
                or not isinstance(profile.get("name"), str) or not profile["name"].strip()
                or not isinstance(profile.get("server", ""), str)
                or not isinstance(profile.get("regions", []), list)
                or any(not isinstance(r, str) or not r.strip() for r in profile.get("regions", []))):
            raise ValueError("O arquivo profiles.json está inválido; os dados não foram alterados.")
        ids.add(profile["id"])
    if data.get("active") not in ids:
        data["active"] = data["profiles"][0]["id"]
    return data


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def reconcile_profiles(state, items):
    """Never merge an orphan account's data into another account."""
    candidate = copy.deepcopy(state)
    known = {p["id"] for p in candidate["profiles"]}
    for item in items:
        pid = item_profile(item)
        if pid not in known:
            candidate["profiles"].append({"id": pid, "name": "Conta recuperada", "server": pid[:12], "regions": []})
            known.add(pid)
    return candidate


def add_profile(state, name, server, source=None):
    name, server = name.strip(), server.strip()
    if not name or not server or len(name) > 60 or len(server) > 60:
        raise ValueError("Informe nome da conta e servidor, com até 60 caracteres cada.")
    if any((p["name"].casefold(), p.get("server", "").casefold()) == (name.casefold(), server.casefold())
           for p in state["profiles"]):
        raise ValueError("Já existe uma conta com esse nome nesse servidor.")
    candidate = copy.deepcopy(state)
    pid = uuid.uuid4().hex
    profile = {"id": pid, "name": name, "server": server, "regions": list(source.get("regions", [])) if source else []}
    candidate["profiles"].append(profile)
    candidate["active"] = pid
    return candidate, pid


def copy_boss_definitions(bosses, destination):
    return [{**b, "id": uuid.uuid4().hex, "profile_id": destination, "end": 0, "last_kill": 0,
             "warned_for": 0, "finished_for": 0, "spawn_for": 0, "respawn_samples": []} for b in bosses]


def trim_history(history, limit):
    groups = defaultdict(list)
    for item in sorted(history, key=lambda r: float(r["killed_at"])):
        groups[item_profile(item)].append(item)
    return sorted([item for group in groups.values() for item in group[-limit:]], key=lambda r: float(r["killed_at"]))


def clean_samples(samples):
    if not isinstance(samples, list):
        return []
    clean, seen = [], set()
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        try:
            killed, spawned = float(sample["killed_at"]), float(sample["spawned_at"])
            duration = spawned - killed
            if (not math.isfinite(killed) or not math.isfinite(spawned) or killed <= 0
                    or not 0 < duration <= MAX_SAMPLE_SECONDS or killed in seen):
                continue
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        seen.add(killed)
        clean.append({"killed_at": killed, "spawned_at": spawned})
    return sorted(clean, key=lambda r: r["killed_at"])[-20:]


def respawn_statistics(boss):
    samples = clean_samples(boss.get("respawn_samples", []))
    durations = [r["spawned_at"] - r["killed_at"] for r in samples]
    if not durations:
        return None
    return {"count": len(durations), "mean": sum(durations) / len(durations),
            "minimum": min(durations), "maximum": max(durations)}


def respawn_seconds(boss):
    stats = respawn_statistics(boss) if boss.get("variable_respawn") else None
    return stats["mean"] if stats else boss["minutes"] * 60


def observe_respawn(boss, spawned_at, now):
    """Return an updated copy only after validating a real kill→spawn pair."""
    if not boss.get("variable_respawn"):
        raise ValueError("Ative Respawn variável neste boss para registrar observações.")
    killed = boss.get("last_kill", 0)
    if not killed or not boss.get("end"):
        raise ValueError("Registre a morte deste boss antes de confirmar o reaparecimento.")
    if (isinstance(spawned_at, bool) or not isinstance(spawned_at, (int, float))
            or not math.isfinite(spawned_at) or not killed < spawned_at <= now
            or spawned_at - killed > MAX_SAMPLE_SECONDS):
        raise ValueError("O reaparecimento deve ser posterior à morte e anterior ou igual a agora (até 7 dias).")
    samples = clean_samples(boss.get("respawn_samples", []))
    if boss.get("spawn_for") == killed or any(s["killed_at"] == killed for s in samples):
        raise ValueError("Este reaparecimento já foi registrado. Registre uma nova morte para iniciar outro ciclo.")
    samples.append({"killed_at": killed, "spawned_at": spawned_at})
    return {**boss, "respawn_samples": clean_samples(samples), "spawn_for": killed,
            "end": spawned_at, "warned_for": spawned_at, "finished_for": spawned_at}
