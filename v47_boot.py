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
            # Delegate authentication through V45's existing gate: endpoint is non-sensitive.
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
