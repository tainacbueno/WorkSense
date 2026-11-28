import unittest,copy,json
from gerar_profissional_v1 import plan,render
from validar_profissional_v1 import check
from avaliar_sinalizacoes import predict,evaluate,wilson,threshold_calibration
from decimal import Decimal
class Tests(unittest.TestCase):
    def test_reproducible(self):
        p=[('P1','estavel'),('P2','leve'),('P3','acentuada')];a=plan(17,p);self.assertEqual(a,plan(17,p));self.assertEqual(render(a),render(plan(17,p)))
    def test_reference_independence(self):
        a=plan(17,[('P1','estavel')]);b=plan(17,[('P1','acentuada')]);self.assertEqual(a[:6],b[:6])
    def test_multiple_seeds(self):
        for s in range(10):
            p=[('P1','estavel'),('P2','leve'),('P3','acentuada')];rows=plan(s,p);_,_,scores=check(render(rows),{'seed':s,'profiles':dict(p),'cards':rows});self.assertEqual(len(scores),6);self.assertTrue(all(x['evidenceCoverage']==1 for x in scores))
    def test_adulteration(self):
        p=[('P1','estavel')];r=plan(3,p);b=render(r);b['actions'].pop()
        with self.assertRaises(ValueError):check(b,{'seed':3,'profiles':dict(p),'cards':r})
    def test_threshold_and_stats(self):
        rows=[{'userId':i,'period':p,'score':s,'evidenceCoverage':1} for i,b,c in [('X',90,83),('Y',90,84),('Z',90,92),('W',90,81)] for p,s in [('baseline',b),('reanalise',c)]]
        pred=predict(rows,'profissional',7);self.assertTrue(pred['X']['flag']);self.assertFalse(pred['Y']['flag']);self.assertFalse(pred['Z']['flag'])
        truth={i:{'altered':i in ('X','Y'),'intensity':'leve' if i in ('X','Y') else None} for i in pred};r=evaluate(pred,truth);self.assertEqual(r['matrix'],{'TP':1,'FN':1,'FP':1,'TN':1});self.assertAlmostEqual(wilson(20,20)['ci95'][0],.83887484)
        with self.assertRaises(ValueError):predict(rows[:-1],'profissional',7)
    def test_calibration_strict(self):
        from datetime import date,timedelta
        days=[date(2026,5,4)+timedelta(days=i) for i in range(40) if (date(2026,5,4)+timedelta(days=i)).weekday()<5];days=days[:20]+[date(2026,6,1)+timedelta(days=i) for i in range(12) if (date(2026,6,1)+timedelta(days=i)).weekday()<5]
        rows=[{'userId':f'CAL{i:03}','period':'baseline' if j<20 else 'reanalise','date':str(d),'score':70 if j<20 else 70-(5 if i in (1,2) else 1),'evidenceCoverage':1} for i in range(1,41) for j,d in enumerate(days)]
        self.assertEqual(threshold_calibration(rows),Decimal(5));self.assertFalse(predict(rows,'comunicacional',5)['CAL001']['flag'])
if __name__=='__main__':unittest.main(verbosity=2)
