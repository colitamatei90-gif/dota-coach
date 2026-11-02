"""
Surse de date: OpenDota (fara cont) si STRATZ (token gratuit, filtre pe pozitie + MMR).
Totul are cache pe disc; daca o sursa pica, se foloseste cache-ul vechi sau fallback-ul.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

from paths import CACHE_DIR

OPENDOTA = "https://api.opendota.com/api"
STRATZ = "https://api.stratz.com/graphql"
CDN = "https://cdn.cloudflare.steamstatic.com"

HOUR = 3600
_warned = set()


def _warn_once(key, msg):
    if key not in _warned:
        _warned.add(key)
        print(msg)


def http_json(url, data=None, headers=None, timeout=25):
    h = {"User-Agent": "dota-coach"}
    h.update(headers or {})
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def cached(key, ttl, fetch):
    """Returneaza datele din cache daca sunt proaspete, altfel apeleaza fetch()."""
    fname = os.path.join(CACHE_DIR, re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".json")
    if os.path.exists(fname) and time.time() - os.path.getmtime(fname) < ttl:
        with open(fname, encoding="utf-8") as f:
            return json.load(f)
    try:
        data = fetch()
        if data is not None:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
    except Exception as e:
        _warn_once(key, f"[date] {key}: {e}")
    if os.path.exists(fname):
        with open(fname, encoding="utf-8") as f:
            return json.load(f)
    return None


# ------------------------------------------------------------------ constante

class Constants:
    heroes_by_npc = {}    # npc_dota_hero_axe -> {id, localized_name, img}
    items_by_name = {}    # black_king_bar -> {id, dname, cost, img, components}
    items_by_id = {}      # 116 -> black_king_bar
    abilities = {}        # antimage_mana_break -> {dname, img}
    ability_ids = {}      # "5003" -> antimage_mana_break
    hero_abilities = {}   # npc_dota_hero_x -> {abilities: [...], talents: [{name, level}]}

    @classmethod
    def load(cls):
        get = lambda p: cached("od" + p, 24 * HOUR, lambda: http_json(OPENDOTA + p))
        heroes = get("/heroes") or []
        cls.heroes_by_npc = {h["name"]: h for h in heroes}
        cls.items_by_name = get("/constants/items") or {}
        cls.items_by_id = {v["id"]: k for k, v in cls.items_by_name.items() if "id" in v}
        cls.abilities = get("/constants/abilities") or {}
        cls.ability_ids = get("/constants/ability_ids") or {}
        cls.hero_abilities = get("/constants/hero_abilities") or {}
        # OpenDota /heroes nu are imagini; le construim din numele npc
        for npc, h in cls.heroes_by_npc.items():
            h.setdefault("img", f"/apps/dota2/images/dota_react/heroes/{npc.replace('npc_dota_hero_', '')}.png")
        print(f"[date] {len(cls.heroes_by_npc)} eroi, {len(cls.items_by_name)} item-e, "
              f"{len(cls.abilities)} abilitati")


def item_info(name):
    it = Constants.items_by_name.get(name, {})
    return {"name": name, "dname": it.get("dname", name.replace("_", " ").title()),
            "cost": it.get("cost") or 0, "img": CDN + it["img"] if it.get("img") else None}


def ability_info(name):
    ab = Constants.abilities.get(name, {})
    dname = ab.get("dname") or name
    dname = re.sub(r"\{s:[^}]+\}", "X", dname)  # talentele au placeholder-e de valori
    return {"name": name, "dname": dname,
            "img": CDN + ab["img"] if ab.get("img") else None,
            "talent": name.startswith("special_bonus")}


# ------------------------------------------------------------------ item builds

PHASE_KEYS = ["start_game_items", "early_game_items", "mid_game_items", "late_game_items"]


def opendota_items(hero_id):
    """{phase_key: {item_name: count}} din OpenDota (meciuri recente, toate pozitiile)."""
    pop = cached(f"od_pop_{hero_id}", 6 * HOUR,
                 lambda: http_json(f"{OPENDOTA}/heroes/{hero_id}/itemPopularity")) or {}
    out = {}
    for key in PHASE_KEYS:
        out[key] = {}
        for iid, cnt in (pop.get(key) or {}).items():
            name = Constants.items_by_id.get(int(iid))
            if name:
                out[key][name] = {"count": cnt}
    return out


STATUS = {"stratz": "neconfigurat"}   # afisat in UI: ce s-a intamplat cu STRATZ


def stratz_items(hero_id, token, position, bracket):
    """
    Item-e pe faze filtrate pe pozitie si MMR, din STRATZ (meciurile din ultima saptamana).
    itemFullPurchase intoarce randuri {itemId, instance, time, matchCount, winCount}:
    cate meciuri au cumparat item-ul (a 'instance'-a oara) in minutul 'time' si cate au castigat.
    Returneaza None daca nu merge (token gresit, schema schimbata) -> se foloseste OpenDota.
    """
    if not token:
        STATUS["stratz"] = "neconfigurat"
        return None
    args = [f"heroId: {int(hero_id)}"]
    if position:
        args.append(f"positionIds: [{position}]")
    if bracket:
        args.append(f"bracketBasicIds: [{bracket}]")
    query = "{ heroStats { itemFullPurchase(%s) { itemId instance time matchCount winCount } } }" % ", ".join(args)

    def fetch():
        res = http_json(STRATZ, {"query": query},
                        {"Authorization": f"Bearer {token}", "User-Agent": "STRATZ_API"})
        if res.get("errors"):
            raise RuntimeError(res["errors"][0].get("message", str(res["errors"]))[:200])
        return res

    try:
        res = cached(f"stratz2_items_{hero_id}_{position}_{bracket}", 6 * HOUR, fetch)
    except Exception as e:
        res = None
    rows = ((((res or {}).get("data") or {}).get("heroStats") or {}).get("itemFullPurchase")) or []
    if not isinstance(rows, list) or not rows:
        STATUS["stratz"] = "eroare (vezi dota-coach.log)" if res is None else "fără date pentru acest erou/filtru"
        return None

    # agregam pe item (doar prima cumparare): meciuri, victorii, minutul mediu
    agg = {}
    for r in rows:
        if not isinstance(r, dict) or (r.get("instance") or 0) != 0:
            continue
        mc = r.get("matchCount") or 0
        name = Constants.items_by_id.get(r.get("itemId"))
        if not name or mc <= 0:
            continue
        a = agg.setdefault(name, {"m": 0, "w": 0, "t": 0.0})
        a["m"] += mc
        a["w"] += r.get("winCount") or 0
        a["t"] += (r.get("time") or 0) * mc
    if not agg:
        STATUS["stratz"] = "fără date pentru acest erou/filtru"
        return None

    out = {k: {} for k in PHASE_KEYS}
    for name, a in agg.items():
        minute = a["t"] / a["m"]
        key = PHASE_KEYS[0 if minute < 1 else 1 if minute < 10 else 2 if minute < 25 else 3]
        out[key][name] = {"count": a["m"], "winrate": a["w"] / a["m"], "minute": round(minute)}
    STATUS["stratz"] = "ok"
    return out


# ------------------------------------------------------------------ skill build + talente

def skill_build(hero_id, hero_npc):
    """
    Skill build-ul cel mai jucat din meciurile pro din ultimele 60 de zile (OpenDota explorer).
    Returneaza {"order": [ability_name x nivel], "talents": [{level, options:[{name, pct, winrate}]}]}
    """
    sql = f"""
        SELECT pm.ability_upgrades_arr AS ups, ((pm.player_slot < 128) = m.radiant_win) AS win
        FROM player_matches pm JOIN matches m ON m.match_id = pm.match_id
        WHERE pm.hero_id = {int(hero_id)} AND pm.ability_upgrades_arr IS NOT NULL
          AND m.start_time > extract(epoch from now() - interval '60 days')
        ORDER BY m.match_id DESC LIMIT 400"""
    url = f"{OPENDOTA}/explorer?sql=" + urllib.parse.quote(" ".join(sql.split()))
    res = cached(f"od_skills_{hero_id}", 12 * HOUR, lambda: http_json(url, timeout=40))
    rows = (res or {}).get("rows") or []
    seqs, wins = [], []
    for r in rows:
        names = [Constants.ability_ids.get(str(a)) for a in (r.get("ups") or [])]
        names = [n for n in names if n]
        if len(names) >= 6:
            seqs.append(names)
            wins.append(bool(r.get("win")))
    if not seqs:
        return None
    return {"order": _consensus_order(seqs), "talents": _talents(hero_npc, seqs, wins),
            "matches": len(seqs)}


def _consensus_order(seqs, levels=18, min_group=5):
    """Coboara pe 'arborele' de build-uri: la fiecare nivel alege cea mai jucata abilitate
    printre meciurile care au avut acelasi build pana atunci -> build coerent, real."""
    max_lvl = defaultdict(int)
    for s in seqs:
        for ab, n in Counter(s).items():
            max_lvl[ab] = max(max_lvl[ab], n)
    order, group = [], seqs
    for i in range(levels):
        counts_so_far = Counter(order)
        pool = group if len(group) >= min_group else seqs
        votes = Counter(s[i] for s in pool if len(s) > i
                        and counts_so_far[s[i]] < max_lvl[s[i]]
                        and not (s[i].startswith("special_bonus") and s[i] in counts_so_far))
        if not votes:
            break
        pick = votes.most_common(1)[0][0]
        order.append(pick)
        group = [s for s in group if s[:i + 1] == order]
    return order


def _talents(hero_npc, seqs, wins):
    talents = (Constants.hero_abilities.get(hero_npc) or {}).get("talents") or []
    by_tier = defaultdict(list)
    for t in talents:
        by_tier[t.get("level")].append(t["name"])
    out = []
    for tier in sorted(k for k in by_tier if k):
        opts = []
        picked = [(set(s) & set(by_tier[tier]), w) for s, w in zip(seqs, wins)]
        total = sum(1 for p, _ in picked if p) or 1
        for name in by_tier[tier]:
            got = [w for p, w in picked if name in p]
            opts.append(dict(ability_info(name), pct=round(100 * len(got) / total),
                             winrate=round(100 * sum(got) / len(got)) if got else None))
        out.append({"level": {1: 10, 2: 15, 3: 20, 4: 25}.get(tier, tier), "options": opts})
    return out
