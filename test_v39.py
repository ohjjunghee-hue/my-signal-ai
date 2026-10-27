import unittest,sqlite3,tempfile,os
import server
class SignalHistoryTests(unittest.TestCase):
 def test_transition_dedup(self):
  con=sqlite3.connect(':memory:')
  con.execute('CREATE TABLE setup_events(id INTEGER PRIMARY KEY AUTOINCREMENT,market TEXT,ts INTEGER,previous TEXT,new_status TEXT,price REAL,reason TEXT,UNIQUE(market,ts,new_status))')
  server.add_setup_event(con,'KRW-TEST',100,None,'PRE',10,'initial')
  server.add_setup_event(con,'KRW-TEST',100,None,'PRE',10,'initial')
  server.add_setup_event(con,'KRW-TEST',101,'PRE','PRE',11,'unchanged')
  server.add_setup_event(con,'KRW-TEST',102,'PRE','BUY',12,'breakout')
  events=server.read_setup_events(con)
  self.assertEqual(len(events),2)
  self.assertEqual(events[0]['new_status'],'BUY')
  self.assertEqual(events[1]['new_status'],'PRE')
 def test_filter_market(self):
  con=sqlite3.connect(':memory:')
  con.execute('CREATE TABLE setup_events(id INTEGER PRIMARY KEY AUTOINCREMENT,market TEXT,ts INTEGER,previous TEXT,new_status TEXT,price REAL,reason TEXT,UNIQUE(market,ts,new_status))')
  server.add_setup_event(con,'KRW-A',100,None,'PRE',10,'x')
  server.add_setup_event(con,'KRW-B',101,None,'PRE',20,'y')
  self.assertEqual([x['market'] for x in server.read_setup_events(con,market='KRW-A')],['KRW-A'])
if __name__=='__main__':unittest.main()
