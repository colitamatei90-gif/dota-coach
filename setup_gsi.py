"""Gaseste Dota 2 (Windows/Linux) si instaleaza automat config-ul Game State Integration."""
import os
import re
import sys

CFG_NAME = "gamestate_integration_coach.cfg"

CFG_TEMPLATE = """"Dota Coach"
{
    "uri"           "http://127.0.0.1:%d/gsi"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.5"
    "heartbeat"     "10.0"
    "data"
    {
        "provider"      "1"
        "map"           "1"
        "player"        "1"
        "hero"          "1"
        "abilities"     "1"
        "items"         "1"
    }
}
"""


def _steam_roots():
    roots = []
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                roots.append(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            pass
        roots += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    else:
        home = os.path.expanduser("~")
        roots += [os.path.join(home, ".steam", "steam"), os.path.join(home, ".local", "share", "Steam")]
    return [r for r in roots if os.path.isdir(r)]


def find_dota():
    for root in _steam_roots():
        libs = [root]
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            with open(vdf, encoding="utf-8", errors="ignore") as f:
                libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
        for lib in libs:
            game = os.path.join(lib, "steamapps", "common", "dota 2 beta", "game", "dota")
            if os.path.isdir(game):
                return game
    return None


def install(port):
    dota = find_dota()
    if not dota:
        print("[gsi] Nu am gasit Dota 2 automat - copiaza manual " + CFG_NAME +
              " in ...\\dota 2 beta\\game\\dota\\cfg\\gamestate_integration\\")
        return False
    folder = os.path.join(dota, "cfg", "gamestate_integration")
    path = os.path.join(folder, CFG_NAME)
    content = CFG_TEMPLATE % port
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if f.read() == content:
                    print(f"[gsi] Config-ul e deja instalat: {path}")
                    return True
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[gsi] Am instalat config-ul: {path}")
        print("[gsi] Nu uita: Steam -> Dota 2 -> Properties -> Launch Options: -gamestateintegration")
        print("[gsi] (Dota trebuie repornit daca era deschis)")
        return True
    except OSError as e:
        print(f"[gsi] Nu am putut scrie config-ul ({e}). Copiaza-l manual.")
        return False


if __name__ == "__main__":
    install(3000)
