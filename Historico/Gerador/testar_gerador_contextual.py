"""Testes sem rede, usando respostas fictícias. Não produzem base experimental."""
import json
import sys
import tempfile
import types
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import gerar_comunicacional_contextual as g
import validar_base_comunicacional as v

class Clock:
    def __init__(self): self.now=0.
    def __call__(self): return self.now
    def sleep(self,s): self.now+=s

def fake_response(req, serial=0):
    props=req['response_format']['json_schema']['schema']['properties']['dias']['properties']
    obj=dict(dias={d:{m:f'Mensagem fictícia {serial} {d} {m}' for m in spec['required']} for d,spec in props.items()},estado_rotina=f'Estado fictício {serial}',descricao_escrita=f'Estilo fictício {serial}')
    return dict(choices=[dict(finish_reason='stop',message=dict(content=json.dumps(obj)))],model=g.MODEL,usage=dict(total_tokens=2000),system_fingerprint='fake')

class Tests(unittest.TestCase):
    def test_plan(self):
        cal=g.make_plan('calibracao'); test=g.make_plan('teste',12345)
        self.assertEqual(Counter(p['experimental_condition'] for p in test['profiles']),dict.fromkeys('ABCD',10))
        self.assertTrue(all(p['condition']=='estavel' for p in cal['profiles']))
        seeds=[]
        for plan in (cal,test):
            self.assertEqual(len(plan['profiles']),40)
            self.assertEqual(len(plan['review_plan']['full_profiles']),4)
            for p in plan['profiles']:
                self.assertEqual(sum(d['count'] for d in p['days']),200)
                self.assertEqual(len(p['days']),30)
                self.assertTrue(all(4<=d['count']<=10 and len(set(d['times']))==d['count'] for d in p['days']))
                sample=plan['review_plan']['profiles'][p['id']]
                self.assertEqual(len(sample['dates']),30 if sample['full'] else 8)
                self.assertEqual(sample['message_count'],sum(d['count'] for d in p['days'] if d['date'] in sample['dates']))
                for b in range(6):
                    self.assertEqual(len({o['situation'] for o in p['opportunities'][b]['slots']}),3)
                    self.assertEqual([(o['day'],o['message_position']) for o in p['opportunities'][b]['slots']],list(g.OPPORTUNITY_POSITIONS))
                    prev=dict(estado_rotina='rotina anterior',descricao_escrita='estilo anterior') if b else None
                    for i in range(g.MAX_INVALID):
                        req=g.make_request(p,b,prev,i,'estilo inicial' if b else None)
                        seeds.append(req['seed']); prompt=req['messages'][0]['content']
                        self.assertIn(g.COMMON,prompt)
                        self.assertEqual(g.INTERVENTIONS['alterada'] in prompt,p['condition']=='alterada' and b>=4)
                        for o in p['opportunities'][b]['slots']:
                            self.assertIn(f"Dia {o['day']}, mensagem {o['message_position']}: {o['situation']}",prompt)
                        self.assertEqual(req,g.make_request(dict(p,experimental_condition='X'),b,prev,i,'estilo inicial' if b else None))
            self.assertEqual(plan['review_plan']['message_count'],sum(p['message_count'] for p in plan['review_plan']['profiles'].values()))
        self.assertEqual(len(set(seeds)),len(seeds))
        # Mudar a atribuição privada não altera horários, oportunidades, contexto ou amostra.
        other=g.make_plan('teste',54321)
        self.assertEqual(test['review_plan'],other['review_plan'])
        for p,q in zip(test['profiles'],other['profiles']):
            self.assertEqual({k:v for k,v in p.items() if k not in ('condition','experimental_condition')},{k:v for k,v in q.items() if k not in ('condition','experimental_condition')})

    def test_official_blocked(self):
        for base in ('calibracao','teste'):
            with patch.object(g,'BASE','piloto'),patch.object(sys,'argv',['test','--base',base]):
                with self.assertRaises(SystemExit): g.main()

    def test_schema(self):
        p=g.make_plan('piloto')['profiles'][0]; req=g.make_request(p,0,None,0)
        for mode in ('missing','extra','empty','incomplete'):
            response=fake_response(req); obj=json.loads(response['choices'][0]['message']['content']); day=obj['dias']['dia_01']
            if mode=='missing': day.pop('msg_01')
            if mode=='extra': day['msg_99']='extra'
            if mode=='empty': day['msg_01']=' '
            if mode=='incomplete': response['choices'][0]['finish_reason']='length'
            response['choices'][0]['message']['content']=json.dumps(obj)
            with self.assertRaises(ValueError): g.parse_response(response,p['days'][:5])

    def test_rate_limit(self):
        c=Clock(); limiter=g.RateLimiter(c,c.sleep)
        for _ in range(3):
            wait,estimate=limiter.wait_before(); self.assertEqual(wait,0); limiter.observe(c(),{},dict(total_tokens=2000),estimate)
        self.assertGreaterEqual(limiter.wait_before()[0],60)
        self.assertIsNone(g.retry_delay({'retry-after':'2'},'TPD limit',1))
        self.assertEqual(g.retry_delay({'retry-after':'2'},'TPM limit',1),3)

    def test_pipeline_resume_and_validation(self):
        calls=[]; clock=Clock()
        class Status(Exception):
            status_code=429
            response=types.SimpleNamespace(headers={'retry-after':'1'},text='TPM limit')
        class Raw:
            headers={}
            def __init__(self,r): self.r=r
            def parse(self): return types.SimpleNamespace(model_dump=lambda **kw:self.r)
        def create(**req):
            calls.append(req)
            if len(calls)==1: raise Status()
            r=fake_response(req,len(calls))
            obj=json.loads(r['choices'][0]['message']['content']); obj['dias']['dia_01']['msg_01']='Mensagem recorrente fictícia'; r['choices'][0]['message']['content']=json.dumps(obj)
            if len(calls)==2: r['choices'][0]['finish_reason']='length'
            return Raw(r)
        client=types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(with_raw_response=types.SimpleNamespace(create=create))))
        sdk=types.SimpleNamespace(Groq=lambda **kw:client,APIStatusError=Status,APIConnectionError=ConnectionError)
        limiter=g.RateLimiter(clock,clock.sleep)
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'privado'; output=Path(d)/'validado'
            with patch.object(g,'OUT',source),patch.dict(sys.modules,{'groq':sdk}),patch.object(g,'RateLimiter',lambda:limiter),patch.object(g.time,'sleep',clock.sleep),patch.object(g.time,'monotonic',clock),patch.object(g.importlib.metadata,'version',return_value='fake'),patch.object(sys,'argv',['test']):
                self.assertEqual(g.main(),0); self.assertEqual(len(calls),14)
                self.assertEqual(calls[0],calls[1]); self.assertNotEqual(calls[1]['seed'],calls[2]['seed'])
                self.assertEqual(g.main(),0); self.assertEqual(len(calls),14)
            report=v.write_outputs(source,output)
            self.assertTrue(report['valid']); self.assertEqual(report['messages'],400); self.assertEqual(report['attempts'],14)
            self.assertEqual(report['actual_review_messages'],400)
            self.assertEqual(len(report['duplicates']),1); self.assertEqual(len(report['duplicates'][0]['occurrences']),12)
            self.assertEqual(len(g.load(output/'para_analise'/'mensagens.json')),400)
            for f in (output/'para_revisao').glob('*.json'):
                self.assertEqual(set(g.load(f)),{'userId','dates','messages','review_alert_message_ids'})
            with self.assertRaises(ValueError): v.write_outputs(source,output)
            # Simular corrupção em exportação, pedido e tentativa após aceite.
            path=source/'P05'/'mensagens.json'; original=g.load(path); modified=[dict(r) for r in original]; modified[0]['text']='adulterado'; g.dump(path,modified)
            with self.assertRaises(ValueError): v.validate(source)
            with self.assertRaises(ValueError): v.write_outputs(source,Path(d)/'falha')
            self.assertFalse((Path(d)/'falha'/'para_analise').exists()); g.dump(path,original)
            attempt=source/'P05'/'bloco_01'/'tentativa_0003.json'; original=g.load(attempt); altered=json.loads(json.dumps(original)); altered['request']['seed']+=1; g.dump(attempt,altered)
            with self.assertRaises(ValueError): v.validate(source)
            g.dump(attempt,original); altered=json.loads(json.dumps(original)); altered['response']['model']='outro-modelo'; g.dump(attempt,altered)
            with self.assertRaises(ValueError): v.validate(source)
            g.dump(attempt,original); extra=attempt.with_name('tentativa_0004.json'); g.dump(extra,original)
            with self.assertRaises(ValueError): v.validate(source)
            extra.unlink(); self.assertTrue(v.validate(source)[3]['valid'])

if __name__=='__main__': unittest.main(verbosity=2)
