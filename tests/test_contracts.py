from datetime import datetime, timezone, timedelta
import unittest
from trading_lab.contracts import *


class ContractTests(unittest.TestCase):
    def setUp(self): self.t=datetime(2026,1,1,tzinfo=timezone.utc)
    def assessment(self,side=Side.BUY,ev=.3,**kw):
        return Assessment(kw.get('name','S01'),side,kw.get('generated',self.t),kw.get('expires',self.t+timedelta(minutes=15)),ev)
    def choose(self,rows,**kw): return decide(rows,self.t,data_healthy=kw.get('healthy',True),risk_allowed=kw.get('risk',True),position_open=kw.get('open',False))
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError): aware(datetime(2026,1,1))
    def test_future_data_not_available(self):
        a=Observation('CPI',2.,self.t,self.t+timedelta(seconds=10),'official','v1'); self.assertEqual(known_at([a],self.t),[])
    def test_future_mutation_invariant(self):
        a=Observation('CPI',2.,self.t,self.t,'official','v1'); b=Observation('CPI',99.,self.t,self.t+timedelta(seconds=10),'official','v2'); self.assertEqual(known_at([a],self.t),known_at([a,b],self.t))
    def test_crossed_quote_rejected(self):
        with self.assertRaises(ValueError): Quote(self.t,self.t,201.,200.)
    def test_negative_price_rejected(self):
        with self.assertRaises(ValueError): Quote(self.t,self.t,-1.,2.)
    def test_nan_price_rejected(self):
        with self.assertRaises(ValueError): Quote(self.t,self.t,float('nan'),2.)
    def test_unknown_ev_no_fabrication(self): self.assertEqual(self.choose([self.assessment(ev=None)]).side,Side.PASS)
    def test_risk_can_veto(self): self.assertEqual(self.choose([self.assessment()],risk=False).reason,'RISK_BLOCK')
    def test_existing_position_blocks_entry(self): self.assertEqual(self.choose([self.assessment()],open=True).reason,'POSITION_OPEN')
    def test_data_health_blocks(self): self.assertEqual(self.choose([self.assessment()],healthy=False).reason,'DATA_UNAVAILABLE')
    def test_expiry_exclusive(self): self.assertEqual(self.choose([self.assessment(generated=self.t-timedelta(minutes=15),expires=self.t)]).side,Side.PASS)
    def test_future_proposal_rejected(self): self.assertEqual(self.choose([self.assessment(generated=self.t+timedelta(seconds=1))]).side,Side.PASS)
    def test_conflict_pass(self): self.assertEqual(self.choose([self.assessment(ev=.3),self.assessment(side=Side.SELL,ev=.28,name='S02')]).reason,'DIRECTION_CONFLICT')
    def test_valid_choice(self): self.assertEqual(self.choose([self.assessment()]).side,Side.BUY)
    def test_model_score_not_probability(self): self.assertEqual(self.choose([self.assessment(ev=1.2)]).side,Side.BUY)
    def test_no_live_order_function(self):
        import trading_lab.contracts as c
        self.assertFalse(hasattr(c,'order_send'))
