"""
Motorul de recomandare: transforma statisticile de build + starea meciului + inamicii
intr-un plan clar: "Cumpara acum X, pentru ca ...", apoi urmatoarele 3 item-e.
Functii pure (fara retea), ca sa poata fi testate usor.
"""
import providers as P

PHASE_NAMES = ["start", "early game", "mid game", "late game"]
STARTING_GOLD = 600

BOOTS = {"boots", "tranquil_boots", "phase_boots", "power_treads", "arcane_boots",
         "guardian_greaves", "travel_boots", "travel_boots_2", "boots_of_bearing"}
BOOT_UPGRADES = BOOTS - {"boots"}

# Din fiecare grup se recomanda/foloseste un singur item
EXCLUSIVE_GROUPS = [
    {"wraith_band", "bracer", "null_talisman"},
    {"hood_of_defiance", "pipe", "eternal_shroud"},
    {"vladmir", "mask_of_madness"},
]

CONSUMABLES = {
    "tango", "clarity", "flask", "enchanted_mango", "faerie_fire", "ward_observer",
    "ward_sentry", "ward_dispenser", "tpscroll", "dust", "smoke_of_deceit",
    "blood_grenade", "tome_of_knowledge", "famango", "great_famango", "greater_famango",
}
CHEAP_LIMIT = 450  # componentele ieftine (branches, circlet...) nu sunt "urmatorul item"
SUPPORT_MARKERS = {"ward_observer", "ward_sentry", "ward_dispenser", "smoke_of_deceit"}

# Datele OpenDota amesteca toate pozitiile; cu astea separam item-ele dupa rol.
SUPPORT_ITEMS = {
    "glimmer_cape", "force_staff", "ghost", "solar_crest", "holy_locket", "guardian_greaves",
    "boots_of_bearing", "mekansm", "pavise", "tranquil_boots", "arcane_boots", "urn_of_shadows",
    "spirit_vessel", "rod_of_atos", "cyclone", "aether_lens", "medallion_of_courage", "headdress",
    "wind_lace", "infused_raindrop", "lotus_orb", "pipe", "wraith_pact", "ancient_janggo",
}
CARRY_ITEMS = {
    "bfury", "butterfly", "skadi", "greater_crit", "satanic", "rapier", "abyssal_blade",
    "monkey_king_bar", "radiance", "manta", "heart", "bloodthorn", "mjollnir", "disperser",
    "sange_and_yasha", "silver_edge", "assault", "maelstrom", "mask_of_madness", "power_treads",
    "desolator", "lesser_crit", "basher", "hurricane_pike", "harpoon", "swift_blink",
}
OFFLANE_ITEMS = {"blink", "pipe", "crimson_guard", "vanguard", "blade_mail", "shivas_guard",
                 "lotus_orb", "heavens_halberd", "overwhelming_blink", "assault", "black_king_bar"}
MID_ITEMS = {"bottle", "kaya", "kaya_and_sange", "yasha_and_kaya", "blink", "black_king_bar",
             "witch_blade", "parasma", "octarine_core", "sphere"}


def role_factor(name, cost, position, role):
    """Cat de potrivit e un item pentru pozitia ta (1 = neutru)."""
    if role == "support":
        if name in SUPPORT_ITEMS:
            return 1.4
        if name in CARRY_ITEMS:
            return 0.25
        return 0.6 if cost >= 4500 else 1.0      # supportii rar ajung la item-e foarte scumpe
    f = 0.35 if name in SUPPORT_ITEMS else 1.0
    if position == "POSITION_1" and name in CARRY_ITEMS:
        f = 1.3
    elif position == "POSITION_2" and name in MID_ITEMS:
        f = 1.3
    elif position == "POSITION_3":
        f = 1.35 if name in OFFLANE_ITEMS else (0.7 if name in CARRY_ITEMS - OFFLANE_ITEMS else f)
    return f

# tag -> ce face inamicul + raspunsuri pentru core (pos 1-3) si support (pos 4-5)
COUNTERS = {
    "invis": {"why": "e invizibil", "core": [], "support": [], "consumables": ["dust", "ward_sentry"]},
    "evasion": {"why": "are evasion (îți ratezi atacurile)", "core": ["monkey_king_bar", "bloodthorn"],
                "support": []},
    "illusions": {"why": "are iluzii / unități multiple", "core": ["mjollnir", "bfury", "maelstrom", "radiance", "shivas_guard"],
                  "support": ["crimson_guard"]},
    "magic_burst": {"why": "face mult damage magic", "core": ["black_king_bar", "pipe"],
                    "support": ["glimmer_cape", "pipe"]},
    "physical": {"why": "lovește puternic fizic", "core": ["blade_mail", "shivas_guard", "assault", "butterfly"],
                 "support": ["ghost", "force_staff", "solar_crest"]},
    "healing": {"why": "se vindecă mult", "core": ["skadi", "shivas_guard", "spirit_vessel"],
                "support": ["spirit_vessel"]},
    "passives": {"why": "are pasive puternice (trebuie 'break')", "core": ["silver_edge"], "support": []},
    "elusive": {"why": "fuge / e greu de prins", "core": ["orchid", "bloodthorn", "abyssal_blade", "nullifier"],
                "support": ["rod_of_atos", "sheepstick", "orchid"]},
    "disable": {"why": "are mult stun / silence", "core": ["black_king_bar", "manta", "lotus_orb"],
                "support": ["glimmer_cape", "lotus_orb", "cyclone"]},
    "buffs": {"why": "are buff-uri care trebuie scoase (dispel)", "core": ["nullifier", "diffusal_blade"],
              "support": ["cyclone"]},
}

HERO_TAGS = {
    "riki": ["invis"], "bounty_hunter": ["invis"], "clinkz": ["invis", "physical"],
    "weaver": ["invis", "elusive"], "nyx_assassin": ["invis", "magic_burst"],
    "templar_assassin": ["invis", "physical"], "mirana": ["invis"], "invoker": ["invis", "magic_burst"],
    "treant": ["invis", "healing"], "sand_king": ["invis", "magic_burst"], "void_spirit": ["elusive", "magic_burst"],
    "phantom_assassin": ["evasion", "physical", "passives"], "windrunner": ["evasion", "elusive"],
    "brewmaster": ["evasion"], "troll_warlord": ["physical", "buffs"],
    "phantom_lancer": ["illusions", "elusive"], "naga_siren": ["illusions"], "chaos_knight": ["illusions", "physical"],
    "terrorblade": ["illusions", "physical"], "meepo": ["illusions"], "broodmother": ["illusions"],
    "lycan": ["illusions", "physical"], "beastmaster": ["illusions"], "arc_warden": ["illusions"],
    "enigma": ["illusions", "disable"], "nature_prophet": ["illusions", "elusive"], "visage": ["illusions"],
    "lion": ["magic_burst", "disable"], "lina": ["magic_burst"], "zuus": ["magic_burst"],
    "skywrath_mage": ["magic_burst", "disable"], "leshrac": ["magic_burst"], "tinker": ["magic_burst", "elusive"],
    "queenofpain": ["magic_burst", "elusive"], "storm_spirit": ["magic_burst", "elusive"],
    "puck": ["magic_burst", "elusive", "disable"], "ember_spirit": ["elusive", "physical"],
    "antimage": ["elusive", "physical"], "slark": ["elusive", "physical", "passives"],
    "faceless_void": ["physical", "disable"], "sven": ["physical", "buffs"], "juggernaut": ["physical"],
    "ursa": ["physical", "buffs"], "drow_ranger": ["physical"], "medusa": ["physical", "passives"],
    "spectre": ["physical", "passives"], "bristleback": ["passives"], "huskar": ["healing", "passives"],
    "necrolyte": ["healing", "magic_burst"], "alchemist": ["healing", "physical"], "morphling": ["healing", "elusive"],
    "oracle": ["healing", "buffs"], "wisp": ["healing"], "omniknight": ["buffs", "healing"],
    "dazzle": ["healing", "buffs"], "abaddon": ["buffs", "passives"], "legion_commander": ["buffs", "physical"],
    "shadow_shaman": ["disable"], "rubick": ["disable"], "bane": ["disable"], "silencer": ["disable"],
    "death_prophet": ["magic_burst"], "doom_bringer": ["disable"], "pugna": ["magic_burst"],
    "ogre_magi": ["buffs"], "life_stealer": ["physical", "healing"], "monkey_king": ["physical"],
    "slardar": ["physical", "disable"], "night_stalker": ["physical"], "bloodseeker": ["healing"],
    "viper": ["magic_burst"], "tidehunter": ["disable"], "magnataur": ["disable"], "earthshaker": ["disable", "magic_burst"],
    "batrider": ["disable", "elusive"], "kunkka": ["physical", "disable"], "dark_seer": ["illusions"],
    "witch_doctor": ["magic_burst", "healing"], "warlock": ["healing", "disable"], "jakiro": ["magic_burst"],
    "crystal_maiden": ["magic_burst", "disable"], "shadow_fiend": ["physical", "magic_burst"],
    "razor": ["physical"], "gyrocopter": ["physical", "magic_burst"], "luna": ["physical"],
    "pangolier": ["elusive", "disable"], "marci": ["physical", "buffs"], "muerta": ["physical", "magic_burst"],
    "dawnbreaker": ["healing"], "primal_beast": ["disable"], "hoodwink": ["elusive"], "ringmaster": ["disable"],
}


def role_of(position, hero_roles):
    """'core' sau 'support': din pozitia aleasa, altfel ghicit din rolurile eroului."""
    if position in ("POSITION_4", "POSITION_5"):
        return "support"
    if position in ("POSITION_1", "POSITION_2", "POSITION_3"):
        return "core"
    roles = set(hero_roles or [])
    return "support" if "Support" in roles and "Carry" not in roles else "core"


def enemy_threats(enemies):
    """[(nume inamic, [tag-uri, cel mai important primul])]"""
    out = []
    for npc in enemies:
        short = npc.replace("npc_dota_hero_", "")
        name = P.Constants.heroes_by_npc.get(npc, {}).get("localized_name", short)
        out.append((name, HERO_TAGS.get(short, [])))
    return out


def threats_by_tag(threats):
    by_tag = {}
    for name, tags in threats:
        for rank, tag in enumerate(tags):
            by_tag.setdefault(tag, []).append((rank, name))
    # tag-urile care privesc mai multi inamici / sunt principale la ei vin primele
    return sorted(by_tag.items(), key=lambda kv: (-len(kv[1]), min(r for r, _ in kv[1])))


def _known(name):
    return not P.Constants.items_by_name or name in P.Constants.items_by_name


def _component_progress(name, owned_direct):
    comps = P.Constants.items_by_name.get(name, {}).get("components") or []
    have = [c for c in comps if c in owned_direct]
    return sum(P.item_info(c)["cost"] for c in have), [P.item_info(c)["dname"] for c in have]


def make_plan(hero, phases, owned_direct, owned_all, gold, phase, enemies, position):
    hero_name = hero["localized_name"]
    role = role_of(position, hero.get("roles"))
    threats = enemy_threats(enemies)
    popular = {it["name"] for p in phases for it in p["items"]}

    # ---- inainte de horn: kit-ul de start, in limita gold-ului de start
    if phase == 0:
        kit, total = [], 0
        for it in phases[0]["items"] if phases else []:
            if it["name"] in owned_all or it["name"] in BOOT_UPGRADES:
                continue
            if role == "core" and it["name"] in SUPPORT_MARKERS | {"ward_dispenser"}:
                continue  # ward-urile din statistici sunt ale supportilor
            if role == "support" and it["name"] in {"quelling_blade"}:
                continue
            if total + it["cost"] <= STARTING_GOLD:
                kit.append(dict(it, reason="cel mai cumpărat la start"))
                total += it["cost"]
        cons = _consumables(threats, owned_all)
        if role == "support" and not any(i["name"] == "ward_observer" for i in kit) and _known("ward_observer"):
            kit.insert(0, dict(P.item_info("ward_observer"), reason="ca support, ward-urile sunt treaba ta"))
        return {"mode": "start", "role": role, "role_auto": not position, "kit": kit, "kit_cost": total,
                "consumables": cons, "threats": _threat_list(threats, owned_all, role)}

    # ---- candidati din popularitate: faza curenta (greutate 1) + urmatoarea (0.75)
    cands = {}
    for idx, weight in ((phase, 1.0), (phase + 1, 0.75)):
        if idx >= len(phases) or not phases[idx]["items"]:
            continue
        top = max(it["count"] for it in phases[idx]["items"]) or 1
        for it in phases[idx]["items"]:
            n = it["name"]
            if n in CONSUMABLES or n in owned_all or not _known(n):
                continue
            if it["cost"] < CHEAP_LIMIT and n not in BOOTS:
                continue
            fit = role_factor(n, it["cost"], position, role)
            if fit < 0.3:
                continue
            score = weight * (0.35 + 0.6 * it["count"] / top) * fit
            if n not in cands or score > cands[n]["score"]:
                wr = f" · {it['winrate']}% win" if it.get("winrate") is not None else ""
                reasons = [f"popular pe {hero_name} în {PHASE_NAMES[idx]}{wr}"]
                if fit >= 1.3:
                    reasons.append("potrivit pentru poziția ta")
                cands[n] = dict(it, score=score, reasons=reasons, kind="build")

    # ---- contra-item-e: cate unul pe fiecare amenintare (daca n-ai deja raspuns la ea)
    served = set()   # inamicii pentru care avem deja un raspuns (in plan sau in inventar)
    for tag, entries in threats_by_tag(threats):
        rule = COUNTERS[tag]
        names = [n for _, n in entries]
        options = [i for i in rule[role] if _known(i)]
        if any(i in owned_all for i in options):
            served.update(names)
            continue
        if not options or all(n in served for n in names):
            continue
        served.update(names)
        pick = next((i for i in options if i in popular), options[0])  # prefera ce se joaca pe eroul tau
        reason = f"contra {', '.join(names)}: {rule['why']}"
        bonus = 0.95 + 0.12 * (len(names) - 1) + (0.1 if pick in popular else 0)
        if pick in cands:
            cands[pick]["score"] = max(cands[pick]["score"], bonus) + 0.15
            cands[pick]["reasons"].insert(0, reason)
            cands[pick]["kind"] = "counter"
        else:
            info = P.item_info(pick)
            cands[pick] = dict(info, owned=False, count=0, score=bonus, reasons=[reason], kind="counter")

    # ---- un singur fel de boots
    has_upgraded_boots = bool(owned_direct & BOOT_UPGRADES)
    boots = sorted((n for n in cands if n in BOOTS), key=lambda n: -cands[n]["score"])
    for n in boots:
        late_travel = n.startswith("travel_boots") and phase >= 2
        if (has_upgraded_boots and not late_travel) or (not has_upgraded_boots and n != boots[0]):
            del cands[n]

    # ---- grupuri exclusive (ex: un singur Wraith Band / Bracer / Null Talisman)
    for group in EXCLUSIVE_GROUPS:
        in_group = sorted((n for n in cands if n in group), key=lambda n: -cands[n]["score"])
        keep = [] if owned_direct & group else in_group[:1]
        for n in in_group:
            if n not in keep:
                del cands[n]

    ranked = sorted(cands.values(), key=lambda c: -c["score"])[:4]
    for c in ranked:
        have_cost, have_names = _component_progress(c["name"], owned_direct)
        c["have_cost"], c["have_parts"] = have_cost, have_names
        c["missing"] = max(0, c["cost"] - have_cost - (gold or 0)) if gold is not None else None
        c["affordable"] = c["missing"] == 0
        c["reason"] = "; ".join(c.pop("reasons"))
        c.pop("score", None)
    return {"mode": "build", "role": role, "role_auto": not position, "buy_now": ranked[0] if ranked else None, "after": ranked[1:],
            "consumables": _consumables(threats, owned_all),
            "threats": _threat_list(threats, owned_all, role)}


def _consumables(threats, owned_all):
    invis = [name for name, tags in threats if "invis" in tags]
    if not invis:
        return []
    return [dict(P.item_info(i), reason=f"vezi invizibilii: {', '.join(invis)}")
            for i in COUNTERS["invis"]["consumables"]]


def _threat_list(threats, owned_all, role):
    """Rezumat pentru UI, cate un rand per inamic: ce problema pune + cu ce raspunzi."""
    out = []
    for name, tags in threats:
        if not tags:
            out.append({"vs": [name], "why": "", "covered": [], "answers": []})
            continue
        answers, covered = [], []
        for tag in tags:
            rule = COUNTERS[tag]
            opts = [i for i in (rule[role] or rule.get("consumables", [])) if _known(i)]
            covered += [P.item_info(i)["dname"] for i in opts if i in owned_all]
            if opts and opts[0] not in answers:
                answers.append(opts[0])
        out.append({"vs": [name], "why": ", ".join(COUNTERS[t]["why"] for t in tags),
                    "covered": sorted(set(covered)), "answers": [P.item_info(i) for i in answers[:3]]})
    return out


def quick_tips(rec):
    """Sfat local (fara AI): rezumat in cuvinte al planului."""
    lines = []
    plan = rec.get("plan") or {}
    if plan.get("mode") == "start":
        kit = ", ".join(i["dname"] for i in plan.get("kit", []))
        if kit:
            lines.append(f"Start: cumpără {kit} ({plan.get('kit_cost')} gold).")
    elif plan.get("buy_now"):
        b = plan["buy_now"]
        miss = f" Îți mai trebuie {b['missing']} gold." if b.get("missing") else " Ai destul gold, cumpără-l acum!"
        lines.append(f"Următorul item: {b['dname']} ({b['reason']}).{miss if b.get('missing') is not None else ''}")
        if plan.get("after"):
            lines.append("După aceea: " + ", ".join(i["dname"] for i in plan["after"]) + ".")
    for c in plan.get("consumables", []):
        lines.append(f"Ia {c['dname']}: {c['reason']}.")
    for t in plan.get("threats", []):
        if not t["covered"] and t["answers"]:
            lines.append(f"{', '.join(t['vs'])} {t['why']} → răspuns: {' / '.join(a['dname'] for a in t['answers'])}.")
    sk = (rec.get("skills") or {}).get("next")
    if sk:
        lines.append(("Crește acum: " if sk["now"] else "La nivelul următor crește: ") + sk["ability"]["dname"] + ".")
    if not rec.get("enemies"):
        lines.append("Adaugă eroii inamici ca să adaptez build-ul la ei.")
    return "\n".join(f"• {l}" for l in lines) or "Nu am încă date despre meci."


# ------------------------------------------------------------------ build adaptat de AI

# Item-e "mari" uzuale, ca AI-ul sa poata iesi si din ce e popular cand meciul o cere.
CORE_POOL = [
    "black_king_bar", "blink", "manta", "butterfly", "skadi", "satanic", "abyssal_blade", "greater_crit",
    "monkey_king_bar", "bloodthorn", "silver_edge", "assault", "shivas_guard", "heart", "sphere", "aeon_disk",
    "refresher", "octarine_core", "sheepstick", "ultimate_scepter", "travel_boots", "force_staff",
    "glimmer_cape", "ghost", "eternal_shroud", "pipe", "crimson_guard", "lotus_orb", "blade_mail", "desolator",
    "maelstrom", "mjollnir", "gungir", "harpoon", "disperser", "nullifier", "ethereal_blade",
    "kaya_and_sange", "sange_and_yasha", "yasha_and_kaya", "heavens_halberd", "solar_crest", "spirit_vessel",
    "holy_locket", "guardian_greaves", "boots_of_bearing", "arcane_boots", "phase_boots", "power_treads",
    "tranquil_boots", "hand_of_midas", "echo_sabre", "orchid", "diffusal_blade", "radiance", "bfury",
    "vanguard", "hurricane_pike", "wind_waker", "rod_of_atos", "overwhelming_blink", "swift_blink",
    "arcane_blink", "devastator", "khanda", "phylactery", "pavise", "revenants_brooch", "bloodstone",
    "mekansm", "cyclone", "veil_of_discord", "urn_of_shadows", "medallion_of_courage", "falcon_blade",
    "wraith_band", "bracer", "null_talisman", "magic_wand", "dust", "ward_sentry", "gem", "smoke_of_deceit",
]


def candidates(phases, owned_all, owned_direct, role):
    """Item-ele din care poate alege AI-ul: populare + contra-item-e + item-e mari uzuale (fara ce ai deja)."""
    names = [it["name"] for p in phases for it in p["items"]]
    for rule in COUNTERS.values():
        names += rule["core"] + rule["support"] + rule.get("consumables", [])
    names += CORE_POOL
    has_boots = bool(owned_direct & BOOT_UPGRADES)
    out, seen = [], set()
    for n in names:
        if n in seen or n in owned_all or not _known(n):
            continue
        if n in CONSUMABLES and n not in ("dust", "ward_sentry", "smoke_of_deceit"):
            continue
        if has_boots and n in BOOTS and not n.startswith("travel_boots"):
            continue
        it = P.Constants.items_by_name.get(n, {})
        if P.Constants.items_by_name and not it.get("cost") and n not in ("ward_sentry",):
            continue   # retete / item-e care nu se cumpara
        seen.add(n)
        out.append(n)
    return out[:120]


def stats_table(phases):
    """Statisticile compacte pentru AI: item -> popularitate relativa, winrate, minut tipic."""
    out = {}
    for i, p in enumerate(phases):
        top = max((it["count"] for it in p["items"]), default=0) or 1
        for it in p["items"]:
            row = {"faza": PHASE_NAMES[i], "popularitate": f"{round(100 * it['count'] / top)}%", "cost": it["cost"]}
            if it.get("winrate") is not None:
                row["winrate"] = f"{it['winrate']}%"
            if it.get("minute") is not None:
                row["minut_tipic"] = it["minute"]
            out.setdefault(it["name"], row)
    return out


def apply_ai(plan, ai_items, gold, owned_direct, owned_all, enemies):
    """Inlocuieste 'Cumpara acum' + 'Apoi' cu alegerile AI-ului (validate)."""
    tags = {t for _, ts in enemy_threats(enemies) for t in ts}   # doar amenintarile din meciul asta
    counter_items = {i for t in tags for i in COUNTERS[t]["core"] + COUNTERS[t]["support"]}
    picked = []
    for it in ai_items:
        n = it["item"]
        if n in owned_all or not _known(n) or n in {p["name"] for p in picked}:
            continue
        info = P.item_info(n)
        have_cost, have_names = _component_progress(n, owned_direct)
        missing = max(0, info["cost"] - have_cost - (gold or 0)) if gold is not None else None
        picked.append(dict(info, reason=it["why"], kind="counter" if n in counter_items else "build",
                           have_cost=have_cost, have_parts=have_names, missing=missing, affordable=missing == 0))
    if not picked:
        return False
    plan["buy_now"], plan["after"] = picked[0], picked[1:4]
    return True
