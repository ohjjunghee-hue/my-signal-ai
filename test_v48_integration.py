import contextlib,http.client,http.server,json,os,pathlib,socket,sqlite3,tempfile,threading,time,unittest
from unittest.mock import patch
import server,v47_boot,v47_storage as storage,outcome_validation as ov

class V48Integration(unittest.TestCase):
    def test_database_migrations_idempotent_and_preserve_records(self):
        with tempfile.TemporaryDirectory() as t:
            db=pathlib.Path(t)/'db.sqlite'
            with patch.object(server,'DB',db):
                server.db_init()
                with sqlite3.connect(db) as c:
                    c.execute("INSERT INTO snapshots(ts,market,status,score,entry,stop,features,reason) VALUES(?,?,?,?,?,?,?,?)",(1,'KRW-TEST','BUY',80,100,95,'{}','test'))
                server.db_init()
                with sqlite3.connect(db) as c:
                    self.assertEqual(c.execute("SELECT count(*) FROM snapshots").fetchone()[0],1)
                    self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0],'ok')
    def test_forward_signal_not_same_scan_hit(self):
        with sqlite3.connect(':memory:') as c:
            ov.init(c)
            r={'market':'KRW-TEST','status':'BUY','price':100,'stop':95,'score':70}
            ov.record(c,[r],1000)
            ov.observe(c,[{'market':'KRW-TEST','trade_price':150}],1000)
            self.assertEqual(c.execute('SELECT count(*) FROM trial_events').fetchone()[0],0)
            ov.observe(c,[{'market':'KRW-TEST','trade_price':150}],1060)
            self.assertEqual(c.execute("SELECT count(*) FROM trial_events WHERE kind='TP50'").fetchone()[0],1)
    def test_legacy_watch_separate_from_verified_trials(self):
        with sqlite3.connect(':memory:') as c:
            c.execute('CREATE TABLE signal_outcomes(id INTEGER PRIMARY KEY,market TEXT,day TEXT,first_seen INTEGER,last_seen INTEGER,entry REAL,last_price REAL,max_pct REAL,min_pct REAL,status TEXT,signal_type TEXT,first_change24 REAL,first_score INTEGER,first_source TEXT,first_class TEXT,observations INTEGER,UNIQUE(market,day))')
            ov.init(c)
            r={'market':'KRW-TEST','status':'WATCH','entry':100,'price':100,'change24':0,'score':60}
            server.record_outcomes(c,[r],1000)
            ov.record(c,[r],1000)
            self.assertEqual(c.execute('SELECT count(*) FROM signal_outcomes').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM signal_trials').fetchone()[0],0)
    def test_storage_disabled_does_not_claim_persistence(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(storage.enabled())
            self.assertFalse(storage.save('/does/not/exist'))
            self.assertEqual(storage.status()['mode'],'not_configured')
    def test_http_auth_for_storage_health(self):
        with patch.object(server,'ACCESS_TOKEN','secret'):
            httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),v47_boot.Handler)
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            try:
                port=httpd.server_address[1]
                def request(path,headers=None):
                    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
                    try:
                        conn.request('GET',path,headers=headers or {})
                        resp=conn.getresponse()
                        return resp.status,resp.read()
                    finally:conn.close()
                self.assertEqual(request('/api/storage-health')[0],401)
                self.assertEqual(request('/api/storage-health',{'Cookie':'ms_token=wrong'})[0],401)
                code,payload=request('/api/storage-health',{'Cookie':'ms_token=secret'})
                self.assertEqual(code,200)
                self.assertIn('configured',json.loads(payload))
                self.assertEqual(request('/health')[0],200)
            finally:
                httpd.shutdown();httpd.server_close();thread.join(3)
if __name__=='__main__':unittest.main()
