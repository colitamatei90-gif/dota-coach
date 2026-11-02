"""
Dota Coach - companion app pentru Dota 2.

Primeste date live de la Dota prin Game State Integration (GSI, oficial Valve),
ia build-uri actuale (OpenDota / STRATZ) si recomanda item-e, skill-uri si talente
adaptate la meci si la inamici. Optional: sfaturi AI (Claude).

Rulare:  python server.py   (sau DotaCoach.exe)   apoi http://localhost:3000
"""
import json
import os
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ai
import coach
import providers as P
import setup_gsi
from paths import BUNDLE_DIR, load_config, save_config

CFG = load_config()
_lock = threading.Lock()

state = {
    "gsi": None,            # ultimul payload de la Dota
    "gsi_time": 0,
    "enemies": [],          # npc names alese in UI
    "hero_override": None,  # pt cand nu esti in meci (draft / test)
}

PHASE_LABELS = ["Start", "Early (0-10 min)", "Mid (10-25 min)", "Late (25+ min)"]
POSITIONS = {"": "Poziție: auto", "POSITION_1": "Pos 1 · Carry", "POSITION_2": "Pos 2 · Mid",
             "POSITION_3": "Pos 3 · Offlane", "POSITION_4": "Pos 4 · Soft support",
             "POSITION_5": "Pos 5 · Hard support"}
BRACKETS = {"": "MMR: toate", "HERALD_GUARDIAN": "Herald-Guardian", "CRUSADER_ARCHON": "Crusader-Archon",
            "LEGEND_ANCIENT": "Legend-Ancient", "DIVINE_IMMORTAL": "Divine-Immortal"}

_last_load = [0.0]


def ensure_constants():
    """Daca datele de baza n-au venit la pornire (fara internet), reincearca la cel mult 60s."""
    if not P.Constants.heroes_by_npc and time.time() - _last_load[0] > 60:
        _last_load[0] = time.time()
        P.Constants.load()


def owned_items(gsi):
    """Item-ele detinute + toate componentele lor (ca sa nu recomandam boots daca ai treads)."""
    names = set()
    for it in ((gsi or {}).get("items") or {}).values():
        n = (it or {}).get("name", "empty")
        if n and n != "empty":
            names.add(n.replace("item_", "", 1))
    expanded, stack = set(), list(names)
    while stack:
        n = stack.pop()
        if n not in expanded:
            expanded.add(n)
            stack.extend(P.Constants.items_by_name.get(n, {}).get("components") or [])
    return names, expanded


def current_phase(clock):
    if clock is None or clock < 0:
        return 0
    return 1 if clock < 600 else 2 if clock < 1500 else 3


def build_skills(hero, gsi, live):
    sb = P.skill_build(hero["id"], hero["name"])
    if not sb:
        return None
    order = sb["order"]
    hero_lvl = ((gsi.get("hero") or {}).get("level") or 0) if live else 0
    spent = None
    if live and gsi.get("abilities"):
        in_build = set(order)
        spent = sum((a or {}).get("level") or 0 for a in gsi["abilities"].values()
                    if (a or {}).get("name") in in_build)
        spent += sum(1 for k, v in (gsi.get("hero") or {}).items() if k.startswith("talent_") and v)
    nxt = None
    if spent is not None and spent < len(order):
        nxt = {"ability": P.ability_info(order[spent]), "now": spent < hero_lvl}
    return {"order": [P.ability_info(a) for a in order], "talents": sb["talents"],
            "matches": sb["matches"], "spent": spent, "next": nxt}


def recommend():
    ensure_constants()
    with _lock:
        gsi = dict(state["gsi"] or {})
        live = bool(gsi) and time.time() - state["gsi_time"] < 60
        enemies = list(state["enemies"])
        override = state["hero_override"]
    hero_npc = ((gsi.get("hero") or {}).get("name") if live else None) or override

    ai_ok, ai_why = ai.available(CFG)
    out = {"live": live, "ever_live": state["gsi_time"] > 0, "hero": None, "enemies": enemies,
           "config": {"position": CFG.get("position", ""), "bracket": CFG.get("bracket", ""),
                      "has_stratz": bool(CFG.get("stratz_token")), "ai": ai_ok, "ai_why": ai_why,
                      "ai_provider": ai.provider(CFG), "ai_name": ai.PROVIDER_NAMES[ai.provider(CFG)],
                      "has_gemini": bool(CFG.get("gemini_api_key")), "has_anthropic": bool(CFG.get("anthropic_api_key"))},
           "positions": POSITIONS, "brackets": BRACKETS}
    hero = P.Constants.heroes_by_npc.get(hero_npc)
    if not hero:
        return out

    out["hero"] = {"npc": hero_npc, "name": hero["localized_name"], "img": P.CDN + hero["img"]}
    player = (gsi.get("player") or {}) if live else {}
    clock = (gsi.get("map") or {}).get("clock_time") if live else None
    gold = player.get("gold") if live else None
    phase = current_phase(clock)
    direct, owned = owned_items(gsi if live else None)
    out.update({"clock": clock, "gold": gold, "phase": phase,
                "kda": [player.get("kills"), player.get("deaths"), player.get("assists")] if live else None,
                "level": (gsi.get("hero") or {}).get("level") if live else None,
                "owned": [P.item_info(n) for n in sorted(direct)]})

    # Item-e pe faze: STRATZ (pozitie + MMR) daca e configurat, altfel OpenDota
    items = P.stratz_items(hero["id"], CFG.get("stratz_token"), CFG.get("position"), CFG.get("bracket"))
    out["source"] = "STRATZ" if items else "OpenDota · meciuri recente, toate pozițiile"
    out["stratz_status"] = P.STATUS["stratz"]
    if items is None:
        items = P.opendota_items(hero["id"])
    phases = []
    for i, key in enumerate(P.PHASE_KEYS):
        lst = []
        for name, st in sorted((items.get(key) or {}).items(), key=lambda kv: -kv[1]["count"])[:10]:
            info = P.item_info(name)
            info.update(owned=name in owned, count=st["count"])
            if st.get("winrate") is not None:
                info["winrate"] = round(100 * st["winrate"])
            if st.get("minute") is not None:
                info["minute"] = st["minute"]
            lst.append(info)
        phases.append({"label": PHASE_LABELS[i], "items": lst})
    out["phases"] = phases

    plan = coach.make_plan(hero, phases, direct, owned, gold, phase, enemies, CFG.get("position", ""))
    out["plan"] = plan
    out["skills"] = build_skills(hero, gsi, live)

    # ---- build adaptat de AI (in fundal; pana vine, ramane planul din reguli)
    sig = _plan_signature(hero_npc, enemies, direct, phase)
    ai_ready = ai.available(CFG)[0] and CFG.get("ai_build", True)
    if ai_ready and plan.get("mode") == "build":
        _maybe_replan(sig, out, hero, phases, direct, owned, gold, phase, enemies)
        res = AI_PLAN.get("result")
        if res and AI_PLAN.get("hero") == hero_npc and coach.apply_ai(plan, res["items"], gold, direct, owned, enemies):
            plan["ai"] = {"summary": res["summary"], "model": res.get("model"),
                          "age": int(time.time() - AI_PLAN["time"]), "updating": AI_PLAN["busy"],
                          "stale": AI_PLAN.get("sig") != sig}
    out["ai_build"] = {"enabled": bool(CFG.get("ai_build", True)), "ready": ai_ready,
                       "busy": AI_PLAN["busy"], "error": AI_PLAN.get("error")}
    return out


# ---------------------------------------------------------------- AI: build in timp real

AI_PLAN = {"sig": None, "result": None, "hero": None, "time": 0, "busy": False, "last_call": 0,
           "error": None, "force": False}
MIN_GAP = 20          # secunde intre doua apeluri automate (limitele gratuite sunt mici)


def _plan_signature(hero_npc, enemies, owned_direct, phase):
    """Se schimba doar la evenimente care conteaza: erou, inamici, item-e mari cumparate, faza."""
    major = sorted(n for n in owned_direct if n not in coach.CONSUMABLES and P.item_info(n)["cost"] >= coach.CHEAP_LIMIT)
    return (hero_npc, CFG.get("position", ""), tuple(sorted(enemies)), tuple(major), phase)


def _maybe_replan(sig, rec, hero, phases, direct, owned, gold, phase, enemies):
    with _lock:
        if AI_PLAN["busy"]:
            return
        force = AI_PLAN["force"]
        if not force and sig == AI_PLAN["sig"]:
            return
        if not force and AI_PLAN["error"] and sig == AI_PLAN.get("err_sig"):
            return  # aceeasi situatie a dat eroare: nu insistam pana nu se schimba ceva
        if not force and time.time() - AI_PLAN["last_call"] < MIN_GAP:
            return
        AI_PLAN.update(busy=True, force=False, last_call=time.time())

    role = coach.role_of(CFG.get("position", ""), hero.get("roles"))
    cands = coach.candidates(phases, owned, direct, role)
    context = {
        "erou": hero["localized_name"], "rol": role,
        "pozitie": POSITIONS.get(CFG.get("position", "")), "mmr": BRACKETS.get(CFG.get("bracket", "")),
        "timp_joc": f"{(rec.get('clock') or 0) // 60} min", "gold_acum": gold, "nivel": rec.get("level"),
        "kda": rec.get("kda"),
        "iteme_detinute": [P.item_info(n)["dname"] for n in sorted(direct)],
        "inamici": [{"erou": t["vs"][0], "probleme": t["why"], "acoperit_de": t["covered"]}
                    for t in rec["plan"].get("threats", [])],
        "sursa_statistici": rec.get("source"),
        "statistici_iteme": coach.stats_table(phases),
        "propunere_din_reguli": [i["dname"] for i in ([rec["plan"]["buy_now"]] if rec["plan"].get("buy_now") else [])
                                 + rec["plan"].get("after", [])],
        "lista_permisa": {n: P.item_info(n)["dname"] for n in cands},
    }

    def run():
        res = ai.plan_build(CFG, context, cands)
        with _lock:
            AI_PLAN["busy"] = False
            if res.get("error"):
                AI_PLAN.update(error=res["error"], err_sig=sig)
                print(f"[ai-build] {res['error']}")
            else:
                AI_PLAN.update(result=res, sig=sig, hero=sig[0], time=time.time(), error=None)
                print(f"[ai-build] {res.get('model')}: {', '.join(i['item'] for i in res['items'])}")

    threading.Thread(target=run, daemon=True).start()


def ai_context(rec):
    """Rezumat compact al meciului pentru AI (fara URL-uri de imagini)."""
    names = lambda lst: [x["dname"] for x in lst or []]
    sk = rec.get("skills") or {}
    plan = rec.get("plan") or {}
    rec_items = ([plan["buy_now"]] if plan.get("buy_now") else []) + plan.get("after", []) + plan.get("kit", [])
    return {
        "erou": (rec.get("hero") or {}).get("name"), "rol": plan.get("role"),
        "pozitie": POSITIONS.get(CFG.get("position", "")), "mmr": BRACKETS.get(CFG.get("bracket", "")),
        "timp_joc_sec": rec.get("clock"), "gold": rec.get("gold"), "nivel": rec.get("level"),
        "kda": rec.get("kda"), "iteme_detinute": names(rec.get("owned")),
        "inamici": [P.Constants.heroes_by_npc.get(e, {}).get("localized_name", e) for e in rec.get("enemies", [])],
        "plan_recomandat": [{"item": i["dname"], "motiv": i.get("reason")} for i in rec_items],
        "amenintari": [{"vs": t["vs"], "problema": t["why"], "acoperit_de": t["covered"],
                        "raspunsuri": names(t["answers"])} for t in plan.get("threats", [])],
        "iteme_populare_pe_faze": {p["label"]: names(p["items"][:6]) for p in rec.get("phases", [])},
        "skill_build_pro": names(sk.get("order")),
        "urmatorul_skill": (sk.get("next") or {}).get("ability", {}).get("dname"),
        "sursa_date": rec.get("source"),
    }


def advice(question):
    rec = recommend()
    tips = coach.quick_tips(rec)
    ok, why = ai.available(CFG)
    if not ok:
        return {"text": tips, "local": True, "note": why}
    res = ai.advise(CFG, ai_context(rec), question)
    if res.get("error"):
        return {"text": tips, "local": True, "note": res["error"]}
    return res


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        try:
            self._get()
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        try:
            self._post()
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def _get(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(BUNDLE_DIR, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/state":
            self._json(recommend())
        elif self.path == "/api/heroes":
            ensure_constants()
            self._json(sorted(({"npc": k, "name": v["localized_name"], "img": P.CDN + v["img"]}
                               for k, v in P.Constants.heroes_by_npc.items()), key=lambda h: h["name"]))
        else:
            self._json({"error": "not found"}, 404)

    def _post(self):
        data = self._body()
        if self.path == "/gsi":
            with _lock:
                state["gsi"], state["gsi_time"] = data, time.time()
        elif self.path == "/api/enemies":
            with _lock:
                state["enemies"] = [e for e in data.get("enemies", []) if e in P.Constants.heroes_by_npc][:5]
        elif self.path == "/api/hero":
            h = data.get("hero")
            with _lock:
                state["hero_override"] = h if h in P.Constants.heroes_by_npc else None
        elif self.path == "/api/config":
            if data.get("position", "") in POSITIONS:
                CFG["position"] = data.get("position", "")
            if data.get("bracket", "") in BRACKETS:
                CFG["bracket"] = data.get("bracket", "")
            if data.get("ai_provider") in ai.PROVIDER_NAMES:
                CFG["ai_provider"] = data["ai_provider"]
            if isinstance(data.get("ai_build"), bool):
                CFG["ai_build"] = data["ai_build"]
            with _lock:
                AI_PLAN.update(error=None, err_sig=None, sig=None)   # setari noi -> build nou
            for key in ("stratz_token", "anthropic_api_key", "gemini_api_key"):
                if data.get(key):            # gol = nu schimba
                    CFG[key] = data[key].strip()
            save_config(CFG)
        elif self.path == "/api/advice":
            return self._json(advice((data.get("question") or "")[:500]))
        elif self.path == "/api/replan":
            with _lock:
                AI_PLAN.update(force=True, error=None)
        else:
            return self._json({"error": "not found"}, 404)
        self._json({"ok": True})


def get_port():
    return int(os.environ.get("DOTA_COACH_PORT") or CFG.get("port") or 3000)


def start(port):
    """Porneste serverul intr-un thread. Returneaza (url, deja_pornit)."""
    print("=== Dota Coach ===")
    setup_gsi.install(port)
    url = f"http://localhost:{port}"
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    except OSError as e:
        print(f"[server] Portul {port} e ocupat ({e}) - probabil Dota Coach ruleaza deja")
        return url, True
    _last_load[0] = time.time()
    # datele de baza se incarca in fundal, ca fereastra sa apara imediat
    threading.Thread(target=P.Constants.load, daemon=True).start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Ruleaza pe {url}  (pe telefon: http://<IP-ul-PC-ului>:{port})")
    return url, False


def main():
    """Mod browser (pentru dezvoltare): python server.py"""
    url, _ = start(get_port())
    if CFG.get("open_browser", True) and not os.environ.get("DOTA_COACH_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
