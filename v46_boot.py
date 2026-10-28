import http.server,threading,server
from urllib.parse import urlparse,parse_qs
class Handler(server.Handler):
 def do_GET(self):
  if urlparse(self.path).path=="/validation-dashboard":
   if server.ACCESS_TOKEN:
    import http.cookies,hmac
    c=http.cookies.SimpleCookie()
    try:c.load(self.headers.get("Cookie",""))
    except Exception:pass
    token=parse_qs(urlparse(self.path).query).get("token",[""])[0]
    cookie=c.get("ms_token")
    if not (hmac.compare_digest(token,server.ACCESS_TOKEN) or (cookie is not None and hmac.compare_digest(cookie.value,server.ACCESS_TOKEN))):
     self.send_response(401);self.end_headers();return
   data=(server.ROOT/"v46_dashboard.html").read_bytes()
   self.send_response(200)
   for k,v in [("Content-Type","text/html; charset=utf-8"),("Cache-Control","no-store"),("X-Content-Type-Options","nosniff"),("Content-Length",str(len(data)))]:self.send_header(k,v)
   self.end_headers();self.wfile.write(data);return
  super().do_GET()
if __name__=="__main__":
 server.db_init()
 for f in (server.loop,server.midnight_loop,server.pulse_loop):threading.Thread(target=f,daemon=True).start()
 http.server.ThreadingHTTPServer(("0.0.0.0",server.PORT),Handler).serve_forever()
