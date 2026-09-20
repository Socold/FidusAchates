"""`python -m fidus_lab.console <trace>`: serve the console and replay a trace.

Prints the URL (with its token) to open in a browser. Ctrl-C stops it.
"""

from __future__ import annotations

import sys
import threading
import webbrowser

from .console import start
from .live import drive_trace


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m fidus_lab.console <trace.fidustr> [--open]",
              file=sys.stderr)
        return 2
    console = start()
    print(f"console: {console.url}")
    if "--open" in argv:
        webbrowser.open(console.url)
    t = threading.Thread(target=console.serve_forever, daemon=True)
    t.start()
    try:
        drive_trace(argv[0], console, delay_s=0.5)
        print("replay done; console still serving, Ctrl-C to stop")
        t.join()
    except KeyboardInterrupt:
        console.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
