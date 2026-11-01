"""Simuleaza un meci (trimite payload-uri GSI false) ca sa testezi fara Dota.
Folosire: python simulate.py npc_dota_hero_juggernaut"""
import json, sys, time, urllib.request

HERO = sys.argv[1] if len(sys.argv) > 1 else "npc_dota_hero_juggernaut"
URL = "http://127.0.0.1:3000/gsi"
timeline = [(-90, "item_tango"), (-90, "item_quelling_blade"), (120, "item_wraith_band"),
            (300, "item_phase_boots"), (840, "item_bfury"), (1320, "item_manta")]

for clock in range(-90, 1800, 30):
    inventory = [it for t, it in timeline if t <= clock]
    level = max(1, min(25, 1 + (clock + 90) // 75))
    payload = {
        "map": {"clock_time": clock, "game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"},
        "player": {"gold": 200 + (clock % 600) * 4, "kills": clock // 300, "deaths": clock // 600, "assists": clock // 200},
        "hero": {"name": HERO, "level": level},
        "items": {f"slot{i}": {"name": n} for i, n in enumerate(inventory[:9])},
        # abilitatile reale vin de la Dota; in simulare lasam app-ul sa arate doar build-ul
    }
    urllib.request.urlopen(urllib.request.Request(URL, json.dumps(payload).encode(),
                           {"Content-Type": "application/json"}))
    print(f"timp {clock:>5}s  lvl {level:>2}  items: {', '.join(i[5:] for i in inventory)}")
    time.sleep(1)
