"""Controle do teste integrado. Nenhuma chamada de API; não cria rótulos A–D."""
import argparse, hashlib, importlib.util, json, random, re, subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path
from avaliar_sinalizacoes import threshold_calibration, load, sha, save

ROOT = Path(__file__).resolve().parent.parent
IDS = {f'TST{i:03}' for i in range(1,41)}
PROF_THRESHOLD = '7'
VERSION = 'profissional_v2_definitiva'
CORE = ['gerar_profissional_v1.py','validar_profissional_v1.py','trello_funcoes_originais.py','score_funcoes_originais.py','avaliar_sinalizacoes.py','preparar_experimento_v2.py','gerar_profissional_v2.py','validar_profissional_v2.py','avaliar_sinalizacoes_v2.py','testar_profissional_v2.py']

def require(ok, message):
    if not ok: raise ValueError(message)

def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args],stderr=subprocess.PIPE)

def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()

def tagged_files(tag, paths):
    commit = git('rev-parse',f'{tag}^{{commit}}').decode().strip()
    require(re.fullmatch(r'[0-9a-f]{40,64}',commit), 'Commit inválido')
    hashes = {}
    for path in paths:
        rel=relative(path)
        actual=sha(ROOT/rel)
        require(hashlib.sha256(git('show',f'{commit}:{rel}')).hexdigest()==actual, f'Arquivo diferente do commit congelado: {rel}')
        hashes[rel]=actual
    return commit,hashes

def calibration(scores, threshold):
    t=load(threshold)
    require(t.get('source_sha256')==sha(scores) and t.get('n')==40 and t.get('k')==2 and t.get('rule')=='>', 'Limiar/calibração incompatíveis')
    require(Decimal(t['threshold'])==threshold_calibration(load(scores)), 'Limiar não reproduz a calibração')
    return str(Decimal(t['threshold']))

def freeze(tag, comm, scores, threshold, other, declaration):
    require(declaration is True, 'Confirme revisão do gerador e registro do congelamento antes do teste')
    require(other, 'Inclua os notebooks/scripts comunicacionais finais e o protocolo no congelamento')
    paths=[ROOT/'Gerador'/x for x in CORE]+[comm,scores,threshold,*other]
    commit,files=tagged_files(tag,paths)
    return {'version':VERSION,'tag':tag,'commit':commit,'files':files,'communication_generator':relative(comm),'calibration_scores':relative(scores),'calibration_threshold':relative(threshold),'thresholds':{'comunicacional':calibration(scores,threshold),'profissional':PROF_THRESHOLD},'rules':{'comunicacional':'>','profissional':'>='},'declared_review_and_freeze':True}

def verify_freeze(f):
    require(f.get('version')==VERSION and f.get('declared_review_and_freeze') is True, 'Registro de congelamento inválido')
    require(f.get('rules')=={'comunicacional':'>','profissional':'>='} and f['thresholds']['profissional']==PROF_THRESHOLD, 'Regras alteradas')
    files=f['files']; required={f'Gerador/{x}' for x in CORE}|{f[k] for k in ('communication_generator','calibration_scores','calibration_threshold')}
    require(required<=set(files), 'Arquivos obrigatórios ausentes do congelamento')
    commit,actual=tagged_files(f['tag'],[ROOT/x for x in files])
    require(commit==f['commit'] and actual==files,'Congelamento divergente')
    require(f['thresholds']['comunicacional']==calibration(ROOT/f['calibration_scores'],ROOT/f['calibration_threshold']),'Limiar comunicacional divergente')
    return f

def labels_from_plan(plan):
    require(plan.get('base')=='teste' and plan.get('purpose')=='teste_independente', 'Plano não pertence ao teste independente')
    entries=plan['profiles']; labels={p['id']:p['experimental_condition'] for p in entries}
    require(len(entries)==40 and set(labels)==IDS and Counter(labels.values())==Counter({x:10 for x in 'ABCD'}),'Exige exatamente 10 perfis de cada grupo A–D')
    require(all(p['condition']==('alterada' if p['experimental_condition'] in 'BD' else 'estavel') for p in entries),'Condição comunicacional inconsistente')
    return labels

def allocation(plan, seed):
    require(type(seed) is int,'Semente profissional inválida')
    labels=labels_from_plan(plan); levels={p:'estavel' for p,l in labels.items() if l in 'AB'}
    for group in 'CD':
        rng=random.Random(int.from_bytes(hashlib.sha256(f'prof-v2-intensity|{seed}|{group}'.encode()).digest()[:8],'big'))
        ids=sorted(p for p,l in labels.items() if l==group);rng.shuffle(ids)
        levels.update({p:('leve' if i<5 else 'acentuada') for i,p in enumerate(ids)})
    return {p:{'group':labels[p],'professional_intensity':levels[p]} for p in sorted(labels)}

def verify_plan(plan,f):
    labels_from_plan(plan)
    path=ROOT/f['communication_generator']
    require(plan.get('script_sha256')==sha(path), 'Plano comunicacional não pertence ao gerador congelado')
    spec=importlib.util.spec_from_file_location('_comm_frozen',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    require(plan==m.make_plan('teste',plan['private_assignment_seed']), 'Plano comunicacional não reproduz a atribuição congelada')

def manifest(plan_path, freeze_path, seed):
    f=verify_freeze(load(freeze_path));plan=load(plan_path);verify_plan(plan,f)
    require(seed!=plan['private_assignment_seed'],'Use uma semente profissional distinta da semente de atribuição A–D')
    return {'version':VERSION,'base':'teste','freeze_sha256':sha(freeze_path),'communication_plan_sha256':sha(plan_path),'professional_seed':seed,'profiles':allocation(plan,seed)}

def verify_manifest(mpath,plan_path,freeze_path):
    m=load(mpath); require(m==manifest(plan_path,freeze_path,m['professional_seed']),'Manifesto privado divergente')
    return m

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('congelar');a.add_argument('--tag',required=True);a.add_argument('--gerador-comunicacional',type=Path,required=True);a.add_argument('--scores-calibracao',type=Path,required=True);a.add_argument('--limiar-comunicacional',type=Path,required=True);a.add_argument('--arquivos-metodo',type=Path,nargs='+',required=True);a.add_argument('--confirmar-revisao-e-congelamento',action='store_true');a.add_argument('--saida',type=Path,required=True)
    a=s.add_parser('manifesto');a.add_argument('--plano-comunicacional',type=Path,required=True);a.add_argument('--congelamento',type=Path,required=True);a.add_argument('--seed-profissional',type=int,required=True);a.add_argument('--saida',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='congelar':r=freeze(a.tag,a.gerador_comunicacional,a.scores_calibracao,a.limiar_comunicacional,a.arquivos_metodo,a.confirmar_revisao_e_congelamento)
    else:r=manifest(a.plano_comunicacional,a.congelamento,a.seed_profissional)
    save(a.saida,r);print('SHA256',sha(a.saida))
if __name__=='__main__':main()
