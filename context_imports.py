"""Reviewable import of structured project context from AI/cloud workspaces."""
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


CONTEXT_PROVIDERS = {
    'chatgpt_personal': 'ChatGPT Personal', 'chatgpt_business': 'ChatGPT Business',
    'chatgpt_work': 'ChatGPT Work', 'claude': 'Claude', 'claude_code': 'Claude Code',
    'codex': 'Codex / Cloud', 'other': 'Otra fuente',
}
CONTEXT_STATUSES = {'implementado', 'parcial', 'pendiente', 'bloqueado', 'descartado'}
MAX_ITEMS = 500
MAX_CONTEXT_BYTES = 500_000


def _text(value, label, limit=8000, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{label}: texto inválido o supera {limit} caracteres.')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{label}: este campo es obligatorio.')
    return value


def _url(value, label='Enlace'):
    value = _text(value, label, 1000)
    if not value:
        return ''
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port:
        raise ValueError(f'{label}: usa un enlace HTTPS válido, sin credenciales.')
    return value


class ContextImports:
    def init_context_imports(self, db):
        db.executescript('''
        CREATE TABLE IF NOT EXISTS context_imports (
          id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          provider TEXT NOT NULL, source_label TEXT NOT NULL, source_ref TEXT NOT NULL,
          payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS context_import_items (
          id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES context_imports(id) ON DELETE CASCADE,
          project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
          provider TEXT NOT NULL, kind TEXT NOT NULL, item_key TEXT NOT NULL, text TEXT NOT NULL,
          certainty TEXT NOT NULL DEFAULT 'declarado_en_fuente', evidence TEXT NOT NULL DEFAULT '',
          digest TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS context_import_items_project_idx ON context_import_items(project_id,kind);
        ''')
        schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='context_import_items'").fetchone()[0]
        if 'UNIQUE(project_id,digest)' in schema.replace(' ', '').replace('\n', ''):
            db.execute('DROP INDEX IF EXISTS context_import_items_project_idx')
            db.execute('''CREATE TABLE context_import_items_new (
              id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES context_imports(id) ON DELETE CASCADE,
              project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              provider TEXT NOT NULL, kind TEXT NOT NULL, item_key TEXT NOT NULL, text TEXT NOT NULL,
              certainty TEXT NOT NULL DEFAULT 'declarado_en_fuente', evidence TEXT NOT NULL DEFAULT '',
              digest TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('INSERT INTO context_import_items_new SELECT * FROM context_import_items')
            db.execute('DROP TABLE context_import_items')
            db.execute('ALTER TABLE context_import_items_new RENAME TO context_import_items')
            db.execute('CREATE INDEX context_import_items_project_idx ON context_import_items(project_id,kind)')

    def context_import_snapshot(self, db):
        return {
            'context_imports': [dict(r) for r in db.execute('SELECT * FROM context_imports ORDER BY id')],
            'context_import_items': [dict(r) for r in db.execute('SELECT * FROM context_import_items ORDER BY id')],
        }

    def validate_context_import_snapshot(self, obj, project_ids):
        batches = obj.get('context_imports', [])
        items = obj.get('context_import_items', [])
        if not isinstance(batches, list) or not isinstance(items, list) or len(batches) > 20000 or len(items) > 100000:
            raise ValueError('Respaldo de contexto importado inválido o demasiado grande.')
        batch_ids, batch_keys, item_ids = set(), set(), set()
        for row in batches:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0 or row['id'] in batch_ids:
                raise ValueError('Registro de importación inválido en el respaldo.')
            if row.get('project_id') not in project_ids or row.get('provider') not in CONTEXT_PROVIDERS:
                raise ValueError('Referencia o proveedor inválido en una importación respaldada.')
            _text(row.get('source_label'), 'Fuente', 120, True)
            _text(row.get('source_ref'), 'Referencia', 1000)
            try:
                payload = json.loads(row.get('payload_json', ''))
            except (TypeError, json.JSONDecodeError):
                raise ValueError('Contenido de importación inválido en el respaldo.')
            if not isinstance(payload, dict) or len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_CONTEXT_BYTES:
                raise ValueError('Contenido de importación fuera de límites.')
            _text(row.get('created_at'), 'Fecha', 60, True)
            batch_ids.add(row['id']); batch_keys.add((row['id'], row['project_id']))
        for row in items:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0 or row['id'] in item_ids:
                raise ValueError('Elemento importado inválido en el respaldo.')
            if (row.get('import_id'), row.get('project_id')) not in batch_keys or row.get('provider') not in CONTEXT_PROVIDERS:
                raise ValueError('Elemento importado apunta a una fuente inexistente.')
            if row.get('kind') not in ('project', 'design', 'component', 'decision', 'backlog', 'test', 'risk', 'progress'):
                raise ValueError('Tipo de elemento importado inválido.')
            _text(row.get('item_key'), 'Clave de elemento', 160, True)
            _text(row.get('text'), 'Elemento', 12000, True)
            _text(row.get('certainty'), 'Certeza', 40, True); _text(row.get('evidence'), 'Evidencia', 2000)
            if not re.fullmatch(r'[a-f0-9]{64}', str(row.get('digest', ''))):
                raise ValueError('Huella inválida en elemento importado.')
            _text(row.get('created_at'), 'Fecha', 60, True)
            item_ids.add(row['id'])
        return {'context_imports': batches, 'context_import_items': items}

    def _normalize_context_payload(self, payload):
        if isinstance(payload, str):
            if len(payload.encode('utf-8')) > MAX_CONTEXT_BYTES:
                raise ValueError('El archivo supera el límite de 500 KB.')
            try: payload = json.loads(payload)
            except json.JSONDecodeError as error: raise ValueError(f'JSON inválido en la línea {error.lineno}.')
        if not isinstance(payload, dict) or payload.get('schema') != 'proyecta.context.v1':
            raise ValueError('Formato requerido: proyecta.context.v1. Usa el prompt de importación para prepararlo.')
        allowed = {'schema', 'project', 'design', 'components', 'decisions', 'backlog', 'tests', 'risks', 'latest_progress'}
        if set(payload) - allowed: raise ValueError('El formato incluye campos no admitidos: ' + ', '.join(sorted(set(payload)-allowed)))
        project = payload.get('project')
        if not isinstance(project, dict) or set(project)-{'name','company','goal','status','phase','next_action','repository','branch','documents','environment'}:
            raise ValueError('Metadatos del proyecto inválidos.')
        project = {
            'name': _text(project.get('name'), 'Nombre del proyecto', 120, True),
            'company': _text(project.get('company') or 'Sin empresa', 'Empresa', 120, True),
            'goal': _text(project.get('goal', ''), 'Objetivo', 4000),
            'status': _text(project.get('status') or 'activo', 'Estado', 30),
            'phase': _text(project.get('phase', ''), 'Fase', 30),
            'next_action': _text(project.get('next_action', ''), 'Próxima acción', 4000),
            'repository': _url(project.get('repository', ''), 'Repositorio'),
            'branch': _text(project.get('branch', ''), 'Rama', 200),
            'documents': _url(project.get('documents', ''), 'Documentación'),
            'environment': _text(project.get('environment', ''), 'Entorno', 1000),
        }
        if project['status'] not in ('activo','pausado','completado'): raise ValueError('Estado de proyecto inválido.')
        if project['phase'] not in ('','Diseño','MVP','Desarrollo','Pruebas','Listo'): raise ValueError('Fase inválida.')
        design = payload.get('design', {})
        if not isinstance(design, dict) or set(design)-{'functional','technical'}: raise ValueError('Diseño funcional/técnico inválido.')
        design = {'functional':_text(design.get('functional',''),'Diseño funcional',12000),
                  'technical':_text(design.get('technical',''),'Diseño técnico',12000)}
        components = payload.get('components', [])
        decisions = payload.get('decisions', [])
        backlog = payload.get('backlog', [])
        tests = payload.get('tests', [])
        risks = payload.get('risks', [])
        for label, value in (('Componentes',components),('Decisiones',decisions),('Backlog',backlog),('Pruebas',tests),('Riesgos',risks)):
            if not isinstance(value,list) or len(value)>MAX_ITEMS: raise ValueError(f'{label}: se requiere una lista de hasta {MAX_ITEMS} elementos.')
        normalized_components=[]
        for row in components:
            if not isinstance(row,dict) or set(row)-{'name','status','description','evidence'}: raise ValueError('Componente inválido.')
            status=_text(row.get('status','pendiente'),'Estado del componente',30)
            if status not in CONTEXT_STATUSES: raise ValueError('Estado de componente inválido.')
            normalized_components.append({'name':_text(row.get('name'),'Componente',160,True),'status':status,
                'description':_text(row.get('description',''),'Descripción',4000),
                'evidence':_text(row.get('evidence',''),'Referencia de evidencia',2000)})
        normalized_decisions=[_text(x,'Decisión',4000,True) for x in decisions]
        normalized_backlog=[]
        for row in backlog:
            if not isinstance(row,dict) or set(row)-{'title','objective','acceptance','priority','dependencies'}: raise ValueError('Tarea de backlog inválida.')
            priority=_text(row.get('priority','media'),'Prioridad',10)
            if priority not in ('alta','media','baja'): raise ValueError('Prioridad de tarea inválida.')
            deps=row.get('dependencies',[])
            if not isinstance(deps,list) or len(deps)>30 or any(not isinstance(d,str) or len(d)>160 for d in deps): raise ValueError('Dependencias importadas inválidas.')
            normalized_backlog.append({'title':_text(row.get('title'),'Tarea',240,True),
                'objective':_text(row.get('objective',''),'Objetivo de tarea',2000),
                'acceptance':_text(row.get('acceptance',''),'Criterios de aceptación',3000),
                'priority':priority,'dependencies':deps})
        normalized_tests=[]
        for row in tests:
            if not isinstance(row,dict) or set(row)-{'name','result','evidence','date'}: raise ValueError('Resultado de prueba inválido.')
            normalized_tests.append({'name':_text(row.get('name'),'Prueba',240,True), 'result':_text(row.get('result'),'Resultado',1000,True),
                'evidence':_text(row.get('evidence',''),'Referencia',2000),'date':_text(row.get('date',''),'Fecha',60)})
        normalized_risks=[_text(x,'Riesgo',2000,True) for x in risks]
        return {'schema':'proyecta.context.v1','project':project,'design':design,'components':normalized_components,
                'decisions':normalized_decisions,'backlog':normalized_backlog,'tests':normalized_tests,
                'risks':normalized_risks,'latest_progress':_text(payload.get('latest_progress',''),'Último avance',4000)}

    def _context_candidate_items(self, payload):
        result=[]
        def add(kind,key,text,evidence=''):
            if not text: return
            digest=hashlib.sha256(json.dumps([kind,key,text],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            result.append({'kind':kind,'key':key,'text':text,'evidence':evidence,'certainty':'declarado_en_fuente','digest':digest})
        for key,value in payload['project'].items(): add('project',key,str(value))
        add('design','functional',payload['design']['functional']); add('design','technical',payload['design']['technical'])
        for i,row in enumerate(payload['components']): add('component',row['name'],json.dumps(row,ensure_ascii=False),row['evidence'])
        for i,value in enumerate(payload['decisions']): add('decision',str(i+1),value)
        for i,row in enumerate(payload['backlog']): add('backlog',row['title'],json.dumps(row,ensure_ascii=False))
        for i,row in enumerate(payload['tests']): add('test',row['name'],json.dumps(row,ensure_ascii=False),row['evidence'])
        for i,value in enumerate(payload['risks']): add('risk',str(i+1),value)
        add('progress','latest_progress',payload['latest_progress'])
        return result

    def preview_context_import(self, obj):
        if not isinstance(obj,dict) or set(obj)-{'project_id','provider','source_label','source_ref','payload'}:
            raise ValueError('Solicitud de importación inválida.')
        provider=obj.get('provider')
        if provider not in CONTEXT_PROVIDERS: raise ValueError('Selecciona una fuente compatible.')
        source_label=_text(obj.get('source_label'), 'Nombre de fuente',120,True)
        source_ref=_url(obj.get('source_ref',''),'Enlace del proyecto o conversación')
        payload=self._normalize_context_payload(obj.get('payload'))
        candidates=self._context_candidate_items(payload)
        project_id=obj.get('project_id')
        with self.lock,self.connect() as db:
            current=None
            if project_id is not None:
                if type(project_id) is not int: raise ValueError('Proyecto destino inválido.')
                current=db.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone()
                if not current: raise ValueError('Proyecto destino inexistente.')
            for item in candidates:
                latest=db.execute('SELECT digest FROM context_import_items WHERE project_id=? AND kind=? AND item_key=? ORDER BY id DESC LIMIT 1',
                    (project_id,item['kind'],item['key'])).fetchone() if current else None
                item['duplicate']=bool(latest and latest['digest']==item['digest'])
                item['current']=current[item['key']] if current and item['kind']=='project' and item['key'] in current.keys() else ''
            return {'project_id':project_id,'project_name':current['name'] if current else payload['project']['name'],
                    'version':current['version'] if current else None,'provider':provider,
                    'provider_label':CONTEXT_PROVIDERS[provider],'source_label':source_label,'source_ref':source_ref,
                    'payload':payload,'items':candidates,'notice':'Los elementos importados se marcan como declarados por la fuente. Proyecta no los considera pruebas verificadas.'}

    def apply_context_import(self, obj):
        from app import now
        if not isinstance(obj,dict) or set(obj)-{'project_id','version','provider','source_label','source_ref','payload','selected'}:
            raise ValueError('Solicitud de incorporación inválida.')
        preview=self.preview_context_import({k:obj.get(k) for k in ('project_id','provider','source_label','source_ref','payload')})
        selected=obj.get('selected')
        if not isinstance(selected,list) or not selected or any(not isinstance(x,str) for x in selected): raise ValueError('Selecciona al menos un elemento para incorporar.')
        by_digest={x['digest']:x for x in preview['items']}
        if any(x not in by_digest for x in selected): raise ValueError('La selección cambió; revisa de nuevo la importación.')
        selected=list(dict.fromkeys(selected))
        payload=preview['payload']; project_id=preview['project_id']
        selected_items=[by_digest[x] for x in selected if not by_digest[x]['duplicate']]
        if not selected_items: raise ValueError('Todos los elementos seleccionados ya fueron importados.')
        with self.lock,self.connect() as db:
            if project_id is None:
                base={'name':'','company':'Sin empresa','goal':'','status':'activo','priority':'media',
                      'next_action':'','repository':'','branch':'','documents':'','environment':'','phase':''}
                for item in selected_items:
                    if item['kind']=='project': base[item['key']]=item['text']
                if not base['name']:
                    raise ValueError('Para crear un proyecto nuevo debes seleccionar su nombre.')
                project={**base,'priority':'media'}
                values=self.project_values(project)
                project_id=db.execute('INSERT INTO projects(name,company,goal,status,priority,next_action,repository,branch,documents,environment,phase,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',values+[now()]).lastrowid
                self.event(db,project_id,'nota','Proyecta','Proyecto creado durante la importación revisada.')
                current_version=1
            else:
                row=db.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone()
                if not row or type(obj.get('version')) is not int or row['version']!=obj['version']:
                    raise RuntimeError('El proyecto cambió durante la revisión. Recarga y revisa las diferencias.')
                current_version=row['version']
            # Keep only material the user approved. The preview payload may contain
            # unchecked or duplicate claims, so it must not be retained wholesale.
            batch_payload={'schema':'proyecta.context.v1','accepted_items':[
                {'kind':x['kind'],'key':x['key'],'text':x['text'],'evidence':x['evidence'],'digest':x['digest']}
                for x in selected_items]}
            batch_id=db.execute('INSERT INTO context_imports(project_id,provider,source_label,source_ref,payload_json,created_at) VALUES(?,?,?,?,?,?)',
                (project_id,preview['provider'],preview['source_label'],preview['source_ref'],json.dumps(batch_payload,ensure_ascii=False),now())).lastrowid
            project_updates={}
            task_count=0
            for item in selected_items:
                kind,key,value=item['kind'],item['key'],item['text']
                db.execute('INSERT INTO context_import_items(import_id,project_id,provider,kind,item_key,text,certainty,evidence,digest,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (batch_id,project_id,preview['provider'],kind,key,value,'declarado_en_fuente',item['evidence'],item['digest'],now()))
                actor=CONTEXT_PROVIDERS[preview['provider']]+' · '+preview['source_label']
                if kind=='project': project_updates[key]=value
                elif kind=='backlog':
                    task=json.loads(value)
                    task_obj={'project_id':project_id,'title':task['title'],'status':'pendiente','needs_me':False,
                        'owner':actor,'notes':'Importado desde contexto seleccionado. Verifica alcance antes de iniciar.',
                        'evidence':'','objective':task['objective'],'acceptance':task['acceptance'],
                        'dependencies':[],'ai_profile':preview['provider'] if preview['provider'] in ('codex','claude_code','claude','chatgpt_personal','chatgpt_business','chatgpt_work') else '',
                        'role':'implementacion','skill_refs':[],'branch':payload['project']['branch'],'commit_ref':'',
                        'pull_request':'','tests':'','checkpoint':'Revisar origen y criterios importados.','execution_environment':'development'}
                    vals=self.task_values(task_obj,db,project_id,None)
                    cols=('title','status','needs_me','owner','notes','evidence','objective','acceptance','dependencies','ai_profile','role','skill_refs','branch','commit_ref','pull_request','tests','checkpoint','execution_environment')
                    tid=db.execute('INSERT INTO tasks(project_id,'+','.join(cols)+',updated_at) VALUES('+','.join('?' for _ in range(len(cols)+2))+')',[project_id]+vals+[now()]).lastrowid
                    self.event(db,project_id,'nota',actor,f'Tarea #{tid} importada: {task["title"]}.',preview['source_ref']);task_count+=1
                elif kind=='decision': self.event(db,project_id,'decision',actor,value,preview['source_ref'])
                elif kind=='test': self.event(db,project_id,'prueba',actor,'Resultado declarado: '+value,item['evidence'] or preview['source_ref'])
                else: self.event(db,project_id,'ia',actor,kind+': '+value,item['evidence'] or preview['source_ref'])
            if project_updates:
                current=dict(db.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone())
                updated={**current,**project_updates}
                vals=self.project_values(updated)
                db.execute('UPDATE projects SET name=?,company=?,goal=?,status=?,priority=?,next_action=?,repository=?,branch=?,documents=?,environment=?,phase=?,updated_at=?,version=version+1 WHERE id=?',vals+[now(),project_id])
            else:
                db.execute('UPDATE projects SET updated_at=?,version=version+1 WHERE id=?',(now(),project_id))
            self.event(db,project_id,'ia',CONTEXT_PROVIDERS[preview['provider']]+' · '+preview['source_label'],
                f'Contexto técnico importado y revisado: {len(selected_items)} elementos, {task_count} tareas nuevas.',preview['source_ref'])
        return {'state':self.snapshot(),'project_id':project_id,'import_id':batch_id,'imported':len(selected_items),'tasks_created':task_count}

    def context_import_prompt(self, provider):
        if provider not in CONTEXT_PROVIDERS: raise ValueError('Fuente de contexto inválida.')
        return f'''Prepara una captura de contexto del proyecto actual para importar en Proyecta. Fuente: {CONTEXT_PROVIDERS[provider]}.
Usa solo información visible en el proyecto elegido. No inventes datos, commits, pruebas o estados. En cada componente describe el estado como declarado por la fuente; Proyecta lo marcará como no verificado. Conserva el repositorio GitHub, rama, PR y referencias de evidencia si están disponibles. Omite secretos, tokens y conversaciones completas. Devuelve únicamente JSON válido con este esquema:
{{"schema":"proyecta.context.v1","project":{{"name":"","company":"","goal":"","status":"activo","phase":"Diseño","next_action":"","repository":"https://github.com/owner/repo","branch":"main","documents":"","environment":""}},"design":{{"functional":"","technical":""}},"components":[{{"name":"","status":"implementado|parcial|pendiente|bloqueado|descartado","description":"","evidence":"ruta, commit o referencia; no afirmes verificación si no puedes mostrarla"}}],"decisions":["decisiones aprobadas"],"backlog":[{{"title":"","objective":"","acceptance":"","priority":"alta|media|baja","dependencies":[]}}],"tests":[{{"name":"","result":"","evidence":"comando, CI o enlace","date":""}}],"risks":["riesgos o preguntas abiertas"],"latest_progress":""}}
El resultado se revisará antes de incorporarse. Marca listas vacías cuando no haya información y no atribuyas a Proyecta la verificación de afirmaciones.'''

    def context_dossier(self, project_id):
        with self.lock,self.connect() as db:
            project=db.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone()
            if not project: raise ValueError('Proyecto inexistente.')
            batches=[dict(r) for r in db.execute('SELECT * FROM context_imports WHERE project_id=? ORDER BY id',(project_id,))]
            tasks=[self.task_record(dict(r)) for r in db.execute('SELECT * FROM tasks WHERE project_id=? ORDER BY id',(project_id,))]
            items=[dict(r) for r in db.execute('SELECT * FROM context_import_items WHERE project_id=? ORDER BY id',(project_id,))]
        lines=[f'# Expediente técnico · {project["name"]}','',f'Fecha de corte: {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
            f'Empresa: {project["company"]}',f'Estado/fase: {project["status"]} / {project["phase"] or "Sin definir"}',
            f'Objetivo: {project["goal"] or "Sin registrar"}',f'Repositorio: {project["repository"] or "Sin registrar"}',
            f'Rama: {project["branch"] or "Sin registrar"}',f'Próxima acción: {project["next_action"] or "Sin registrar"}','',
            '## Procedencia y certeza','', 'Las afirmaciones importadas desde conversaciones o resúmenes se consideran declaradas por la fuente. Proyecta no las presenta como pruebas de código ni de ejecución.', '']
        for b in batches:
            lines.extend([f'### Importación #{b["id"]} · {CONTEXT_PROVIDERS.get(b["provider"],b["provider"])} · {b["source_label"]}',
                f'- Fecha: {b["created_at"]}',f'- Referencia: {b["source_ref"] or "No registrada"}',''])
        for kind,title in (('design','Diseño'),('component','Avance por componente'),('decision','Decisiones'),('backlog','Desarrollo esperado'),('test','Pruebas declaradas'),('risk','Riesgos y preguntas'),('progress','Avance declarado')):
            subset=[i for i in items if i['kind']==kind]
            if not subset: continue
            lines.extend([f'## {title}',''])
            for item in subset:
                if kind=='design': label='Diseño funcional' if item['item_key']=='functional' else 'Diseño técnico'
                else: label=item['item_key']
                body=item['text']
                if kind in ('component','backlog','test'):
                    try: body=json.dumps(json.loads(body),ensure_ascii=False,indent=2)
                    except json.JSONDecodeError: pass
                lines.extend([f'### {label}',f'- Certeza: {item["certainty"]}',f'- Fuente: {CONTEXT_PROVIDERS.get(item["provider"],item["provider"])}',
                    f'- Evidencia declarada: {item["evidence"] or "No indicada"}', '',body,''])
        lines.extend(['## Tareas en Proyecta',''])
        for task in tasks:
            lines.extend([f'- [{task["status"]}] {task["title"]}',f'  - Aceptación: {task["acceptance"] or "Pendiente de definir"}',f'  - Origen/responsable: {task["owner"]}'])
        if not tasks: lines.append('No hay tareas registradas.')
        return '\n'.join(lines)+'\n'
