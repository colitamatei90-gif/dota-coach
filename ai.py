"""
Sfaturi in limbaj natural de la Claude, pe baza starii live a meciului.
Optional: are nevoie de `pip install anthropic` si de o cheie API
(config.json -> anthropic_api_key, sau variabila de mediu ANTHROPIC_API_KEY).
"""
import json
import os

SYSTEM = """Esti un coach de Dota 2 care ajuta un jucator IN TIMPUL meciului.
Primesti starea meciului (erou, pozitie, timp, gold, item-e, abilitati, inamici) si statistici
actuale de build (item-e populare pe faze, skill build, contra-item-e sugerate).

Reguli:
- Raspunde in romana, scurt: maximum 5 puncte, fiecare intr-o singura propozitie. Jucatorul se uita in timp ce joaca.
- Incepe cu cel mai important lucru de facut ACUM (urmatorul item / ce sa schimbe).
- Adapteaza-te la inamici si la item-ele pe care le are deja; explica pe scurt de ce.
- Bazeaza-te pe statisticile primite; patch-ul se schimba, deci nu inventa cifre sau mecanici de care nu esti sigur.
- Daca jucatorul pune o intrebare, raspunde in primul rand la ea."""


def available(cfg):
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "Instaleaza pachetul: pip install anthropic"
    if not (cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")):
        return False, "Lipseste cheia API (config.json -> anthropic_api_key)"
    return True, ""


def advise(cfg, context, question=""):
    ok, why = available(cfg)
    if not ok:
        return {"error": why}

    import anthropic
    client = anthropic.Anthropic(api_key=cfg.get("anthropic_api_key") or None, timeout=60.0)
    user = "Starea meciului:\n" + json.dumps(context, ensure_ascii=False, indent=1)
    user += f"\n\nIntrebarea jucatorului: {question}" if question else "\n\nCe ar trebui sa fac acum?"

    try:
        resp = client.beta.messages.create(
            model=cfg.get("ai_model") or "claude-opus-5-5",
            max_tokens=4000,
            system=SYSTEM,
            output_config={"effort": "low"},       # raspuns rapid; in meci conteaza viteza
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                    # daca un model refuza, preia altul automat
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        return {"error": "Cheia API e invalida"}
    except anthropic.RateLimitError:
        return {"error": "Prea multe cereri, incearca peste cateva secunde"}
    except anthropic.APIStatusError as e:
        return {"error": f"Eroare API ({e.status_code}): {e.message}"}
    except anthropic.APIConnectionError:
        return {"error": "Nu ma pot conecta la API (internet?)"}

    if resp.stop_reason == "refusal":
        return {"error": "Modelul a refuzat cererea"}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return {"text": text or "(raspuns gol)"}
