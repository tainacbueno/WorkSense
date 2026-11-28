import sys,os,tempfile,shutil,json
from pathlib import Path
from unittest.mock import patch
import gerar_comunicacional_estilo_v3 as g, validar_base_estilo_v3 as v
from testar_gerador_estilo_v3 import Clock,fake_response
origin=g.OUT
with tempfile.TemporaryDirectory() as td:
    source=Path(td)/'privado'; source.mkdir();
    for pid in ('P05','P06'):
        shutil.copytree(origin/pid/'bloco_01',source/pid/'bloco_01')
    shutil.copy2(origin/'plano_piloto.json',source/'plano_piloto.json'); initial={f:f.read_bytes() for f in source.glob('*/bloco_01/*.json')}; calls=[]; clock=Clock(); limiter=g.RateLimiter(clock,clock.sleep)
    def create(key,req):
        calls.append(req)
        if len(calls)==2: raise g.APIConnectionError('fake interruption')
        return {},fake_response(req,len(calls))
    with patch.object(g,'OUT',source),patch.dict(os.environ,{'CEREBRAS_API_KEY':'fake'}),patch.object(g,'call_api',create),patch.object(g,'RateLimiter',lambda:limiter),patch.object(g.time,'sleep',clock.sleep),patch.object(g.time,'monotonic',clock),patch.object(sys,'argv',['test']):
        assert g.main()==1; assert len(calls)==2
        style_before=(source/'P05/caracterizacao/caracterizacao.json').read_bytes()
        assert g.main()==0; assert len(calls)==13; assert calls[1]==calls[2]
        assert g.main()==0; assert len(calls)==13
        assert (source/'P05/caracterizacao/caracterizacao.json').read_bytes()==style_before
    assert all(f.read_bytes()==data for f,data in initial.items())
    plan,rows,sample,report=v.validate(source); assert report['messages']==400 and report['attempts']==15
    assert sum(r['response_format']['json_schema']['name']=='caracterizacao_escrita' for r in calls)==2
    print('PASS: B1 real preservado, duas caracterizações simuladas, interrupção/retomada, 400 mensagens e 15 tentativas (incluindo 1 interrupção e 2 B1 históricos).')
