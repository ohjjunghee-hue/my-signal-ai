import unittest
from server import opportunity_targets
class TestOpportunity(unittest.TestCase):
 def test_strong(self):
  x=opportunity_targets(1000,970,1.2,950,2.5,5,True,True,[],3,2)
  self.assertTrue(x['eligible']);self.assertEqual([v['pct'] for v in x['levels']],[10,20,50]);self.assertEqual([v['price'] for v in x['levels']],[1100,1200,1500])
 def test_weak_volume(self):
  self.assertFalse(opportunity_targets(1000,970,1.2,950,1.0,5,True,True,[],3,2)['eligible'])
 def test_bad_rr(self):
  self.assertFalse(opportunity_targets(1000,950,1.2,950,1.4,11,True,True,[],3,2)['eligible'])
 def test_near_resistance(self):
  self.assertFalse(opportunity_targets(1000,970,1.2,1010,2.5,5,True,True,[],3,2)['eligible'])
 def test_overheated(self):
  self.assertFalse(opportunity_targets(1000,970,1.2,950,2.5,5,True,True,['단기 급등 추격'],20,9)['eligible'])
if __name__=='__main__':unittest.main()
