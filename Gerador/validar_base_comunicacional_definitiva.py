"""Reutiliza o validador V4 e produz recibo sem condições ou prompts."""
import argparse
from pathlib import Path
from controle_comunicacional import authorize, require
from avaliar_sinalizacoes import load, save, sha
from validar_base_estilo_v4 import write_outputs

def validate(base,source,output,freeze):
    authorize(base,freeze)
    plan=load(source/'plano_privado.json');require(plan['base']==base,'Base divergente')
    report=write_outputs(source,output)
    receipt={'base':base,'messages':report['messages'],'profiles':report['profiles'],'messages_sha256':sha(output/'para_analise'/'mensagens.json'),'freeze_sha256':sha(freeze)}
    save(output/'para_analise'/'recibo_validacao.json',receipt)
    print(f"{report['profiles']} perfis; {report['messages']} mensagens; {report['actual_review_messages']} para revisão; revisão humana pendente.")
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',choices=['calibracao','teste'],required=True);p.add_argument('--origem',type=Path,required=True);p.add_argument('--saida',type=Path,required=True);p.add_argument('--congelamento',type=Path,required=True)
    a=p.parse_args();validate(a.base,a.origem,a.saida,a.congelamento)
if __name__=='__main__':main()
