"""Selective, local exchange of project state and decisions. No account scraping."""
import hashlib
import json
import re
from urllib.parse import urlparse

PROVIDERS = {
 'chatgpt_personal': ('ChatGPT Personal', 'Exploración y borradores'),
 'chatgpt_business': ('ChatGPT Business', 'Dirección y orquestación del proyecto'),
 'chatgpt_work': ('ChatGPT Work', 'Dirección y orquestación del proyecto'),
 'codex': ('Codex', 'Implementación, debugging, pruebas y repositorios'),
 'claude_code': ('Claude Code', 'Segunda implementación o trabajos aislados'),
 'claude': ('Claude', 'Arquitectura, crítica, revisión de especificaciones y segunda opinión'),
}

def text(value, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value)>limit:
        raise ValueError('Texto vacío o demasiado largo.')
    return value.strip()

def source_url(value, host):
    if value == '': return ''
    if not isinstance(value,str) or len(value)>1000: raise ValueError('Enlace inválido.')
    u=urlparse(value)
    if u.scheme!='https' or u.hostname!=host or u.username or u.password or u.port:
        raise ValueError('Se requiere un enlace HTTPS de '+host)
    return value

class Integrations:
    def init_integrations(self, db):
        db.executescript('''
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY, provider TEXT NOT NULL,
          label TEXT NOT NULL, workspace TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS project_sources(project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          account_id INTEGER NOT NULL REFERENCES accounts(id), sync_state INTEGER NOT NULL,
          sync_decisions INTEGER NOT NULL, PRIMARY KEY(project_id,account_id));
        CREATE TABLE IF NOT EXISTS imported_items(project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          account_id INTEGER NOT NULL REFERENCES accounts(id), digest TEXT NOT NULL,
          PRIMARY KEY(project_id,account_id,digest));
        ''')
    def integration_snapshot(self, db):
        return {k:[dict(r) for r in db.execute('SELECT * FROM '+k)] for k in ('accounts','project_sources','imported_items')}
    def validate_integrations(self, obj, pids):
        result={k:obj.get(k,[]) for k in ('accounts','project_sources','imported_items')}
        if any(not isinstance(v,list) or len(v)>20000 for v in result.values()): raise ValueError('Integraciones inválidas.')
        aids=set(); bindings=set(); digests=set()
        for a in result['accounts']:
            if not isinstance(a,dict) or type(a.get('id')) is not int or a['id']<=0 or a['id'] in aids: raise ValueError('Cuenta inválida.')
            self.account_values(a); aids.add(a['id'])
        for r in result['project_sources']:
            if not isinstance(r,dict) or r.get('project_id') not in pids or r.get('account_id') not in aids: raise ValueError('Asociación inválida.')
            key=(r['project_id'],r['account_id'])
            if key in bindings: raise ValueError('Asociación duplicada.')
            bindings.add(key)
            for k in ('sync_state','sync_decisions'):
                if type(r.get(k)) not in (bool,int) or r[k] not in (0,1): raise ValueError('Selección inválida.')
        for r in result['imported_items']:
            if not isinstance(r,dict) or r.get('project_id') not in pids or r.get('account_id') not in aids or not re.fullmatch('[a-f0-9]{64}',str(r.get('digest',''))): raise ValueError('Importación inválida.')
            key=(r['project_id'],r['account_id'],r['digest'])
            if key in digests: raise ValueError('Importación duplicada.')
            digests.add(key)
        return result
    def account_values(self,obj):
        if not isinstance(obj,dict) or obj.get('provider') not in PROVIDERS: raise ValueError('Proveedor inválido.')
        if type(obj.get('enabled',True)) not in (int,bool) or obj.get('enabled',True) not in (0,1): raise ValueError('Selección inválida.')
        workspace=obj.get('workspace','')
        if not isinstance(workspace,str) or len(workspace)>120: raise ValueError('Espacio inválido.')
        return [obj['provider'],text(obj.get('label'),120),workspace.strip(),int(obj.get('enabled',True))]
    def save_account(self,obj):
        values=self.account_values(obj)
        with self.lock,self.connect() as db:
            aid=obj.get('id')
            if aid is None:
                db.execute('INSERT INTO accounts(provider,label,workspace,enabled) VALUES(?,?,?,?)',values)
            else:
                if type(aid) is not int or not db.execute('SELECT id FROM accounts WHERE id=?',(aid,)).fetchone(): raise ValueError('Cuenta inexistente.')
                db.execute('UPDATE accounts SET provider=?,label=?,workspace=?,enabled=? WHERE id=?',values+[aid])
        return self.snapshot()
    def save_sources(self,obj):
        from app import now
        pid=obj.get('project_id'); rows=obj.get('sources')
        if type(pid) is not int or not isinstance(rows,list): raise ValueError('Selección inválida.')
        with self.lock,self.connect() as db:
            self.check_version(db,'projects',pid,obj)
            self.validate_integrations({'accounts':[dict(r) for r in db.execute('SELECT * FROM accounts')], 'project_sources':[dict(r,project_id=pid) for r in rows]}, {pid})
            db.execute('DELETE FROM project_sources WHERE project_id=?',(pid,))
            for r in rows:
                db.execute('INSERT INTO project_sources VALUES(?,?,?,?)',(pid,r['account_id'],int(r['sync_state']),int(r['sync_decisions'])))
            db.execute('UPDATE projects SET version=version+1,updated_at=? WHERE id=?',(now(),pid))
            self.event(db,pid,'nota','Usuario','Selección de fuentes IA actualizada.')
        return self.snapshot()
    def normalize_exchange(self,obj,db):
        if not isinstance(obj,dict) or set(obj)-{'project_id','account_id','version','summary','selected'}: raise ValueError('Formato de intercambio inválido.')
        pid=obj.get('project_id'); aid=obj.get('account_id'); summary=obj.get('summary')
        if type(pid) is not int or type(aid) is not int: raise ValueError('Selecciona proyecto y perfil.')
        account=db.execute('SELECT * FROM accounts WHERE id=? AND enabled=1',(aid,)).fetchone()
        source=db.execute('SELECT * FROM project_sources WHERE project_id=? AND account_id=?',(pid,aid)).fetchone()
        project=db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not account or not source or not project: raise ValueError('Este perfil no está habilitado para el proyecto.')
        if not isinstance(summary,dict) or set(summary)-{'schema','state','decisions','source_ref'} or summary.get('schema')!='proyecta.summary.v1':
            raise ValueError('Solo se aceptan resúmenes proyecta.summary.v1; no historiales completos.')
        ref=summary.get('source_ref','')
        if not isinstance(ref,str) or len(ref)>1000: raise ValueError('Referencia inválida.')
        items=[]
        state=summary.get('state',{})
        if not isinstance(state,dict) or set(state)-{'goal','status','next_action','latest_progress'}: raise ValueError('Campos de estado inválidos.')
        for key,value in state.items():
            value=text(value)
            if key=='status' and value not in ('activo','pausado','completado'): raise ValueError('Estado inválido.')
            items.append({'kind':'state','key':key,'text':value,'allowed':bool(source['sync_state'])})
        decisions=summary.get('decisions',[])
        if not isinstance(decisions,list) or len(decisions)>100: raise ValueError('Demasiadas decisiones.')
        for d in decisions:
            items.append({'kind':'decision','key':'decision','text':text(d,8000),'allowed':bool(source['sync_decisions'])})
        for i in items:
            i['digest']=hashlib.sha256(json.dumps([i['kind'],i['key'],i['text']],ensure_ascii=False).encode()).hexdigest()
            i['duplicate']=bool(db.execute('SELECT 1 FROM imported_items WHERE project_id=? AND account_id=? AND digest=?',(pid,aid,i['digest'])).fetchone())
            i['current']=project[i['key']] if i['kind']=='state' and i['key']!='latest_progress' else ''
        return project,account,ref,items
    def preview_exchange(self,obj):
        with self.lock,self.connect() as db:
            p,a,ref,items=self.normalize_exchange(obj,db)
            return {'version':p['version'],'items':items,'account':a['label'],'source_ref':ref}
    def apply_exchange(self,obj):
        from app import now
        with self.lock,self.connect() as db:
            p,a,ref,items=self.normalize_exchange(obj,db)
            self.check_version(db,'projects',p['id'],obj)
            selected=obj.get('selected')
            if not isinstance(selected,list) or not selected or any(not isinstance(x,str) for x in selected): raise ValueError('Selecciona al menos un elemento.')
            by_digest={i['digest']:i for i in items}
            if any(x not in by_digest or not by_digest[x]['allowed'] for x in selected): raise ValueError('Elemento no autorizado por la selección de fuentes.')
            applied=0
            for digest in dict.fromkeys(selected):
                i=by_digest[digest]
                if i['duplicate']: continue
                actor=PROVIDERS[a['provider']][0]+' · '+a['label']
                if i['kind']=='decision': self.event(db,p['id'],'decision',actor,i['text'],ref)
                else:
                    if i['key']!='latest_progress':
                        db.execute('UPDATE projects SET '+i['key']+'=? WHERE id=?',(i['text'],p['id']))
                    self.event(db,p['id'],'ia',actor,'Último avance: '+i['text'] if i['key']=='latest_progress' else i['key']+': '+i['text'],ref)
                db.execute('INSERT INTO imported_items VALUES(?,?,?)',(p['id'],a['id'],digest));applied+=1
            if applied: db.execute('UPDATE projects SET version=version+1,updated_at=? WHERE id=?',(now(),p['id']))
        return self.snapshot()
    def exchange_prompt(self,pid,aid):
        snap=self.snapshot(); p=next((r for r in snap['projects'] if r['id']==pid),None)
        a=next((r for r in snap['accounts'] if r['id']==aid),None)
        source=next((r for r in snap['project_sources'] if r['project_id']==pid and r['account_id']==aid),None)
        if not p or not a or not a['enabled'] or not source or not (source['sync_state'] or source['sync_decisions']): raise ValueError('Selecciona un perfil habilitado para el proyecto.')
        context={'project':p['name'],'state':{k:p[k] for k in ('goal','status','phase','next_action')} if source['sync_state'] else {},'decisions':[e['text'] for e in snap['events'] if e['project_id']==pid and e['kind']=='decision'] if source['sync_decisions'] else [],'sources':{'github':p['repository'],'branch':p['branch'],'drive':p['documents']}}
        return ('Resume exclusivamente el estado y las decisiones de '+p['name']+'. No incluyas conversaciones, secretos ni conclusiones sin respaldo. Omite datos desconocidos. '+
        'Distingue lo implementado de lo propuesto en latest_progress. Devuelve JSON puro con este formato (los valores son ejemplos, reemplázalos):\n'+
        json.dumps({'schema':'proyecta.summary.v1','source_ref':'Referencia de la conversación o artefacto','state':{'goal':'Objetivo vigente','status':'activo','next_action':'Siguiente acción','latest_progress':'Último avance y evidencia'},'decisions':['Decisión aprobada']},ensure_ascii=False,indent=2)+'\n\nRol de esta herramienta: '+PROVIDERS[a['provider']][1]+'\n\nEstado y decisiones registrados (verifica vigencia):\n'+json.dumps(context,ensure_ascii=False,indent=2))
