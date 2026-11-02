# Dota Coach

Aplicație care rulează lângă Dota 2 și îți spune, live, **ce să cumperi acum și de ce**:
- **„Cumpără acum”**: un singur item clar, cu motivul și câți bani îți mai trebuie. Ține cont de ce ai deja
  (inclusiv componente), de poziția ta și de inamici. Recomandă un singur fel de boots;
- **inamicii**: îi alegi din grila de portrete. Pentru fiecare îți spune ce problemă îți face
  (evasion, invizibil, burst magic…) și cu ce îi contrezi. Contra-item-ele intră direct în build;
- **poziția**: Pos 1-5 schimbă recomandările (carry, mid, offlane, support);
- **abilități și talente**: ce abilitate crești acum și ce talente aleg jucătorii pro;
- **coach**: răspunde mereu cu un sfat din reguli. Cu o cheie API Anthropic răspunde la orice întrebare (Claude).

E sigur: folosește Game State Integration, sistemul oficial Valve. Nu citește memoria jocului
și nu desenează peste joc.

## Instalare rapidă (.exe)

1. Rulează `DotaCoach.exe`. Se deschide fereastra aplicației (nu mai e nevoie de browser). La prima pornire:
   - găsește singur Dota 2 și instalează config-ul GSI;
   - creează `config.json` și `dota-coach.log` lângă exe.
2. În Steam → Dota 2 → Properties → Launch Options adaugă: `-gamestateintegration`
3. Pornește Dota (repornește-l dacă era deschis) și intră într-un meci.

Butonul **📌 Mereu deasupra** ține fereastra peste joc. E util pe un singur monitor, cu Dota în modul
„Borderless window”. În fullscreen exclusiv, Windows nu poate afișa nimic peste joc.

Când închizi fereastra, se oprește toată aplicația.

Pe telefon: `http://<IP-ul-PC-ului>:3000` în browser, cât timp aplicația rulează pe PC.

Fereastra folosește Microsoft Edge WebView2, preinstalat pe Windows 10 și 11. Dacă lipsește,
aplicația se deschide în browser.

## Rulare din Python

```
pip install pywebview
python app.py        # fereastra desktop
python server.py     # varianta in browser (pentru dezvoltare)
```

Python 3.8+. Fără pywebview, `app.py` deschide browserul. Pentru Coach AI: `pip install anthropic`.

## Construire .exe

- **Local, pe Windows:** dublu-click pe `build.bat` → `dist\DotaCoach.exe`.
- **Automat, pe GitHub:** urcă proiectul pe GitHub; workflow-ul din `.github/workflows/build.yml`
  construiește exe-ul la fiecare tag `v*` (sau manual din tab-ul Actions).

## Setări opționale

Din pagină (secțiunea **Setări**) sau din `config.json`:

| Cheie | Pentru ce | De unde |
|---|---|---|
| `stratz_token` | build-uri pe poziție + MMR | gratuit, https://stratz.com/api |
| `gemini_api_key` | Coach AI cu Gemini (**gratuit**, cu limită zilnică) | https://aistudio.google.com/apikey |
| `ai_provider` | cine răspunde: `gemini` sau `anthropic` | se alege și din ⚙ Setări |
| `gemini_model` | model Gemini anume | gol = ales automat (cel mai nou Flash) |
| `anthropic_api_key` | Coach AI cu Claude (plătit per întrebare) | https://console.anthropic.com |
| `ai_model` | modelul Claude | implicit `claude-opus-5-5` |
| `position`, `bracket` | filtrele implicite | se aleg și din pagină |

Fără token STRATZ, item-ele vin de pe OpenDota (meciuri recente, toate pozițiile amestecate). Aplicația
le ajustează apoi după poziția aleasă (ex: la support scoate item-ele de carry). Cu STRATZ, datele sunt exact pentru poziția și MMR-ul tău.
Skill build-ul și talentele vin de pe OpenDota (meciuri pro din ultimele 60 de zile).

Coach AI se apelează doar când apeși un buton. Cu **Gemini** e gratuit: aplicația alege singură cel mai
nou model Flash disponibil pe cheia ta și, dacă ai atins limita gratuită, trece pe altul (de ex. Flash-Lite).
Pe nivelul gratuit, Google poate folosi întrebările ca să-și îmbunătățească modelele. Cu **Claude**, un apel
costă câțiva cenți; dacă modelul refuză cererea, API-ul trece automat pe alt model (fallback activat).

**Atenție:** serverul ascultă în rețeaua locală (ca să meargă pe telefon). Oricine e pe același
Wi-Fi poate deschide pagina și folosi Coach AI cu cheia ta. Pe o rețea publică, pune
`"port"` pe altceva sau oprește aplicația.

## Test fără Dota

```
python server.py
python simulate.py npc_dota_hero_juggernaut
```

## Fișiere

- `app.py`: aplicația desktop (fereastra)
- `server.py`: serverul și starea meciului
- `coach.py`: motorul de recomandare (plan de item-e, poziție, contra-item-e, sfaturi din reguli)
- `providers.py`: OpenDota + STRATZ (cache în `cache/`)
- `ai.py`: Coach AI
- `setup_gsi.py`: găsește Dota și instalează config-ul GSI
- `index.html`: interfața
- `gamestate_integration_coach.cfg`: config-ul GSI, pentru instalare manuală
- `icon.ico`: iconița aplicației

## Limitări

- Dota nu trimite eroii inamici jucătorilor (anti-cheat), deci îi adaugi manual.
- Query-ul STRATZ (`providers.py` → `stratz_items`) n-a putut fi testat pe API-ul real. Dacă
  STRATZ își schimbă schema, aplicația revine automat pe OpenDota și scrie motivul în `dota-coach.log`.
