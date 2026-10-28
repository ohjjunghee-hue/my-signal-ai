import tempfile, unittest
from pathlib import Path
from apply_fix import patch

class PatchTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
  (self.p/'index.html').write_text('<h1>V45 · OUTCOME VALIDATION</h1>',encoding='utf-8')
  (self.p/'server.py').write_text("import os\nTOP=max(5,min(160,int(os.getenv('DEEP_MARKETS','80'))))\n",encoding='utf-8')
 def tearDown(self):self.t.cleanup()
 def test_apply(self):
  patch(self.p)
  self.assertIn('V48 · INTEGRATED',(self.p/'index.html').read_text())
  self.assertIn('min(500,',(self.p/'server.py').read_text())
 def test_backup(self):
  patch(self.p)
  self.assertTrue((self.p/'server.py.pre_v48_fix.bak').exists())
  self.assertTrue((self.p/'index.html.pre_v48_fix.bak').exists())
 def test_idempotence_guard(self):
  patch(self.p)
  with self.assertRaises(RuntimeError):patch(self.p)
 def test_no_partial_changes(self):
  (self.p/'server.py').write_text('unexpected source',encoding='utf-8')
  with self.assertRaises(RuntimeError):patch(self.p)
  self.assertIn('V45',(self.p/'index.html').read_text())

if __name__=='__main__':unittest.main()
