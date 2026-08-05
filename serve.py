#!/usr/bin/env python3
"""
Local server for the Built-with-Kali portfolio dashboard.

It does two things:
  1. Serves the dashboard files (index.html, config.json, kali-avatar.png).
  2. Proxies live prices from Yahoo Finance at /api/prices so the browser
     never has to deal with CORS or rate-limit headaches. Python fetching
     Yahoo server-side is reliable and needs no API key.

Usage:
    python3 serve.py
then open http://localhost:8000 in your browser.

No third-party dependencies — Python 3 standard library only.
Your holdings live in config.json on your machine; only ticker symbols are
sent to Yahoo for pricing (never your share counts or cost basis).
"""
import http.server
import socketserver
import json
import os
import time
import urllib.request
import urllib.parse

PORT = int(os.environ.get("PORT", "8000"))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# simple in-memory price cache so rapid refreshes don't hammer Yahoo
_CACHE = {}                 # symbol -> (price, ts)
_CACHE_TTL = 20             # seconds

YHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def fetch_price(sym):
    """Return the latest price for one ticker, or None. Cached briefly."""
    now = time.time()
    hit = _CACHE.get(sym)
    if hit and now - hit[1] < _CACHE_TTL:
        return hit[0]
    url = YHOO.format(sym=urllib.parse.quote(sym))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.load(resp)
        meta = data["chart"]["result"][0]["meta"]
        px = meta.get("regularMarketPrice")
        if px is None:
            px = meta.get("previousClose")
        if isinstance(px, (int, float)):
            _CACHE[sym] = (float(px), now)
            return float(px)
    except Exception:
        pass
    # on failure, serve a stale cached value if we have one
    return hit[0] if hit else None


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/prices"):
            return self.handle_prices()
        return super().do_GET()

    def handle_prices(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        symbols = params.get("symbols", [""])[0]
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        prices = {}
        for s in syms:
            px = fetch_price(s)
            if px is not None:
                prices[s] = px
        body = json.dumps({"ok": True, "prices": prices}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass  # quiet


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("🐾 Built with Kali — portfolio dashboard")
        print(f"→ open  http://localhost:{PORT}")
        print("  (edit config.json, then refresh the page)")
        print("  live prices proxied via /api/prices — Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye 🐾")
