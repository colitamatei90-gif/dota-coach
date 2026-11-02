"""
Sfaturi in limbaj natural pe baza starii live a meciului.

Furnizori:
- Gemini (Google): are nivel gratuit. Cheie din https://aistudio.google.com/apikey
  -> config.json: gemini_api_key. Fara biblioteci in plus (REST direct).
- Claude (Anthropic): platit per intrebare. Cheie din https://console.anthropic.com
  -> config.json: anthropic_api_key. Necesita `pip install anthropic`.

ai_provider = "gemini" | "anthropic" | "" (auto: Gemini daca exista cheie, altfel Claude).
"""
import json
import os
import re
import threading
import urllib.error
import urllib.request

SYSTEM = """Esti un coach de Dota 2 care ajuta un jucator IN TIMPUL meciului.
Primesti starea meciului (erou, pozitie, timp, gold, item-e, abilitati, inamici) si statistici
actuale de build (item-e populare pe faze, skill build, contra-item-e sugerate).

Reguli:
- Raspunde in romana, scurt: maximum 5 puncte, fiecare intr-o singura propozitie. Jucatorul se uita in timp ce joaca.
- Incepe cu cel mai important lucru de facut ACUM (urmatorul item / ce sa schimbe).
- Adapteaza-te la inamici si la item-ele pe care le are deja; explica pe scurt de ce.
- Bazeaza-te pe statisticile primite; patch-ul se schimba, deci nu inventa cifre sau mecanici de care nu esti sigur.
- Daca jucatorul pune o intrebare, raspunde in primul rand la ea.
- Text simplu, fara Markdown (fara **, #, tabele)."""

PROVIDER_NAMES = {"gemini": "Gemini", "anthropic": "Claude"}


def _gemini_key(cfg):
    return cfg.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or ""


def _anthropic_key(cfg):
    return cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or ""


def provider(cfg):
    p = cfg.get("ai_provider") or ""
    if p in PROVIDER_NAMES:
        return p
    if _gemini_key(cfg):
        return "gemini"
    if _anthropic_key(cfg):
        return "anthropic"
    return "gemini"   # implicit: varianta gratuita


def available(cfg):
    p = provider(cfg)
    if p == "gemini":
        if not _gemini_key(cfg):
            return False, "Pentru întrebări libere adaugă o cheie Gemini gratuită (⚙ Setări)"
        return True, ""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "Pentru Claude instalează pachetul: pip install anthropic"
    if not _anthropic_key(cfg):
        return False, "Pentru întrebări libere adaugă o cheie API (⚙ Setări)"
    return True, ""


def _user_message(context, question):
    msg = "Starea meciului:\n" + json.dumps(context, ensure_ascii=False, indent=1)
    msg += f"\n\nIntrebarea jucatorului: {question}" if question else "\n\nCe ar trebui sa fac acum?"
    return msg


def advise(cfg, context, question=""):
    ok, why = available(cfg)
    if not ok:
        return {"error": why}
    try:
        if provider(cfg) == "gemini":
            return _gemini(cfg, _user_message(context, question))
        return _claude(cfg, _user_message(context, question))
    except Exception as e:  # orice altceva: aratam motivul in loc sa pice cererea
        import traceback
        traceback.print_exc()
        return {"error": f"Eroare neașteptată: {type(e).__name__}: {e}"}


# ------------------------------------------------------------------ Gemini

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_gemini_models = {"key": None, "list": []}   # modelele potrivite pentru cheia curenta
_gemini_lock = threading.Lock()
SKIP_WORDS = ("embedding", "image", "tts", "audio", "live", "vision", "thinking-exp", "learnlm", "gemma", "robotics", "computer")


class GeminiError(Exception):
    def __init__(self, code, status, message):
        super().__init__(message)
        self.code, self.status, self.message = code, status, message


def _gemini_call(method, path, key, body=None, timeout=60):
    req = urllib.request.Request(
        GEMINI_BASE + path, method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8")).get("error", {})
        except Exception:
            err = {}
        raise GeminiError(e.code, err.get("status", ""), err.get("message", str(e))) from None


def _version(name):
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def _rank(name):
    """Mai mic = mai bun. Preferam: Flash stabil > Flash-Lite stabil > Flash preview; versiunea cea mai noua."""
    n = name.lower()
    preview = "preview" in n or "exp" in n
    lite = "lite" in n
    tier = (2 if preview else 0) + (1 if lite else 0)
    return (tier, -_version(n), len(n))


def _gemini_candidates(key, refresh=False):
    """Lista modelelor Flash disponibile pe cheia ta, de la cel mai potrivit."""
    with _gemini_lock:
        if not refresh and _gemini_models["key"] == key and _gemini_models["list"]:
            return _gemini_models["list"]
        names, token = [], ""
        for _ in range(10):  # paginare
            res = _gemini_call("GET", "/models?pageSize=200" + (f"&pageToken={token}" if token else ""), key, timeout=20)
            for m in res.get("models", []):
                name = m.get("name", "").replace("models/", "")
                n = name.lower()
                if ("generateContent" in (m.get("supportedGenerationMethods") or [])
                        and n.startswith("gemini-") and "flash" in n
                        and not any(w in n for w in SKIP_WORDS)):
                    names.append(name)
            token = res.get("nextPageToken") or ""
            if not token:
                break
        names = sorted(set(names), key=_rank)
        print(f"[gemini] modele disponibile: {', '.join(names[:6]) or 'niciunul'}")
        _gemini_models.update(key=key, list=names)
        return names


def _gemini(cfg, user_msg, system=None, schema=None):
    key = _gemini_key(cfg)
    try:
        forced = (cfg.get("gemini_model") or "").strip()
        models = [forced] if forced else _gemini_candidates(key)
    except GeminiError as e:
        return {"error": _gemini_friendly(e)}
    except urllib.error.URLError:
        return {"error": "Nu mă pot conecta la Gemini (internet?)"}
    if not models:
        return {"error": "Cheia Gemini nu are acces la niciun model Flash"}

    body = {
        "systemInstruction": {"parts": [{"text": system or SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.4 if schema else 0.6},
    }
    if schema:
        body["generationConfig"].update(responseMimeType="application/json", responseSchema=schema)
    last = None
    for model in models[:4]:
        try:
            res = _gemini_call("POST", f"/models/{model}:generateContent", key, body)
        except GeminiError as e:
            last = e
            # limita gratuita depasita sau model retras -> incercam urmatorul model
            if e.code in (404, 429) or e.status in ("RESOURCE_EXHAUSTED", "NOT_FOUND"):
                print(f"[gemini] {model}: {e.code} {e.status} - incerc alt model")
                if e.code == 404:
                    _gemini_models["list"] = []   # lista veche: o reincarcam data viitoare
                continue
            return {"error": _gemini_friendly(e)}
        except urllib.error.URLError:
            return {"error": "Nu mă pot conecta la Gemini (internet?)"}
        return _gemini_text(res, model, raw=bool(schema))
    return {"error": _gemini_friendly(last) if last else "Gemini nu a răspuns"}


def _gemini_text(res, model, raw=False):
    fb = res.get("promptFeedback") or {}
    if fb.get("blockReason"):
        return {"error": f"Gemini a blocat cererea ({fb['blockReason']})"}
    cands = res.get("candidates") or []
    if not cands:
        return {"error": "Gemini a trimis un răspuns gol"}
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not raw:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # fara Markdown in fereastra
    if not text:
        reason = cands[0].get("finishReason", "")
        return {"error": f"Gemini nu a dat text (motiv: {reason or 'necunoscut'})"}
    return {"text": text, "model": model}


def _gemini_friendly(e):
    if e.code in (400, 401, 403) and ("API key" in e.message or e.status in ("PERMISSION_DENIED", "UNAUTHENTICATED")
                                      or "API_KEY" in e.message):
        return "Cheia Gemini e invalidă sau nu are acces. Verifică-o în aistudio.google.com/apikey"
    if e.code == 429 or e.status == "RESOURCE_EXHAUSTED":
        return "Ai atins limita gratuită Gemini pentru moment. Încearcă peste un minut (sau mâine, dacă e limita zilnică)."
    if e.code == 400 and "location" in e.message.lower():
        return "Gemini nu e disponibil gratuit în regiunea ta."
    return f"Eroare Gemini ({e.code}): {e.message[:200]}"


# ------------------------------------------------------------------ Claude

def _claude(cfg, user_msg, system=None, schema=None):
    import anthropic
    client = anthropic.Anthropic(api_key=_anthropic_key(cfg) or None, timeout=60.0)
    output_config = {"effort": "low"}              # raspuns rapid; in meci conteaza viteza
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    try:
        resp = client.beta.messages.create(
            model=cfg.get("ai_model") or "claude-opus-5-5",
            max_tokens=8000,
            system=system or SYSTEM,
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                    # daca un model refuza, preia altul automat
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.AuthenticationError:
        return {"error": "Cheia API Anthropic e invalidă"}
    except anthropic.RateLimitError:
        return {"error": "Prea multe cereri, încearcă peste câteva secunde"}
    except anthropic.APIStatusError as e:
        return {"error": f"Eroare API ({e.status_code}): {e.message}"}
    except anthropic.APIConnectionError:
        return {"error": "Nu mă pot conecta la API (internet?)"}
    if resp.stop_reason == "refusal":
        return {"error": "Modelul a refuzat cererea"}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return {"text": text or "(răspuns gol)", "model": resp.model}


# ------------------------------------------------------------------ build adaptat de AI

PLAN_SYSTEM = """Esti un analist de build-uri Dota 2. In timpul meciului alegi URMATOARELE item-e pe care
jucatorul trebuie sa le cumpere, in ordine, pe baza statisticilor actuale si a situatiei din meci.

Reguli:
- Alegi 5 item-e, doar din lista permisa. Primul = cel mai important de cumparat ACUM.
- Nu alege item-e pe care le are deja (nici componentele lor daca are item-ul mare).
- Un singur fel de boots. Daca are deja boots imbunatatite, nu mai alege altele (exceptie: Boots of Travel in late game).
- Tine cont de pozitie/rol: un support nu face item-e scumpe de carry; un carry nu cumpara item-e de support.
- Adapteaza-te la inamici: daca o amenintare nu e acoperita (ex. evasion, invizibili, burst magic), include raspunsul cand conteaza.
- Statisticile (cat de des e cumparat, winrate, minutul tipic) sunt baza; abate-te de la ele doar cand meciul o cere si spune de ce.
- Tine cont de timp si gold: nu propune item-e de late game la minutul 5 daca exista ceva mai urgent.
- motiv: in romana, maximum 14 cuvinte, concret (ex. "PA are evasion; MKB iti da atacuri sigure").
- rezumat: o propozitie in romana despre strategia de build in acest meci."""


def _plan_schema(candidates, gemini):
    if gemini:   # schema in formatul Gemini (subset OpenAPI)
        return {"type": "OBJECT", "properties": {
            "rezumat": {"type": "STRING"},
            "iteme": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "item": {"type": "STRING", "enum": candidates},
                "motiv": {"type": "STRING"}}, "required": ["item", "motiv"]}}},
            "required": ["rezumat", "iteme"]}
    return {"type": "object", "additionalProperties": False, "required": ["rezumat", "iteme"], "properties": {
        "rezumat": {"type": "string"},
        "iteme": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["item", "motiv"], "properties": {
            "item": {"type": "string", "enum": candidates}, "motiv": {"type": "string"}}}}}}


def plan_build(cfg, context, candidates):
    """Intoarce {"items": [{"item", "why"}], "summary", "model"} sau {"error"}."""
    ok, why = available(cfg)
    if not ok:
        return {"error": why}
    if not candidates:
        return {"error": "nu am item-e candidate"}
    user = "Situatia si statisticile:\n" + json.dumps(context, ensure_ascii=False, indent=1)
    try:
        if provider(cfg) == "gemini":
            res = _gemini(cfg, user, PLAN_SYSTEM, _plan_schema(candidates, True))
        else:
            res = _claude(cfg, user, PLAN_SYSTEM, _plan_schema(candidates, False))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"{type(e).__name__}: {e}"}
    if res.get("error"):
        return res
    try:
        data = json.loads(res["text"])
    except ValueError:
        return {"error": "AI-ul a trimis un JSON invalid"}
    allowed = set(candidates)
    items, seen = [], set()
    for it in data.get("iteme") or []:
        name = (it or {}).get("item")
        if name in allowed and name not in seen:      # validam oricum, chiar daca schema garanteaza
            seen.add(name)
            items.append({"item": name, "why": str(it.get("motiv") or "")[:160]})
    if not items:
        return {"error": "AI-ul nu a ales niciun item valid"}
    return {"items": items[:6], "summary": str(data.get("rezumat") or "")[:240], "model": res.get("model")}
