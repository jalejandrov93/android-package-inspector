"""Console report rendering."""

from __future__ import annotations


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"


def _c(text: str, color: str, enable: bool) -> str:
    return f"{color}{text}{C.RESET}" if enable else text


def render_cli(data: dict, color: bool) -> None:
    apps = data["apps"]
    print(_c("\nAndroid Package Inspector", C.BOLD, color))
    print(_c("=" * 40, C.DIM, color))
    counts = data["counts"]
    print(f"{counts['total']} apps · {counts['user']} usuario · "
          f"{counts['system']} sistema · {counts['high_risk']} alto riesgo · "
          f"{counts['critical']} críticas\n")

    def section(title, items):
        print(_c(f"[+] {title} ({len(items)})", C.CYAN, color))
        if items:
            for it in items:
                print(f"    {it}")
        else:
            print("    Ninguna")
        print(_c("-" * 40, C.DIM, color))

    section("Apps con Overlay", [a["package"] for a in apps if a.get("overlay")])
    section("Apps con Accessibility", [a["package"] for a in apps if a.get("accessibility")])
    section("Apps con Boot Completed", [a["package"] for a in apps if a.get("boot_completed")])
    section("Installer desconocido",
            [a["package"] for a in apps
             if a.get("installer_label") == "Unknown" and a["type"] == "user"])

    print(_c("[+] Apps posiblemente peligrosas", C.YELLOW, color))
    for a in apps[:15]:
        stars = "★" * a.get("stars", 0) + "☆" * (5 - a.get("stars", 0))
        crit = _c(" 🔒CRITICAL", C.MAGENTA, color) if a.get("critical") else ""
        col = C.RED if a.get("stars", 0) >= 4 else C.RESET
        print(f"    {_c(stars, col, color)} {a['package']} "
              f"{_c('[' + a['type'] + ']', C.DIM, color)}{crit}")
    print(_c("-" * 40, C.DIM, color))
