"""
Welfog AI — run with:  python main.py
Opens the chat UI in your browser.
Accessible from other devices on the same Wi‑Fi/LAN.
"""

from __future__ import annotations

import socket
import threading
import time
import webbrowser

from app import app


# 0.0.0.0 = all network interfaces (localhost + LAN IP)
HOST = "0.0.0.0"
PORT = 5055


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_PC_IP"


def _open_browser(lan_ip: str):
    time.sleep(0.8)
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


def main():
    lan_ip = get_lan_ip()
    print(
        f"\n  Welfog AI running\n"
        f"  Chat UI      → http://127.0.0.1:{PORT}/\n"
        f"  Admin panel  → http://127.0.0.1:{PORT}/admin\n"
        f"  Other devices → http://{lan_ip}:{PORT}/\n"
        f"  Admin login: admin / admin123\n"
        f"  Press Ctrl+C to stop.\n"
    )
    threading.Thread(target=_open_browser, args=(lan_ip,), daemon=True).start()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
