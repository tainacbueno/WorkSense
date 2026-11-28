"""Geração profissional definitiva, somente após congelamento integrado."""
import argparse
from pathlib import Path
from gerar_profissional_v1 import plan, render, sha, write
from preparar_experimento_v2 import verify_manifest, VERSION

def generate(manifest_path,comm_path,freeze_path,out):
    m=verify_manifest(manifest_path,comm_path,freeze_path)
    profiles=[(pid,v['professional_intensity']) for pid,v in sorted(m['profiles'].items())]
    rows=plan(m['professional_seed'],profiles);board=render(rows)
    # Apenas metadado do quadro; mesmas regras de eventos da V1.
    board['id']='board-profissional-teste'
    out.mkdir(parents=True,exist_ok=False);(out/'privado').mkdir();(out/'para_analise').mkdir()
    log=out/'para_analise/trello_log.json';write(log,board)
    write(out/'privado/plano.json',{'base':'teste','version':VERSION,'seed':m['professional_seed'],'profiles':dict(profiles),'cards':rows,'sha256_log':sha(log),'manifest_sha256':sha(manifest_path),'freeze_sha256':sha(freeze_path),'communication_plan_sha256':sha(comm_path),'sha256_gerador':sha(Path(__file__))})
    print(f'{len(profiles)} perfis, {len(rows)} cartões, {len(board["actions"])} ações. Rótulos em privado.')

def args_common(p):
    for key in ('manifesto','plano-comunicacional','congelamento','saida'):p.add_argument('--'+key,type=Path,required=True)
def main():
    p=argparse.ArgumentParser(description=__doc__);args_common(p);a=p.parse_args();generate(a.manifesto,a.plano_comunicacional,a.congelamento,a.saida)
if __name__=='__main__':main()
