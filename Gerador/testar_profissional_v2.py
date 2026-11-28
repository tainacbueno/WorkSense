import json, shutil, subprocess, tempfile, unittest
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
import preparar_experimento_v2 as p
import gerar_profissional_v2 as g
import validar_profissional_v2 as v
import avaliar_sinalizacoes_v2 as a
from avaliar_sinalizacoes import sha,load,save,threshold_calibration
from gerar_profissional_v1 import plan,render

HERE=Path(__file__).resolve().parent
# Fixture reproduz a interface V4, sem API nem planejamento oficial.
COMM='''import random,hashlib\nfrom pathlib import Path\ndef make_plan(base,assignment_seed):\n    labels=list('A'*10+'B'*10+'C'*10+'D'*10);random.Random(assignment_seed).shuffle(labels)\n    return {'base':base,'purpose':'teste_independente','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'private_assignment_seed':assignment_seed,'profiles':[{'id':f'TST{i:03}','experimental_condition':l,'condition':'alterada' if l in 'BD' else 'estavel'} for i,l in enumerate(labels,1)]}\n'''
def commrows(prefix):
    return [{'userId':f'{prefix}{i:03}','period':'baseline' if j<20 else 'reanalise','date':str(date(2026,5,4)+timedelta(days=7*(j//5)+j%5)),'score':70 if j<20 else 70-i%6,'evidenceCoverage':1} for i in range(1,41) for j in range(30)]

class Tests(unittest.TestCase):
    def test_allocation(self):
        ns={'__file__':str(HERE/'preparar_experimento_v2.py')};exec(COMM,ns);cp=ns['make_plan']('teste',3);m=p.allocation(cp,4);self.assertEqual(m,p.allocation(cp,4));a.truth_from_profiles(m)
        self.assertEqual({i:x['group'] for i,x in m.items()},p.labels_from_plan(cp));cp['profiles'][0]['condition']='invalid'
        with self.assertRaises(ValueError):p.allocation(cp,4)
    def test_full_pipeline(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=root/'Gerador';d.mkdir()
            for name in p.CORE:shutil.copyfile(HERE/name,d/name)
            comm=d/'com_fixture.py';comm.write_text(COMM,encoding='utf-8');method=root/'metodo_fixture.md';method.write_text('Fixture de teste')
            cal=root/'cal.json';save(cal,commrows('CAL'));lim=root/'limiar.json';save(lim,{'threshold':str(threshold_calibration(load(cal))),'source_sha256':sha(cal),'n':40,'k':2,'rule':'>'})
            def git(*args):return subprocess.check_output(['git','-C',t,*args],stderr=subprocess.PIPE)
            git('init','-q');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture');git('config','core.autocrlf','false');git('add','.');git('commit','-qm','Fixture');git('tag','fixture')
            with patch.object(p,'ROOT',root):
                with self.assertRaises(ValueError):p.freeze('fixture',comm,cal,lim,[method],False)
                f=root/'freeze.json';save(f,p.freeze('fixture',comm,cal,lim,[method],True));ns={'__file__':str(comm)};exec(COMM,ns);cp=root/'comm.json';save(cp,ns['make_plan']('teste',15));m=root/'manifesto.json';save(m,p.manifest(cp,f,123));out=root/'dados';g.generate(m,cp,f,out);val=root/'validado';v.validate(out,val,m,cp,f)
                self.assertEqual(len(load(val/'professional_period_scores.json')),80);self.assertEqual(len(load(out/'para_analise/trello_log.json')['cards']),480)
                manifest=load(m);expected=plan(123,[(i,x['professional_intensity']) for i,x in sorted(manifest['profiles'].items())]);self.assertEqual(load(out/'privado/plano.json')['cards'],expected)
                # Nenhuma substituição dos dados profissionais por scores artificiais.
                cs=root/'comscores_fixture.json';save(cs,commrows('TST'));ps=val/'professional_period_scores.json';paths=[root/'pc.json',root/'pp.json']
                for dim,src,dest in zip(a.DIMS,[cs,ps],paths):save(dest,a.prediction(src,dim,f))
                hs=[sha(x) for x in paths];labels=root/'labels.json'
                with self.assertRaises(ValueError):a.reveal(m,cp,f,paths,['0'*64,hs[1]])
                save(labels,a.reveal(m,cp,f,paths,hs));report=a.assess(labels,f,paths,hs);self.assertEqual(len(report['profiles']),40)
                for dim in a.DIMS:self.assertEqual(sum(report['dimensions'][dim]['matrix'].values()),40)
                with self.assertRaises(FileExistsError):g.generate(m,cp,f,out)
                log=out/'para_analise/trello_log.json';log.write_text('{}')
                with self.assertRaises(ValueError):v.validate(out,root/'invalid',m,cp,f)
                method.write_text('Alterado')
                with self.assertRaises(ValueError):p.verify_freeze(load(f))
    def test_threshold_boundary(self):
        from avaliar_sinalizacoes import predict
        rows=[{'userId':'X','period':period,'score':s,'evidenceCoverage':1} for period,s in [('baseline',90),('reanalise',83)]]
        self.assertTrue(predict(rows,'profissional',7)['X']['flag']);rows[-1]['score']=83.01;self.assertFalse(predict(rows,'profissional',7)['X']['flag'])
if __name__=='__main__':unittest.main(verbosity=2)
