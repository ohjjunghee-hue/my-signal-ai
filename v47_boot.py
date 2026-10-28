"""V47 persistence add-on, keeping V46 dashboard and V45 scanner unchanged."""
import http.server
import json
import threading
from urllib.parse import urlparse
import server
import v46_boot
import v47_storage as storage

class Handler(v46_boot.Handler):
    def do_GET(self):
        if urlparse(self.path).path == '/api/storage-health':
            # Protect storage status with the same token/cookie as other APIs.
            if server.ACCESS_TOKEN:
                import http.cookies, hmac
                from urllib.parse import parse_qs
                cookie=http.cookies.SimpleCookie()
                try: cookie.load(self.headers.get('Cookie',''))
                except Exception: pass
                supplied=parse_qs(urlparse(self.path).query).get('token',[''])[0]
                stored=cookie.get('ms_token')
                valid=hmac.compare_digest(supplied,server.ACCESS_TOKEN) or (stored is not None and hmac.compare_digest(stored.value,server.ACCESS_TOKEN))
                if not valid:
                    self.send_response(401)
                    self.send_header('Content-Length','0')
                    self.end_headers()
                    return
            payload=json.dumps(storage.status(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers();self.wfile.write(payload)
            return
        return super().do_GET()

if __name__ == '__main__':
    storage.restore(server.DB)
    server.db_init()
    for fn in (server.loop, server.midnight_loop, server.pulse_loop):
        threading.Thread(target=fn, daemon=True).start()
    threading.Thread(target=storage.run, args=(server.DB,30), daemon=True).start()
    print('V47 storage mode:', 'PostgreSQL snapshots' if storage.enabled() else 'EPHEMERAL: configure DATABASE_URL',flush=True)
    http.server.ThreadingHTTPServer(('0.0.0.0',server.PORT),Handler).serve_forever()
