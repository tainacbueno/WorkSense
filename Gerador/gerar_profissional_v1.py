"""Piloto candidato. Não gera base oficial. Python 3.10+; sem API externa."""
import argparse, hashlib, json, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=-3))  # datas simuladas maio/junho de 2026
WINDOWS = {'baseline': ('2026-05-01','2026-05-30'), 'reanalise': ('2026-05-31','2026-06-14')}
OFFSETS = {'baseline': [4,8,12,16,20,24], 'reanalise': [3,5,7,9,11,12]}
LISTS = [{'id':f'list-{i}', 'name':n,'closed':False,'pos':i+1} for i,n in enumerate(['A Fazer','Em Andamento','Em Teste','Concluído'])]
VERSION='profissional_v1_piloto'

def seed_for(seed,*keys):
    return int.from_bytes(hashlib.sha256(json.dumps([VERSION,seed,*keys]).encode()).digest()[:8],'big')

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def plan(seed, profiles):
    result=[]
    for pid,level in profiles:
        assert level in ('estavel','leve','acentuada')
        for period,(start,end) in WINDOWS.items():
            r=random.Random(seed_for(seed,pid,period)); dates=OFFSETS[period]
            delays={}
            if r.random()<0.5: delays[r.randrange(6)]=r.choice([6,12])
            # Uma ocorrência de qualidade natural, separada do atraso.
            quality=r.choice(['nenhuma','retorno','reabertura','checklist']) if r.random()<0.5 else 'nenhuma'
            quality_idx=r.randrange(6)
            open_idx=None
            if period=='reanalise' and level!='estavel':
                added=r.sample([i for i in range(6) if i not in delays],1 if level=='leve' else 2)
                for i in added: delays[i]=r.choice([12,18,24] if level=='leve' else [24,36,48])
                if level=='acentuada' and r.random()<0.5: open_idx=r.choice(added)
            if quality_idx==open_idx: quality_idx=r.choice([i for i in range(6) if i!=open_idx])
            for i,offset in enumerate(dates):
                due=datetime.fromisoformat(start).replace(tzinfo=TZ,hour=r.choice([12,13,14]))+timedelta(days=offset)
                result.append({'userId':pid,'period':period,'cardId':f'{pid}-{period[0]}-{i+1:02}', 'due':iso(due), 'delayHours':delays.get(i,0),'open':i==open_idx,'quality':quality if i==quality_idx else 'nenhuma'})
    return result

def render(rows):
    members={p:{'id':p,'fullName':p,'username':p.lower()} for p in sorted({x['userId'] for x in rows})}
    actions=[];cards=[];checklists=[]
    for row in rows:
        pid=row['userId']; cid=row['cardId']; member=members[pid]; due=datetime.fromisoformat(row['due'].replace('Z','+00:00')); created=due-timedelta(hours=36)
        name=f'Atividade {cid}'; card={'id':cid,'name':name}; stage=0
        items=[{'id':f'{cid}-item-{j}','name':f'Item {j}','state':'incomplete'} for j in range(1,4)]
        chk={'id':f'{cid}-checklist','name':'Checklist de validação','idCard':cid,'checkItems':items}
        def emit(t,kind,data):
            actions.append({'id':f'act-{len(actions)+1:06}','type':kind,'date':iso(t),'memberCreator':member,'data':{'card':dict(card),**data}})
        def move(t,to):
            nonlocal stage
            emit(t,'updateCard',{'card':{**card,'idList':LISTS[to]['id']},'old':{'idList':LISTS[stage]['id']},'listBefore':LISTS[stage],'listAfter':LISTS[to]});stage=to
        emit(created,'createCard',{'list':LISTS[0]})
        emit(created+timedelta(minutes=1),'addMemberToCard',{'idMember':pid,'member':member})
        emit(created+timedelta(minutes=2),'updateCard',{'old':{'due':None},'card':{**card,'due':row['due']}})
        emit(created+timedelta(minutes=3),'addChecklistToCard',{'checklist':{**chk,'checkItems':[dict(x) for x in items]}})
        move(created+timedelta(hours=1),1);move(created+timedelta(hours=12),2)
        if row['quality']=='retorno':
            move(created+timedelta(hours=13),1);move(created+timedelta(hours=14),2)
        for j,item in enumerate(items):
            if (row['quality']=='checklist' or row['open']) and j==2:continue
            item['state']='complete';emit(created+timedelta(hours=15,minutes=j),'updateCheckItemStateOnCard',{'checkItem':dict(item),'checklist':{'id':chk['id']}})
        if not row['open']:
            completed=due+timedelta(hours=row['delayHours'] or -4)
            if row['quality']=='reabertura':
                move(completed-timedelta(hours=2),3);move(completed-timedelta(hours=1),2)
            move(completed,3)
        cards.append({**card,'desc':'Atividade simulada','closed':False,'idList':LISTS[stage]['id'],'idMembers':[pid],'due':row['due'],'dueComplete':stage==3,'idChecklists':[chk['id']],'badges':{'checkItems':3,'checkItemsChecked':sum(x['state']=='complete' for x in items)}})
        checklists.append(chk)
    return {'id':'board-profissional-piloto','name':'WorkSense simulado','closed':False,'lists':LISTS,'members':list(members.values()),'cards':cards,'checklists':checklists,'actions':sorted(actions,key=lambda a:(a['date'],a['id'])),'labels':[],'customFields':[]}

def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--saida',type=Path,required=True);p.add_argument('--seed',type=int,default=20261128);a=p.parse_args()
    # A distribuição do piloto é escolhida antes dos resultados.
    labels=['estavel']*4+['leve']*4+['acentuada']*4;random.Random(seed_for(a.seed,'labels')).shuffle(labels)
    profiles=[(f'PP{i:03}',level) for i,level in enumerate(labels,1)]
    rows=plan(a.seed,profiles); board=render(rows)
    a.saida.mkdir(parents=True,exist_ok=False);(a.saida/'privado').mkdir();(a.saida/'para_analise').mkdir()
    log=a.saida/'para_analise/trello_log.json';write(log,board)
    write(a.saida/'privado/plano.json',{'base':'piloto','version':VERSION,'seed':a.seed,'profiles':dict(profiles),'cards':rows,'sha256_log':sha(log),'sha256_gerador':sha(Path(__file__))})
    print(f'{len(profiles)} perfis, {len(rows)} cartões, {len(board["actions"])} ações. Piloto, não oficial.')
if __name__=='__main__':main()
