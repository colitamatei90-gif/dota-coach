"""
Dota Coach - aplicatia desktop (fereastra proprie, fara browser).

Porneste serverul intern (Dota trimite datele live prin HTTP, deci serverul ramane)
si afiseaza interfata intr-o fereastra nativa (Edge WebView2 pe Windows).
Daca fereastra nativa nu poate porni, deschide interfata in browser.
"""
import os
import sys
import threading
import time
import urllib.request

from paths import APP_DIR, load_config, save_config

LOG_PATH = os.path.join(APP_DIR, "dota-coach.log")


def setup_logging():
    """In exe-ul fara consola nu exista stdout: scriem totul in dota-coach.log."""
    if sys.stdout is None or getattr(sys, "frozen", False):
        try:
            log = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
        except OSError:
            pass


class Api:
    """Functii apelabile din pagina (window.pywebview.api.*)."""

    def __init__(self):
        self.window = None
        self.cfg = load_config()

    def get_on_top(self):
        return bool(self.cfg.get("on_top", False))

    def set_on_top(self, value):
        value = bool(value)
        self.cfg = load_config()
        self.cfg["on_top"] = value
        save_config(self.cfg)
        if self.window:
            self.window.on_top = value
        return value


def wait_for_server(url, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url + "/api/heroes", timeout=2)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def selftest(window, url):
    """Folosit doar de testul automat de pe GitHub: verifica fereastra si serverul, apoi inchide."""
    ok = {"loaded": False}
    window.events.loaded += lambda: ok.update(loaded=True)

    def run():
        time.sleep(10)
        try:
            state = urllib.request.urlopen(url + "/api/state", timeout=5).read()
            title = window.evaluate_js("document.title")
            print(f"[selftest] fereastra incarcata: {ok['loaded']}, titlu: {title}, state: {len(state)} bytes")
            code = 0 if ok["loaded"] and title == "Dota Coach" else 1
        except Exception as e:
            print(f"[selftest] EROARE: {e}")
            code = 1
        print(f"[selftest] rezultat: {'OK' if code == 0 else 'ESUAT'}")
        sys.stdout.flush()
        window.destroy()
        os._exit(code)

    threading.Thread(target=run, daemon=True).start()


def main():
    setup_logging()
    import server  # dupa setup_logging, ca mesajele de pornire sa ajunga in log

    url, already_running = server.start(server.get_port())
    if not already_running:
        wait_for_server(url)

    try:
        import webview
    except ImportError:
        print("[app] pywebview nu e instalat - deschid in browser (pip install pywebview)")
        return browser_fallback(url)

    api = Api()
    window = webview.create_window(
        "Dota Coach", url, js_api=api,
        width=1440, height=880, min_size=(900, 600),
        background_color="#0b0d11", on_top=api.get_on_top(), text_select=True,
    )
    api.window = window
    if os.environ.get("DOTA_COACH_SELFTEST"):
        selftest(window, url)
    try:
        webview.start(private_mode=False)   # se termina cand inchizi fereastra
    except Exception as e:
        print(f"[app] Fereastra nativa n-a pornit ({e}) - deschid in browser")
        return browser_fallback(url)
    os._exit(0)  # inchide si serverul


def browser_fallback(url):
    import webbrowser
    webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
