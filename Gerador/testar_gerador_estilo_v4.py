"""Testes sem rede, usando respostas fictícias. Não produzem base experimental."""
import json
import os
import sys
import tempfile
import types
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import gerar_comunicacional_estilo_v4 as g
import validar_base_estilo_v4 as v

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

    def test_individual_style(self):
        pilot = g.make_plan('piloto')['profiles']
        self.assertEqual(len(pilot),4)
        self.assertEqual({p['context'] for p in pilot},{'tecnico'})
        self.assertEqual(pilot[0]['individual_style'],pilot[1]['individual_style'])
        self.assertEqual(pilot[2]['individual_style'],pilot[3]['individual_style'])
        self.assertNotEqual(pilot[0]['individual_style'],pilot[2]['individual_style'])
        for p in pilot:
            for b in range(6):
                prev = dict(estado_rotina='rotina fixa',descricao_escrita='MARCADOR_DIAGNOSTICO') if b else None
                req = g.make_request(p,b,prev,0,'MARCADOR_DIAGNOSTICO')
                prompt=req['messages'][0]['content']
                for description in p['individual_style']['characteristics'].values():
                    self.assertIn(description,prompt)
                self.assertNotIn('MARCADOR_DIAGNOSTICO',prompt)
                self.assertEqual(g.STABILITY in prompt, b<4 or p['condition']=='estavel')
                other=dict(p,condition='estavel' if p['condition']=='alterada' else 'alterada')
                if b<4:
                    self.assertEqual(req,g.make_request(other,b,prev,0,'OUTRO'))
        for base in ('calibracao','teste'):
            plan=g.make_plan(base,12345 if base=='teste' else None)
            self.assertGreater(len({tuple(p['individual_style']['indices']) for p in plan['profiles']}),1)
            for p in plan['profiles']:
                self.assertEqual(p['individual_style'],g.individual_style(p['id'],base))
        self.assertEqual(g.make_plan('piloto'),json.loads(json.dumps(g.make_plan('piloto'))))

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
        for _ in range(5):
            wait,estimate=limiter.wait_before(); self.assertEqual(wait,0); limiter.observe(c(),{},dict(total_tokens=2000),estimate)
        self.assertGreaterEqual(limiter.wait_before()[0],60)
        self.assertIsNone(g.retry_delay({'retry-after':'2'},'TPD limit',1))
        self.assertEqual(g.retry_delay({'retry-after':'2'},'TPM limit',1),3)

    def test_cerebras_headers(self):
        c=Clock(); limiter=g.RateLimiter(c,c.sleep)
        limiter.observe(c(), {'x-ratelimit-remaining-requests-minute':'0', 'x-ratelimit-remaining-tokens-day':'999000'}, {'total_tokens':3149}, 5000)
        self.assertGreaterEqual(limiter.wait_before()[0],60)
        limiter.headers={'x-ratelimit-remaining-tokens-day':'2000'}
        with self.assertRaises(RuntimeError): limiter.wait_before()
        self.assertIsNone(g.retry_delay({'x-ratelimit-remaining-requests-day':'0'}, 'rate limit', 1))

    def test_pipeline_resume_and_validation(self):
        calls=[]; clock=Clock()
        def create(key, req):
            calls.append(req)
            if len(calls)==1: raise g.APIStatusError(429, {'retry-after':'1'}, 'TPM limit')
            r=fake_response(req,len(calls))
            obj=json.loads(r['choices'][0]['message']['content']); obj['dias']['dia_01']['msg_01']='Mensagem recorrente fictícia'; r['choices'][0]['message']['content']=json.dumps(obj)
            if len(calls)==2: r['choices'][0]['finish_reason']='length'
            return {}, r
        limiter=g.RateLimiter(clock,clock.sleep)
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'privado'; output=Path(d)/'validado'
            with patch.object(g,'OUT',source),patch.dict(os.environ,{'CEREBRAS_API_KEY':'fake'}),patch.object(g,'call_api',create),patch.object(g,'RateLimiter',lambda:limiter),patch.object(g.time,'sleep',clock.sleep),patch.object(g.time,'monotonic',clock),patch.object(sys,'argv',['test']):
                self.assertEqual(g.main(),0); self.assertEqual(len(calls),26)
                self.assertEqual(calls[0],calls[1]); self.assertNotEqual(calls[1]['seed'],calls[2]['seed'])
                preserved={f: f.read_bytes() for f in source.rglob("*.json") if f.name.startswith("tentativa_") or f.name in ("mensagens.json", "plano_piloto.json")}
                self.assertEqual(g.main(),0); self.assertEqual(len(calls),26)
                self.assertTrue(all(f.read_bytes()==data for f,data in preserved.items()))
            report=v.write_outputs(source,output)
            self.assertTrue(report['valid']); self.assertEqual(report['messages'],800); self.assertEqual(report['attempts'],26)
            self.assertEqual(report['actual_review_messages'],800)
            self.assertEqual(len(report['duplicates']),1); self.assertEqual(len(report['duplicates'][0]['occurrences']),24)
            self.assertEqual(len(g.load(output/'para_analise'/'mensagens.json')),800)
            for f in (output/'para_revisao').glob('*.json'):
                self.assertEqual(set(g.load(f)),{'userId','dates','messages','review_alert_message_ids'})
            with self.assertRaises(ValueError): v.write_outputs(source,output)
            plan_path=source/"plano_piloto.json"; original_plan=g.load(plan_path); altered_plan=json.loads(json.dumps(original_plan)); altered_plan["profiles"][0]["individual_style"]["characteristics"]["registro"]="adulterado"; g.dump(plan_path,altered_plan)
            with self.assertRaises(ValueError): v.validate(source)
            g.dump(plan_path,original_plan)
            # Simular corrupção em exportação, pedido e tentativa após aceite.
            path=source/'P07'/'mensagens.json'; original=g.load(path); modified=[dict(r) for r in original]; modified[0]['text']='adulterado'; g.dump(path,modified)
            with self.assertRaises(ValueError): v.validate(source)
            with self.assertRaises(ValueError): v.write_outputs(source,Path(d)/'falha')
            self.assertFalse((Path(d)/'falha'/'para_analise').exists()); g.dump(path,original)
            attempt=source/'P07'/'bloco_01'/'tentativa_0003.json'; original=g.load(attempt); altered=json.loads(json.dumps(original)); altered['request']['seed']+=1; g.dump(attempt,altered)
            with self.assertRaises(ValueError): v.validate(source)
            g.dump(attempt,original); altered=json.loads(json.dumps(original)); altered['response']['model']='outro-modelo'; g.dump(attempt,altered)
            with self.assertRaises(ValueError): v.validate(source)
            g.dump(attempt,original); altered=json.loads(json.dumps(original)); altered['provider']='Groq'; g.dump(attempt,altered)
            with self.assertRaises(ValueError): v.validate(source)
            g.dump(attempt,original); extra=attempt.with_name('tentativa_0004.json'); g.dump(extra,original)
            with self.assertRaises(ValueError): v.validate(source)
            extra.unlink(); self.assertTrue(v.validate(source)[3]['valid'])

if __name__=='__main__': unittest.main(verbosity=2)
