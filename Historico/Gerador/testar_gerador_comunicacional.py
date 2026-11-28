"""Testes locais do gerador candidato, sem rede nem chave da Groq."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import gerar_comunicacional as g


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


def fake_response(request, serial=0):
    props = request['response_format']['json_schema']['schema']['properties']['dias']['properties']
    obj = {'dias': {d: {m: f'Mensagem fictícia {serial} {d} {m}'
                     for m in v['required']} for d, v in props.items()},
           'estado_rotina': 'Estado fictício', 'descricao_escrita': 'Descrição fictícia'}
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(obj)}}],
            'usage': {'total_tokens': 2000}, 'system_fingerprint': 'fake'}


class Tests(unittest.TestCase):
    def test_plan_and_all_blocks(self):
        import gerar_piloto_comunicacional_v3 as v3
        plan = g.make_plan()
        old_plan = v3.make_plan()
        for new, old in zip(plan['profiles'], old_plan['profiles']):
            self.assertEqual({k:v for k,v in new.items() if k!='condition'}, {k:v for k,v in old.items() if k!='condition'})
        self.assertEqual(plan['parameters'], v3.PARAMS)
        for p in plan['profiles']:
            blocks = []
            for b in range(6):
                req = g.make_request(p,b,blocks[-1] if blocks else None,0,
                                     blocks[0]['descricao_escrita'] if blocks else None)
                old_profile = next(x for x in old_plan['profiles'] if x['id']==p['id'])
                old = v3.make_request(old_profile,b,blocks[-1] if blocks else None,0,
                                      blocks[0]['descricao_escrita'] if blocks else None)
                self.assertEqual(req['seed'], old['seed'])
                for k in g.PARAMS: self.assertEqual(req[k],old[k])
                self.assertEqual(req['response_format'],old['response_format'])
                if b<4 or p['condition']=='estavel':
                    self.assertEqual(req,old)
                else:
                    self.assertEqual(req['messages'][0]['content'].replace(g.INTERVENTIONS['alterada'],v3.INTERVENTIONS[old_profile['condition']]),old['messages'][0]['content'])
                days = p['days'][b*5:b*5+5]
                resp = fake_response(req,b)
                obj = g.parse_response(resp,days)
                self.assertEqual([len(d['mensagens']) for d in obj['dias']], [d['count'] for d in days])
                blocks.append(obj)
                if p['condition'] in g.INTERVENTIONS:
                    self.assertEqual(g.INTERVENTIONS[p['condition']] in req['messages'][0]['content'],b>=4)
            rows = g.export_profile(p,blocks)
            self.assertEqual(len(rows),200)
            self.assertEqual(len({r['messageId'] for r in rows}),200)

    def test_official_planning(self):
        from collections import Counter
        cal=g.make_plan('calibracao')['profiles']
        test=g.make_plan('teste', assignment_seed=12345)['profiles']
        self.assertEqual(len(cal),40)
        self.assertEqual(len(test),40)
        self.assertEqual(Counter(p['experimental_condition'] for p in test),dict.fromkeys('ABCD',10))
        self.assertTrue(all(p['condition']=='estavel' for p in cal))
        self.assertEqual(len({p['id'] for p in cal+test}),80)
        seeds=[]
        for p in cal+test:
            self.assertEqual(len(p['days']),30)
            self.assertEqual(sum(d['count'] for d in p['days']),200)
            self.assertTrue(all(4<=d['count']<=10 for d in p['days']))
            for b in range(6):
                prev={'estado_rotina':'rotina','descricao_escrita':'estilo'} if b else None
                req=g.make_request(p,b,prev,0,'estilo' if b else None)
                seeds.append(req['seed'])
                self.assertEqual(g.INTERVENTIONS['alterada'] in req['messages'][0]['content'],p['condition']=='alterada' and b>=4)
                if 'experimental_condition' in p:
                    alternate=dict(p,experimental_condition='X')
                    self.assertEqual(req,g.make_request(alternate,b,prev,0,'estilo' if b else None))
        self.assertEqual(len(set(seeds)),len(seeds))
        with self.assertRaises(ValueError): g.make_plan('teste')

    def test_official_generation_blocked(self):
        for base in ('calibracao','teste'):
            with patch.object(g,'BASE','piloto'), patch.object(sys,'argv',['test','--base',base]):
                with self.assertRaises(SystemExit): g.main()

    def test_invalid_outputs(self):
        p=g.make_plan()['profiles'][0]; req=g.make_request(p,0,None,0)
        for mode in ('missing','extra','empty','incomplete'):
            resp=fake_response(req); obj=json.loads(resp['choices'][0]['message']['content'])
            d=obj['dias']['dia_01']
            if mode=='missing': d.pop('msg_01')
            elif mode=='extra': d['msg_99']='extra'
            elif mode=='empty': d['msg_01']=' '
            else: resp['choices'][0]['finish_reason']='length'
            resp['choices'][0]['message']['content']=json.dumps(obj)
            with self.assertRaises(ValueError): g.parse_response(resp,p['days'][:5])

    def test_limiter(self):
        c=Clock(); r=g.RateLimiter(c,c.sleep)
        for _ in range(3):
            wait, est=r.wait_before(); self.assertEqual(wait,0)
            r.observe(c(),{}, {'total_tokens':2000},est)
        wait,_=r.wait_before(); self.assertGreaterEqual(wait,60)
        c=Clock(); r=g.RateLimiter(c,c.sleep)
        r.observe(0,{'x-ratelimit-remaining-tokens':'1000','x-ratelimit-reset-tokens':'7.66s'},{'total_tokens':2000})
        wait,_=r.wait_before(); self.assertAlmostEqual(wait,8.16)
        r.headers={'x-ratelimit-remaining-requests':'0','x-ratelimit-reset-requests':'2h'}
        r.header_time=c()
        with self.assertRaises(RuntimeError): r.wait_before()

    def test_retry(self):
        self.assertAlmostEqual(g.duration_seconds('2m59.56s'),179.56)
        self.assertEqual(g.duration_seconds('500ms'),.5)
        self.assertEqual(g.retry_delay({'retry-after':'2'},'TPM limit',1),3)
        self.assertIsNone(g.retry_delay({'retry-after':'2'},'TPD limit',1))
        self.assertIsNone(g.retry_delay({'retry-after':'300'},'limit',1))
        self.assertEqual(g.retry_delay({},'limit',1),16)

    def test_main_and_resume(self):
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
            return Raw(fake_response(req,len(calls)))
        client=types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(with_raw_response=types.SimpleNamespace(create=create))))
        sdk=types.SimpleNamespace(Groq=lambda **kw:client,APIStatusError=Status,APIConnectionError=ConnectionError)
        limiter=g.RateLimiter(clock,clock.sleep)
        with tempfile.TemporaryDirectory() as d, patch.object(g,'OUT',Path(d)), patch.dict(sys.modules,{'groq':sdk}), patch.object(g,'RateLimiter',lambda: limiter), patch.object(g.time,'sleep',clock.sleep), patch.object(g.time,'monotonic',clock), patch.object(g.importlib.metadata,'version',return_value='fake'), patch.object(sys,'argv',['test','--perfis','P03']):
            # O relógio virtual evita pausas reais.
            self.assertEqual(g.main(),0)
            self.assertEqual(len(calls),7)
            self.assertEqual(calls[0],calls[1])
            self.assertEqual(len(g.load(Path(d)/'P03'/'mensagens.json')),200)
            self.assertEqual(g.main(),0)
            self.assertEqual(len(calls),7)
            stats=g.load(Path(d)/'diagnostico_execucao.json')[0]
            self.assertEqual(stats['http_429'],1)
            self.assertEqual(stats['responses'],6)
            self.assertEqual(stats['total_tokens_reported'],12000)


if __name__=='__main__':
    unittest.main()
