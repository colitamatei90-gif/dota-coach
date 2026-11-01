# Dota Coach

Aplicație care rulează lângă Dota 2 și îți arată, live:
- **următorul item** de cumpărat (marcat cu verde dacă îți permiți acum), adaptat la ce ai deja;
- **contra-item-e** în funcție de eroii inamici;
- **skill build-ul** din meciurile pro și **ce abilitate să crești acum**;
- **talentele** cele mai alese, cu winrate;
- build-uri filtrate pe **poziție și MMR** (cu STRATZ);
- **Coach AI**: sfaturi în limbaj natural despre meciul tău (cu Claude).

E sigur: folosește Game State Integration, sistemul oficial Valve. Nu citește memoria jocului
și nu desenează peste joc.

## Instalare rapidă (.exe)

1. Rulează `DotaCoach.exe` (vezi mai jos cum îl construiești). La prima pornire:
   - găsește singur Dota 2 și instalează config-ul GSI;
   - creează `config.json` lângă exe;
   - deschide pagina în browser.
2. În Steam → Dota 2 → Properties → Launch Options adaugă: `-gamestateintegration`
3. Pornește Dota (repornește-l dacă era deschis) și intră într-un meci.

Pe telefon: `http://<IP-ul-PC-ului>:3000` (aceeași rețea Wi-Fi; permite aplicația în firewall).

## Rulare din Python

```
python server.py
```

Python 3.8+. Fără dependențe; doar pentru Coach AI: `pip install anthropic`.

## Construire .exe

- **Local, pe Windows:** dublu-click pe `build.bat` → `dist\DotaCoach.exe`.
- **Automat, pe GitHub:** urcă proiectul pe GitHub; workflow-ul din `.github/workflows/build.yml`
  construiește exe-ul la fiecare tag `v*` (sau manual din tab-ul Actions).

## Setări opționale

Din pagină (secțiunea **Setări**) sau din `config.json`:

| Cheie | Pentru ce | De unde |
|---|---|---|
| `stratz_token` | build-uri pe poziție + MMR | gratuit, https://stratz.com/api |
| `anthropic_api_key` | Coach AI | https://console.anthropic.com (plătit per utilizare) |
| `ai_model` | modelul AI | implicit `claude-opus-5-5` |
| `position`, `bracket` | filtrele implicite | se aleg și din pagină |

Fără token STRATZ, item-ele vin de pe OpenDota (toate pozițiile, meciuri recente).
Skill build-ul și talentele vin de pe OpenDota (meciuri pro din ultimele 60 de zile).

Coach AI se apelează doar când apeși butonul (un apel ≈ câțiva cenți). Dacă un model refuză
cererea, API-ul trece automat pe alt model (fallback activat).

**Atenție:** serverul ascultă în rețeaua locală (ca să meargă pe telefon). Oricine e pe același
Wi-Fi poate deschide pagina și folosi Coach AI cu cheia ta. Pe o rețea publică, pune
`"port"` pe altceva sau oprește aplicația.

## Test fără Dota

```
python server.py
python simulate.py npc_dota_hero_juggernaut
```

## Fișiere

- `server.py`: serverul, logica de recomandare și contra-item-ele
- `providers.py`: OpenDota + STRATZ (cache în `cache/`)
- `ai.py`: Coach AI
- `setup_gsi.py`: găsește Dota și instalează config-ul GSI
- `index.html`: interfața
- `gamestate_integration_coach.cfg`: config-ul GSI, pentru instalare manuală

## Limitări

- Dota nu trimite eroii inamici jucătorilor (anti-cheat), deci îi adaugi manual.
- Query-ul STRATZ (`providers.py` → `stratz_items`) n-a putut fi testat pe API-ul real. Dacă
  STRATZ își schimbă schema, aplicația revine automat pe OpenDota și scrie motivul în consolă.
