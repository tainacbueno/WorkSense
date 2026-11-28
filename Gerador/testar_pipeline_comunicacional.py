"""Testes sem rede; nenhum resultado experimental produzido.
--comparar permite verificar a equivalência real no ambiente que possui os modelos.
"""
import argparse, contextlib, io, json, os, shutil, subprocess, sys, tempfile, unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import gerar_comunicacional_estilo_v4 as g
import gerar_comunicacional_definitivo as official
import controle_comunicacional as c
import preparar_experimento_v2 as integrated
import validar_base_comunicacional_definitiva as validator
from preprocessar_comunicacional import validate_messages
from calcular_score_comunicacional import calculate
from avaliar_sinalizacoes import load,save,sha,threshold_calibration
from testar_gerador_estilo_v4 import Clock, fake_response
HERE=Path(__file__).resolve().parent

class Tests(unittest.TestCase):
    def test_plan_and_message_integrity(self):
        for base in ('calibracao','teste'):
            plan=g.make_plan(base,1234 if base=='teste' else None)
            self.assertEqual({x['id'] for x in plan['profiles']},c.expected_ids(base))
            rows=[]
            for p in plan['profiles']:
                blocks=[]
                for b in range(6):
                    req=g.make_request(p,b,blocks[-1] if blocks else None,0,blocks[0]['descricao_escrita'] if blocks else None)
                    blocks.append(g.parse_response(fake_response(req,len(rows)+b),p['days'][b*5:b*5+5]))
                rows.extend(g.export_profile(p,blocks))
            self.assertEqual(len(validate_messages(rows,base)),8000)
            with self.assertRaises(ValueError):validate_messages(rows[:-1],base)
            bad=[dict(r) for r in rows];bad[0]['condition']='estavel'
            with self.assertRaises(ValueError):validate_messages(bad,base)
    def test_score_rejects_incomplete(self):
        with self.assertRaises(ValueError):calculate({k:{} for k in ('basicLinguistic','sentimentAnalysis','semanticShift','lexicalDiversityByPeriod')},'calibracao')
    def test_official_end_to_end_no_api(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=root/'Gerador';d.mkdir();(root/'docs').mkdir()
            for name in set(c.CORE+integrated.CORE):shutil.copyfile(HERE/name,d/name)
            (root/c.PROTOCOL).write_text('Protocolo fictício, apenas teste',encoding='utf-8')
            review=root/'revisao.md';review.write_text('Registro fictício',encoding='utf-8');env=root/'ambiente.json';save(env,{'fixture':True,'model_identity':{'fixture':True}})
            def git(*args):return subprocess.check_output(['git','-C',t,*args],stderr=subprocess.PIPE)
            git('init','-q');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture');git('config','core.autocrlf','false');git('add','.');git('commit','-qm','Fixture');git('tag','cal')
            calls=[];clock=Clock();limiter=g.RateLimiter(clock,clock.sleep)
            def fake(key,req):calls.append(req);return {},fake_response(req,len(calls))
            def execute(base,freeze,output,extra=()):
                argv=['test','--base',base,'--congelamento',str(freeze),'--saida',str(output),*extra]
                with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):return official.main()
            with patch.object(c,'ROOT',root),patch.object(integrated,'ROOT',root),patch.object(c,'environment',lambda:{'fixture':True}),patch.dict(os.environ,{'CEREBRAS_API_KEY':'fake'}),patch.object(official,'call_api',fake),patch.object(official,'RateLimiter',lambda:limiter),patch.object(official.time,'sleep',clock.sleep),patch.object(official.time,'monotonic',clock):
                calfreeze=root/'congelamento_calibracao.json'
                with self.assertRaises(ValueError):c.freeze_calibration('cal',review,env,[],False)
                save(calfreeze,c.freeze_calibration('cal',review,env,[],True));self.assertEqual(c.authorize('calibracao',calfreeze)['stage'],'calibracao')
                with self.assertRaises((ValueError,KeyError)):c.authorize('teste',calfreeze)
                calout=root/'cal_privado';self.assertEqual(execute('calibracao',calfreeze,calout,('--planejar',)),0);self.assertEqual(len(calls),0)
                self.assertEqual(execute('calibracao',calfreeze,calout),0);self.assertEqual(len(calls),240)
                self.assertEqual(execute('calibracao',calfreeze,calout),0);self.assertEqual(len(calls),240)
                val=root/'cal_validado';receipt=validator.validate('calibracao',calout,val,calfreeze)
                self.assertEqual(receipt['messages'],8000);validate_messages(load(val/'para_analise/mensagens.json'),'calibracao')
                # Scores fictícios exclusivos da fixture: PLN real é testado separadamente.
                cal=root/'cal_scores.json';save(cal,[{'userId':f'CAL{i:03}','date':day,'period':'baseline' if j<20 else 'reanalise','score':70 if j<20 else 70-i%6,'evidenceCoverage':1} for i in range(1,41) for j,day in enumerate(c.DAYS)])
                lim=root/'limiar.json';save(lim,{'threshold':str(threshold_calibration(load(cal))),'source_sha256':sha(cal),'n':40,'k':2,'rule':'>'})
                # Evita adicionar as respostas fictícias ao repositório de teste.
                ind=root/'indicadores_fixture.json';save(ind,{'fixture':True});msg=val/'para_analise/mensagens.json'
                pln=root/'execucao_pln.json';save(pln,{'base':'calibracao','output_sha256':sha(ind),'input_sha256':sha(msg),'freeze_sha256':sha(calfreeze),'declared_review_fixed':True,'environment':load(env)})
                score_record=root/'cal_scores_execucao.json';save(score_record,{'base':'calibracao','scores_sha256':sha(cal),'score_count':1200,'freeze_sha256':sha(calfreeze),'indicators_sha256':sha(ind),'pln_record_sha256':sha(pln)})
                git('add',calfreeze.name,cal.name,lim.name,ind.name,pln.name,score_record.name,str(msg.relative_to(root)));git('commit','-qm','Fixture cal');git('tag','final')
                final=root/'final.json';files=[root/k for k in load(calfreeze)['files']]+[calfreeze,ind,msg,pln,score_record]
                save(final,integrated.freeze('final',root/c.GENERATOR,cal,lim,files,True));c.authorize('teste',final)
                testout=root/'test_privado';self.assertEqual(execute('teste',final,testout,('--seed-atribuicao','12345')),0);self.assertEqual(len(calls),480)
                testval=root/'test_validado';validator.validate('teste',testout,testval,final);validate_messages(load(testval/'para_analise/mensagens.json'),'teste')
                p=testout/'plano_privado.json';manifest=integrated.manifest(p,final,67890);self.assertEqual(Counter(x['group'] for x in manifest['profiles'].values()),dict.fromkeys('ABCD',10))
                with self.assertRaises(ValueError):execute('teste',final,testout,('--seed-atribuicao','54321'))
                review.write_text('Alterado',encoding='utf-8')
                with self.assertRaises(ValueError):c.authorize('teste',final)


def compare(new,old):
    expected=load(HERE/'referencia_pipeline_v4/chat_scores.json')
    original=load(old);current=load(new)
    old_scores=calculate(original,'piloto');new_scores=calculate(current,'piloto')
    print('Scores dos indicadores anteriores iguais à referência:',old_scores==expected)
    print('Indicadores novos iguais aos anteriores:',current==original)
    print('Scores novos iguais à referência:',new_scores==expected)
    if current!=original:
        for k in original:
            if current.get(k)!=original[k]:print('Diferença em:',k)
    if old_scores!=expected or current!=original or new_scores!=expected:raise SystemExit('Equivalência integral não demonstrada. Investigar antes do congelamento.')
    print('Equivalência integral confirmada: 120 scores e indicadores.')

if __name__=='__main__':
    if '--comparar' in sys.argv:
        p=argparse.ArgumentParser();p.add_argument('--comparar',type=Path,required=True);p.add_argument('--referencia-indicadores',type=Path,required=True);a=p.parse_args();compare(a.comparar,a.referencia_indicadores)
    else:unittest.main(verbosity=2)
