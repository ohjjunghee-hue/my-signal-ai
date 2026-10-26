import unittest,time,math
from server import analyze

def bars(unit=5,n=90,trend=.0003,spike=False):
    base=100.;now=int(time.time()//(unit*60))*(unit*60)-n*unit*60
    out=[]
    for i in range(n):
        c=base*(1+trend)**i
        if spike and i>=n-8:c*=1+(i-(n-8))*.018
        out.append({'t':now+i*unit*60,'o':c*.998,'h':c*1.004,'l':c*.994,'c':c,'v':100+(200 if i==n-1 else 0)})
    return out
class TestEngine(unittest.TestCase):
    def test_insufficient(self):self.assertEqual(analyze([],[],[],100)['status'],'DATA')
    def test_no_buy_without_evidence(self):
        a=bars();b=bars(15);c=bars(60)
        self.assertNotEqual(analyze(a,b,c,a[-1]['c'])['status'],'BUY')
    def test_spike_is_not_buy(self):
        a=bars(spike=True);b=bars(15);c=bars(60)
        r=analyze(a,b,c,a[-1]['c']);self.assertEqual(r['status'],'WAIT');self.assertIn('단기 급등 추격',r['risk'])
    def test_price_divergence(self):
        a=bars();b=bars(15);c=bars(60)
        r=analyze(a,b,c,a[-1]['c']*1.1);self.assertIn('현재가와 확정봉 가격 괴리',r['risk'])
    def test_determinism(self):
        a=bars();b=bars(15);c=bars(60)
        self.assertEqual(analyze(a,b,c,a[-1]['c']),analyze(a,b,c,a[-1]['c']))
if __name__=='__main__':unittest.main()
