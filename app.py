#!/usr/bin/env python3
"""Proyecta 1.3: local-first project control center, Python standard library only."""
import argparse
from contextlib import contextmanager
import io
import json
import os
import secrets
import sqlite3
import sys
import threading
import webbrowser
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

VERSION = '1.3.0'
ROOT = Path(__file__).resolve().parent
MAX_BODY = 5 * 1024 * 1024
STATUSES = ('pendiente', 'lista', 'en_curso', 'bloqueada', 'en_revision', 'en_validacion', 'completada')
KINDS = ('nota', 'decision', 'ia', 'prueba', 'despliegue')
TASK_ROLES = ('coordinacion', 'implementacion', 'arquitectura', 'revision', 'validacion', 'documentacion', 'otro')
TASK_ENVIRONMENTS = ('development', 'test', 'staging', 'production')

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def data_home():
    if os.environ.get('PROYECTA_DATA_DIR'):
        return Path(os.environ['PROYECTA_DATA_DIR']).expanduser()
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Proyecta'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Proyecta'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'proyecta'

def field(obj, key, limit=2000, required=False):
    value = obj.get(key, '')
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Campo inválido: {key} (máximo {limit} caracteres).')
    value = value.strip()
    if required and not value:
        raise ValueError(f'El campo {key} es obligatorio.')
    return value

def link(value):
    if value and (urlparse(value).scheme not in ('https', 'http') or not urlparse(value).netloc):
        raise ValueError('Los enlaces deben comenzar con https:// o http://.')
    return value

from integrations import Integrations
from context_imports import ContextImports
from skills import Skills, SKILL_PROVIDERS

class Store(Skills, Integrations, ContextImports):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, company TEXT NOT NULL,
                goal TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL,
                next_action TEXT NOT NULL, repository TEXT NOT NULL, branch TEXT NOT NULL,
                documents TEXT NOT NULL, environment TEXT NOT NULL, updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL, status TEXT NOT NULL, needs_me INTEGER NOT NULL,
                owner TEXT NOT NULL, notes TEXT NOT NULL, evidence TEXT NOT NULL,
                updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                objective TEXT NOT NULL DEFAULT '', acceptance TEXT NOT NULL DEFAULT '',
                dependencies TEXT NOT NULL DEFAULT '[]', ai_profile TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '', skill_refs TEXT NOT NULL DEFAULT '[]',
                branch TEXT NOT NULL DEFAULT '', commit_ref TEXT NOT NULL DEFAULT '',
                pull_request TEXT NOT NULL DEFAULT '', tests TEXT NOT NULL DEFAULT '',
                checkpoint TEXT NOT NULL DEFAULT '', execution_environment TEXT NOT NULL DEFAULT 'development');
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                kind TEXT NOT NULL, actor TEXT NOT NULL, text TEXT NOT NULL,
                evidence TEXT NOT NULL, created_at TEXT NOT NULL);
            PRAGMA user_version=1;
            ''')
            if 'phase' not in [r[1] for r in db.execute('PRAGMA table_info(projects)')]:
                db.execute("ALTER TABLE projects ADD COLUMN phase TEXT NOT NULL DEFAULT ''")
            task_columns = {r[1] for r in db.execute('PRAGMA table_info(tasks)')}
            migrations = {
                'objective': "TEXT NOT NULL DEFAULT ''", 'acceptance': "TEXT NOT NULL DEFAULT ''",
                'dependencies': "TEXT NOT NULL DEFAULT '[]'", 'ai_profile': "TEXT NOT NULL DEFAULT ''",
                'role': "TEXT NOT NULL DEFAULT ''", 'skill_refs': "TEXT NOT NULL DEFAULT '[]'",
                'branch': "TEXT NOT NULL DEFAULT ''", 'commit_ref': "TEXT NOT NULL DEFAULT ''",
                'pull_request': "TEXT NOT NULL DEFAULT ''", 'tests': "TEXT NOT NULL DEFAULT ''",
                'checkpoint': "TEXT NOT NULL DEFAULT ''",
                'execution_environment': "TEXT NOT NULL DEFAULT 'development'",
            }
            for column, sql_type in migrations.items():
                if column not in task_columns:
                    db.execute(f'ALTER TABLE tasks ADD COLUMN {column} {sql_type}')
            db.execute('PRAGMA user_version=2')
            self.init_integrations(db)
            self.init_skills(db)
            self.init_context_imports(db)
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()
    def snapshot(self):
        with self.lock, self.connect() as db:
            return {**self.integration_snapshot(db), **self.skill_snapshot(db), **self.context_import_snapshot(db), 'schema_version': 3, 'app_version': VERSION, 'exported_at': now(),
                    'projects': [dict(r) for r in db.execute('SELECT * FROM projects ORDER BY id')],
                    'tasks': [self.task_record(dict(r)) for r in db.execute('SELECT * FROM tasks ORDER BY id')],
                    'events': [dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC')]}
    def event(self, db, pid, kind, actor, text, evidence=''):
        db.execute('INSERT INTO events(project_id,kind,actor,text,evidence,created_at) VALUES(?,?,?,?,?,?)',
                   (pid, kind, actor, text, evidence, now()))
    def project_values(self, obj):
        values = [field(obj,'name',120,True), field(obj,'company',120,True), field(obj,'goal',4000),
                  field(obj,'status',30,True), field(obj,'priority',30,True), field(obj,'next_action',4000),
                  link(field(obj,'repository',1000)), field(obj,'branch',200),
                  link(field(obj,'documents',1000)), field(obj,'environment',1000), field(obj,'phase',30)]
        if values[3] not in ('activo','pausado','completado') or values[4] not in ('alta','media','baja'):
            raise ValueError('Estado o prioridad inválidos.')
        if values[10] not in ('','Diseño','MVP','Desarrollo','Pruebas','Listo'): raise ValueError('Fase inválida.')
        return values
    def task_record(self, row):
        for key in ('dependencies', 'skill_refs'):
            try:
                row[key] = json.loads(row.get(key, '[]') or '[]') if isinstance(row.get(key), str) else row.get(key, [])
            except (TypeError, json.JSONDecodeError):
                row[key] = []
        return row
    def _id_list(self, obj, key, limit=50):
        value = obj.get(key, [])
        if isinstance(value, str):
            try:
                value = json.loads(value) if value.strip().startswith('[') else [int(x.strip()) for x in value.split(',') if x.strip()]
            except (ValueError, json.JSONDecodeError):
                raise ValueError(f'Lista inválida: {key}.')
        if not isinstance(value, list) or len(value) > limit or any(type(x) is not int or x <= 0 for x in value):
            raise ValueError(f'Lista inválida: {key}.')
        if len(value) != len(set(value)):
            raise ValueError(f'La lista {key} contiene duplicados.')
        return value
    def _validate_dependencies(self, db, pid, rid, dependencies):
        if rid in dependencies:
            raise ValueError('Una tarea no puede depender de sí misma.')
        graph = {}
        rows = db.execute('SELECT id,project_id,dependencies FROM tasks').fetchall()
        for row in rows:
            if row['project_id'] == pid and row['id'] != rid:
                try: graph[row['id']] = json.loads(row['dependencies'] or '[]')
                except (TypeError, json.JSONDecodeError): graph[row['id']] = []
        available = set(graph)
        for dep in dependencies:
            row = db.execute('SELECT project_id FROM tasks WHERE id=?', (dep,)).fetchone()
            if not row or row['project_id'] != pid:
                raise ValueError(f'La dependencia #{dep} no existe en este proyecto.')
            if dep not in available:
                raise ValueError(f'La dependencia #{dep} no está disponible.')
        graph[rid or -1] = dependencies
        visiting, visited = set(), set()
        def visit(node):
            if node in visiting: raise ValueError('Las dependencias forman un ciclo.')
            if node in visited: return
            visiting.add(node)
            for dep in graph.get(node, []): visit(dep)
            visiting.remove(node); visited.add(node)
        for node in graph: visit(node)
    def task_values(self, obj, db=None, pid=None, rid=None):
        status = field(obj, 'status',30,True)
        if status not in STATUSES or type(obj.get('needs_me')) is not bool:
            raise ValueError('Estado o necesita atención inválidos.')
        evidence = field(obj,'evidence',4000)
        if status == 'completada' and not evidence:
            raise ValueError('Registra evidencia o un resultado verificable para completar una tarea.')
        dependencies = self._id_list(obj, 'dependencies')
        skills = self._id_list(obj, 'skill_refs', 20)
        ai_profile = field(obj, 'ai_profile', 40)
        role = field(obj, 'role', 40)
        environment = field(obj, 'execution_environment', 30) or 'development'
        if ai_profile and ai_profile not in SKILL_PROVIDERS:
            raise ValueError('Perfil de IA inválido para la tarea.')
        if role and role not in TASK_ROLES:
            raise ValueError('Rol de trabajo inválido.')
        if environment not in TASK_ENVIRONMENTS:
            raise ValueError('Entorno de ejecución inválido.')
        if db is not None and pid is not None:
            self._validate_dependencies(db, pid, rid, dependencies)
            if status == 'completada' and dependencies:
                incomplete = [dep for dep in dependencies if not db.execute('SELECT 1 FROM tasks WHERE id=? AND status=?', (dep, 'completada')).fetchone()]
                if incomplete:
                    raise ValueError('Completa primero las tareas previas: ' + ', '.join('#'+str(x) for x in incomplete))
            if skills:
                found = {r[0] for r in db.execute('SELECT id FROM skill_catalog WHERE id IN ('+','.join('?' for _ in skills)+')', skills)}
                if found != set(skills):
                    raise ValueError('Una skill seleccionada ya no está en el catálogo. Actualiza las recomendaciones.')
        pr = link(field(obj, 'pull_request', 1000))
        return [field(obj,'title',240,True), status, int(obj['needs_me']), field(obj,'owner',120),
                field(obj,'notes',4000), evidence, field(obj,'objective',2000), field(obj,'acceptance',3000),
                json.dumps(dependencies), ai_profile, role, json.dumps(skills), field(obj,'branch',200),
                field(obj,'commit_ref',200), pr, field(obj,'tests',3000), field(obj,'checkpoint',2000), environment]
    def save(self, kind, obj, rid=None):
        if not isinstance(obj,dict):
            raise ValueError('Se esperaba un objeto JSON.')
        with self.lock, self.connect() as db:
            if kind == 'projects':
                values = self.project_values(obj)
                if rid:
                    self.check_version(db,kind,rid,obj)
                    db.execute('UPDATE projects SET name=?,company=?,goal=?,status=?,priority=?,next_action=?,repository=?,branch=?,documents=?,environment=?,phase=?,updated_at=?,version=version+1 WHERE id=?', values+[now(),rid])
                else:
                    rid = db.execute('INSERT INTO projects(name,company,goal,status,priority,next_action,repository,branch,documents,environment,phase,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', values+[now()]).lastrowid
                self.event(db,rid,'nota','Usuario', 'Estado del proyecto actualizado.' if obj.get('version') else 'Proyecto creado.')
            elif kind == 'tasks':
                if rid:
                    old = self.check_version(db,kind,rid,obj)
                    pid = old['project_id']
                else:
                    pid = obj.get('project_id')
                    if type(pid) is not int or not db.execute('SELECT id FROM projects WHERE id=?',(pid,)).fetchone():
                        raise ValueError('Proyecto inexistente.')
                values = self.task_values(obj, db, pid, rid)
                columns = ('title','status','needs_me','owner','notes','evidence','objective','acceptance',
                           'dependencies','ai_profile','role','skill_refs','branch','commit_ref','pull_request',
                           'tests','checkpoint','execution_environment')
                if rid:
                    db.execute('UPDATE tasks SET '+','.join(c+'=?' for c in columns)+',updated_at=?,version=version+1 WHERE id=?',values+[now(),rid])
                else:
                    rid = db.execute('INSERT INTO tasks(project_id,'+','.join(columns)+',updated_at) VALUES('+','.join('?' for _ in range(len(columns)+2))+')',[pid]+values+[now()]).lastrowid
                db.execute('UPDATE projects SET updated_at=?,version=version+1 WHERE id=?',(now(),pid))
                self.event(db,pid,'nota','Usuario',f'Tarea #{rid}: {values[0]} → {values[1]}',values[5])
            elif kind == 'events':
                pid = obj.get('project_id')
                if type(pid) is not int or not db.execute('SELECT id FROM projects WHERE id=?',(pid,)).fetchone():
                    raise ValueError('Proyecto inexistente.')
                ekind = field(obj,'kind',30,True)
                if ekind not in KINDS:
                    raise ValueError('Tipo de actividad inválido.')
                self.event(db,pid,ekind,field(obj,'actor',120,True),field(obj,'text',8000,True),field(obj,'evidence',4000))
                db.execute('UPDATE projects SET updated_at=?,version=version+1 WHERE id=?',(now(),pid))
            else:
                raise ValueError('Recurso inválido.')
        return self.snapshot()
    def check_version(self, db, kind, rid, obj):
        row = db.execute(f'SELECT * FROM {kind} WHERE id=?',(rid,)).fetchone()
        if not row:
            raise ValueError('Registro inexistente.')
        if type(obj.get('version')) is not int or obj['version'] != row['version']:
            raise RuntimeError('Este registro cambió en otra ventana. Recarga antes de guardar.')
        return row
    def import_snapshot(self, obj):
        if not isinstance(obj,dict) or obj.get('schema_version') not in (1, 2, 3):
            raise ValueError('Formato de respaldo incompatible.')
        projects, tasks, events = (obj.get(k) for k in ('projects','tasks','events'))
        if not all(isinstance(x,list) for x in (projects,tasks,events)) or sum(map(len,(projects,tasks,events))) > 20000:
            raise ValueError('Respaldo inválido o demasiado grande.')
        ids = set()
        for p in projects:
            if not isinstance(p,dict):
                raise ValueError('Proyecto inválido en respaldo.')
            for key in ('name','company','goal','status','priority','next_action','repository','branch','documents','environment','updated_at','version'):
                if key not in p:
                    raise KeyError(key)
            self.project_values(p)
            if type(p.get('id')) is not int or p['id'] <= 0 or p['id'] in ids:
                raise ValueError('Identificador de proyecto inválido o duplicado.')
            ids.add(p['id'])
        normalized_tasks = []
        for collection in (tasks,events):
            seen = set()
            for r in collection:
                if not isinstance(r,dict) or type(r.get('id')) is not int or r['id'] <= 0 or r['id'] in seen or r.get('project_id') not in ids:
                    raise ValueError('Referencias inválidas o duplicadas en respaldo.')
                seen.add(r['id'])
                if collection is tasks:
                    normalized = dict(r)
                    if type(r.get('needs_me')) not in (bool,int) or r['needs_me'] not in (0,1):
                        raise ValueError('Indicador de atención inválido.')
                    normalized['needs_me'] = bool(r['needs_me'])
                    defaults = {'objective':'','acceptance':'','dependencies':[],'ai_profile':'','role':'',
                                'skill_refs':[],'branch':'','commit_ref':'','pull_request':'','tests':'',
                                'checkpoint':'','execution_environment':'development'}
                    for key, value in defaults.items(): normalized.setdefault(key, value)
                    self.task_values(normalized)
                    normalized['dependencies'] = self._id_list(normalized, 'dependencies')
                    normalized['skill_refs'] = self._id_list(normalized, 'skill_refs', 20)
                    normalized_tasks.append(normalized)
                else:
                    if field(r,'kind',30,True) not in KINDS:
                        raise ValueError('Tipo de evento inválido.')
                    field(r,'actor',120,True); field(r,'text',8000,True); field(r,'evidence',4000)
        for collection in (projects,tasks,events):
            for r in collection:
                stamp = field(r,'created_at' if collection is events else 'updated_at',60,True)
                datetime.fromisoformat(stamp)
                if collection is not events and (type(r.get('version')) is not int or r['version'] < 1):
                    raise ValueError('Versión de registro inválida.')
        integrations = self.validate_integrations(obj,ids)
        skill_data = self.validate_skill_snapshot(obj)
        context_data = self.validate_context_import_snapshot(obj,ids)
        catalog_ids = {row['id'] for row in skill_data['skills']}
        task_by_id = {row['id']: row for row in normalized_tasks}
        graph = {}
        for row in normalized_tasks:
            graph[row['id']] = row['dependencies']
            for dep in row['dependencies']:
                target = task_by_id.get(dep)
                if not target or target['project_id'] != row['project_id']:
                    raise ValueError(f'La dependencia #{dep} no existe en el mismo proyecto.')
                if row['status'] == 'completada' and target['status'] != 'completada':
                    raise ValueError('Un respaldo marca como completada una tarea con dependencias pendientes.')
            if any(skill_id not in catalog_ids for skill_id in row['skill_refs']):
                raise ValueError('Una tarea referencia skills que no aparecen en el respaldo.')
        visiting, visited = set(), set()
        def visit_task(task_id):
            if task_id in visiting: raise ValueError('Las dependencias del respaldo forman un ciclo.')
            if task_id in visited: return
            visiting.add(task_id)
            for dep in graph.get(task_id, []): visit_task(dep)
            visiting.remove(task_id); visited.add(task_id)
        for task_id in graph: visit_task(task_id)
        with self.lock, self.connect() as db:
            # Preserve the previous state before replacing any data.
            backup = self.path.parent / ('before-import-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3) + '.json')
            backup.write_text(json.dumps(self.snapshot(),ensure_ascii=False,indent=2),encoding='utf-8')
            for table in ('context_import_items','context_imports','imported_items','project_sources','accounts','events','tasks','skill_catalog','skill_sources','projects'):
                db.execute('DELETE FROM '+table)
            for table, rows in (('projects',projects),('tasks',normalized_tasks),('events',events)):
                cols = [r[1] for r in db.execute('PRAGMA table_info('+table+')')]
                for row in rows:
                    values = []
                    for c in cols:
                        value = row.get(c)
                        if table == 'tasks' and c in ('dependencies','skill_refs'):
                            value = json.dumps(row.get(c, []))
                        elif value is None and c in ('objective','acceptance','ai_profile','role','branch','commit_ref','pull_request','tests','checkpoint'):
                            value = ''
                        elif value is None and c == 'execution_environment': value = 'development'
                        elif value is None and c in ('dependencies','skill_refs'): value = '[]'
                        values.append(value)
                    db.execute('INSERT INTO '+table+' ('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',values)
            for table, rows in integrations.items():
                cols = [r[1] for r in db.execute('PRAGMA table_info('+table+')')]
                for row in rows:
                    db.execute('INSERT INTO '+table+' ('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',[row[c] for c in cols])
            for row in skill_data['skill_sources']:
                db.execute('INSERT INTO skill_sources(id,label,provider,path,enabled) VALUES(?,?,?,?,?)',
                           (row['id'],row['label'],row['provider'],row['path'],int(row['enabled'])))
            for row in skill_data['skills']:
                db.execute('''INSERT INTO skill_catalog(id,source_id,relative_path,name,description,tags,digest,modified_at)
                              VALUES(?,?,?,?,?,?,?,?)''',
                           (row['id'],row['source_id'],row['relative_path'],row['name'],row['description'],
                            json.dumps(row['tags'],ensure_ascii=False),row['digest'],row['modified_at']))
            for row in context_data['context_imports']:
                db.execute('INSERT INTO context_imports(id,project_id,provider,source_label,source_ref,payload_json,created_at) VALUES(?,?,?,?,?,?,?)',
                           (row['id'],row['project_id'],row['provider'],row['source_label'],row['source_ref'],row['payload_json'],row['created_at']))
            for row in context_data['context_import_items']:
                db.execute('INSERT INTO context_import_items(id,import_id,project_id,provider,kind,item_key,text,certainty,evidence,digest,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                           (row['id'],row['import_id'],row['project_id'],row['provider'],row['kind'],row['item_key'],row['text'],row['certainty'],row['evidence'],row['digest'],row['created_at']))
            prefs=skill_data['skill_preferences']
            db.execute('UPDATE skill_preferences SET enabled=?,mode=?,max_suggestions=? WHERE id=1',
                       (int(prefs['enabled']),prefs['mode'],prefs['max_suggestions']))
        return self.snapshot()
    def seed(self):
        with self.lock:
            if self.snapshot()['projects']:
                raise ValueError('Los ejemplos solo se cargan en una instalación vacía.')
            for name, company, goal in [('RIPO','Savetek','Ejemplo: organizar preview, exportaciones y publicación.'),('Planilla GT','Savetek','Ejemplo: validar reglas y cálculos de planilla.'),('Kehila / KNISSA','Savetek','Ejemplo: control de visitantes preautorizados.'),('Cognitia','Gammiatek','Ejemplo: definir primer juego y mediación IA.')]:
                snap = self.save('projects',dict(name=name,company=company,goal=goal,status='activo',priority='media',next_action='Verificar el estado real antes de trabajar.',environment='DEMO: información ilustrativa, sin verificar.'))
                pid = snap['projects'][-1]['id']
                self.save('tasks',dict(project_id=pid,title='Confirmar alcance y fuentes actuales',status='pendiente',needs_me=True,owner='Samuel',notes='Datos de demostración. No representa avances reales.',evidence=''))
        return self.snapshot()
    def ask(self, obj):
        if not isinstance(obj,dict) or type(obj.get('project_id')) is not int:
            raise ValueError('Selecciona un proyecto.')
        import unicodedata
        q = field(obj,'question',500,True)
        norm = lambda text: ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')
        snap = self.snapshot()
        p = next((p for p in snap['projects'] if p['id']==obj['project_id']),None)
        if not p:
            raise ValueError('Proyecto inexistente.')
        ts = [t for t in snap['tasks'] if t['project_id']==p['id']]
        es = [e for e in snap['events'] if e['project_id']==p['id']]
        nq = norm(q)
        if any(w in nq for w in ('sigue','proxim','siguiente')):
            answer = 'Próxima acción registrada: ' + (p['next_action'] or 'Sin registrar.')
            refs = ['Estado del proyecto, versión '+str(p['version'])]
        elif any(w in nq for w in ('bloque','atencion','necesita')):
            chosen = [t for t in ts if t['status']!='completada' and (t['status']=='bloqueada' or t['needs_me'])]
            answer = '\n'.join(f"#{t['id']} {t['title']} [{t['status']}] — {t['notes'] or 'Sin detalle'}" for t in chosen) or 'No hay bloqueos o solicitudes de atención registrados.'
            refs = [f"Tarea #{t['id']}" for t in chosen]
        elif 'decision' in nq:
            chosen = [e for e in es if e['kind']=='decision']
            answer = '\n'.join(f"{e['created_at']} — {e['text']}" for e in chosen) or 'No hay decisiones registradas.'
            refs = [f"Actividad #{e['id']}" for e in chosen]
        elif any(w in nq for w in ('ultimo','reciente','actividad')):
            chosen = es[:10]
            answer = '\n'.join(f"{e['created_at']} — {e['actor']}: {e['text']}" for e in chosen) or 'No hay actividad registrada.'
            refs = [f"Actividad #{e['id']}" for e in chosen]
        elif 'estado' in nq or 'resumen' in nq:
            answer = f"{p['name']}: {p['status']}. Objetivo: {p['goal'] or 'Sin registrar'}. {sum(t['status']=='completada' for t in ts)}/{len(ts)} tareas completadas. Próxima acción: {p['next_action'] or 'Sin registrar'}."
            refs = ['Estado del proyecto, versión '+str(p['version'])]
        else:
            stop = {'que','como','para','del','las','los','una','por','con','este','esta','hay','sobre'}
            words = [w.strip('¿?.,:;') for w in nq.split() if len(w.strip('¿?.,:;'))>2 and w not in stop]
            chosen = []
            for t in ts:
                if any(w in norm(t['title']+' '+t['notes']+' '+t['evidence']) for w in words):
                    chosen.append((f"Tarea #{t['id']}",t['title']+' — '+t['notes']+' — '+t['evidence']))
            for e in es:
                if any(w in norm(e['text']+' '+e['evidence']) for w in words):
                    chosen.append((f"Actividad #{e['id']}",e['text']+' — '+e['evidence']))
            chosen = chosen[:20]
            answer = '\n'.join(r+': '+text for r,text in chosen) or 'No encontré registros relacionados. Prueba «estado», «qué sigue», «bloqueos», «decisiones» o busca una palabra del trabajo.'
            refs = [r for r,_ in chosen]
        return {'answer':answer,'sources':refs,'mode':'local_lookup','notice':'Consulta local de registros; no es una respuesta generada por IA ni una verificación de fuentes externas.'}
    def context(self, pid):
        snap = self.snapshot()
        p = next((p for p in snap['projects'] if p['id']==pid),None)
        if not p:
            raise ValueError('Proyecto inexistente.')
        lines = [f"# {p['name']} — Estado maestro",f"\nÚltima actualización: {p['updated_at']}",f"Empresa: {p['company']}",f"Fase: {p['phase'] or 'Sin registrar'} | Estado: {p['status']} | Prioridad: {p['priority']}", '\n## Objetivo',p['goal'] or 'Sin registrar','\n## Próxima acción',p['next_action'] or 'Sin registrar','\n## Fuentes y entorno',f"Repositorio: {p['repository'] or 'Sin registrar'}",f"Rama: {p['branch'] or 'Sin registrar'}",f"Documentos: {p['documents'] or 'Sin registrar'}",f"Entorno: {p['environment'] or 'Sin registrar'}",'\n## Tareas']
        skill_by_id = {s['id']: s for s in snap['skills']}
        for t in snap['tasks']:
            if t['project_id']==pid:
                lines += [f"- #{t['id']} [{t['status']}] {t['title']} — {t['owner'] or 'Sin asignar'}" + (' | Requiere mi atención' if t['needs_me'] and t['status']!='completada' else ''),f"  Notas: {t['notes'] or '—'}",f"  Evidencia registrada: {t['evidence'] or 'Sin evidencia'}"]
                if t['objective']: lines.append(f"  Objetivo de tarea: {t['objective']}")
                if t['acceptance']: lines.append(f"  Criterios de aceptación: {t['acceptance']}")
                if t['dependencies']: lines.append('  Depende de: '+', '.join('#'+str(x) for x in t['dependencies']))
                if t['ai_profile'] or t['role']: lines.append(f"  IA/rol: {t['ai_profile'] or 'Sin asignar'} / {t['role'] or 'Sin asignar'}")
                if t['skill_refs']:
                    lines.append('  Skills seleccionados: '+', '.join(skill_by_id.get(x,{}).get('name','Skill #'+str(x)) for x in t['skill_refs']))
                if t['branch'] or t['commit_ref'] or t['pull_request']:
                    lines.append(f"  Git: rama {t['branch'] or '—'}; commit {t['commit_ref'] or '—'}; PR {t['pull_request'] or '—'}")
                if t['tests']: lines.append(f"  Pruebas: {t['tests']}")
                if t['checkpoint']: lines.append(f"  Punto de reanudación: {t['checkpoint']}")
        lines += ['\n## Decisiones y actividad reciente']
        evs = [e for e in snap['events'] if e['project_id']==pid]
        selected = [e for e in evs if e['kind']=='decision'] + [e for e in evs if e['kind']!='decision'][:30]
        for e in selected:
            lines += [f"- {e['created_at']} | {e['kind']} | {e['actor']}: {e['text']}",f"  Evidencia: {e['evidence'] or 'Sin evidencia'}"]
        from integrations import PROVIDERS
        lines += ['\n## Roles y fuentes IA seleccionadas']
        for source in snap['project_sources']:
            if source['project_id']==pid:
                account=next(a for a in snap['accounts'] if a['id']==source['account_id'])
                label,role=PROVIDERS[account['provider']]
                lines += [f"- {label} / {account['label']}: {role}. Estado: {bool(source['sync_state'])}; decisiones: {bool(source['sync_decisions'])}; perfil habilitado: {bool(account['enabled'])}."]
        lines += ['\n## Instrucciones para continuar','Lee las fuentes actuales antes de modificar. Este estado contiene registros del usuario, no verificaciones automáticas. Distingue propuestas, cambios implementados y resultados verificados. Respeta las ramas y entornos autorizados. Al finalizar, devuelve cambios, evidencias, bloqueos y próxima acción para registrarlos en Proyecta.']
        return '\n'.join(lines)+'\n'
    def task_context(self, tid):
        snap = self.snapshot()
        task = next((t for t in snap['tasks'] if t['id'] == tid), None)
        if not task: raise ValueError('Tarea inexistente.')
        project = next(p for p in snap['projects'] if p['id'] == task['project_id'])
        skills = {s['id']:s for s in snap['skills']}
        lines = [f"# Tarea #{task['id']}: {task['title']}", '', f"Proyecto: {project['name']} · {project['company']}",
                 f"Estado: {task['status']} · Entorno: {task['execution_environment']}",
                 f"Responsable: {task['owner'] or 'Sin asignar'} · IA: {task['ai_profile'] or 'Sin asignar'} · Rol: {task['role'] or 'Sin asignar'}",
                 '', '## Objetivo', task['objective'] or task['notes'] or 'Sin registrar',
                 '', '## Criterios de aceptación', task['acceptance'] or 'Sin registrar',
                 '', '## Dependencias', ', '.join('#'+str(x) for x in task['dependencies']) or 'Ninguna',
                 '', '## Punto de reanudación', task['checkpoint'] or 'Sin registrar',
                 '', '## Skills seleccionados']
        for sid in task['skill_refs']:
            skill=skills.get(sid)
            if skill: lines.append(f"- {skill['name']} ({skill['provider_label']}): {skill['description']} · {skill['path']}")
        if not task['skill_refs']: lines.append('Ninguno. El usuario puede consultar el Asesor de skills.')
        lines += ['', '## Repositorio y evidencia', f"Repositorio: {project['repository'] or 'Sin registrar'}",
                  f"Rama de proyecto: {project['branch'] or 'Sin registrar'}", f"Rama de tarea: {task['branch'] or 'Sin registrar'}",
                  f"Commit: {task['commit_ref'] or 'Sin registrar'}", f"Pull request: {task['pull_request'] or 'Sin registrar'}",
                  f"Pruebas: {task['tests'] or 'Sin registrar'}", f"Resultado/evidencia: {task['evidence'] or 'Sin registrar'}",
                  '', '## Decisiones pertinentes']
        decisions = [e for e in snap['events'] if e['project_id']==project['id'] and e['kind']=='decision']
        lines.extend('- '+e['text'] for e in decisions[:30])
        if not decisions: lines.append('Sin decisiones registradas.')
        lines += ['', '## Instrucciones', 'Implementa exclusivamente el alcance descrito. No afirmes que un cambio está completo sin evidencia. No cambies de rama, entorno, alcance o decisiones aprobadas sin registrarlo y solicitar revisión humana. Al finalizar, devuelve un resumen, archivos cambiados, rama/commit/PR, pruebas y bloqueos.']
        return '\n'.join(lines)+'\n'

class Handler(BaseHTTPRequestHandler):
    server_version = 'Proyecta/1.3'
    def log_message(self, fmt, *args):
        pass
    def headers_ok(self, write=False):
        if self.headers.get('Host') != self.server.authority:
            return False
        if write:
            origin = self.headers.get('Origin')
            return (not origin or origin == 'http://'+self.server.authority) and secrets.compare_digest(self.headers.get('X-Proyecta-Token',''),self.server.token)
        return True
    def respond(self, data, status=200, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(data,bytes):
            data = json.dumps(data,ensure_ascii=False).encode() if content_type.startswith('application/json') else data.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        if not self.headers_ok():
            return self.respond({'error':'Host no permitido.'},403)
        path = urlparse(self.path).path
        if path=='/api/state':
            return self.respond(self.server.store.snapshot())
        if path=='/api/session':
            return self.respond({'token':self.server.token,'version':VERSION})
        if path=='/api/skills/discover':
            return self.respond({'directories':self.server.store.discover_skill_directories()})
        if path.startswith('/api/context-import/prompt/'):
            try:
                provider=path.rsplit('/',1)[-1]
                return self.respond(self.server.store.context_import_prompt(provider),content_type='text/plain; charset=utf-8')
            except ValueError as e:
                return self.respond({'error':str(e)},400)
        if path=='/api/backup':
            return self.respond(self.server.store.snapshot(),filename='proyecta-backup.json')
        if path=='/api/export':
            buffer = io.BytesIO()
            snap = self.server.store.snapshot()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('proyecta-backup.json',json.dumps(snap,ensure_ascii=False,indent=2))
                for p in snap['projects']:
                    archive.writestr(f"proyecto-{p['id']}/PROJECT_STATUS.md",self.server.store.context(p['id']))
            return self.respond(buffer.getvalue(),content_type='application/zip',filename='proyecta-contextos.zip')
        if path.startswith('/api/context/'):
            try:
                pid = int(path.rsplit('/',1)[-1])
                return self.respond(self.server.store.context(pid),content_type='text/markdown; charset=utf-8',filename=f'PROJECT_STATUS_{pid}.md')
            except ValueError as e:
                return self.respond({'error':str(e)},404)
        if path.startswith('/api/context-dossier/'):
            try:
                pid=int(path.rsplit('/',1)[-1])
                return self.respond(self.server.store.context_dossier(pid),content_type='text/markdown; charset=utf-8',filename=f'EXPEDIENTE_TECNICO_{pid}.md')
            except ValueError as e:
                return self.respond({'error':str(e)},404)
        if path.startswith('/api/task-context/'):
            try:
                tid = int(path.rsplit('/',1)[-1])
                return self.respond(self.server.store.task_context(tid),content_type='text/markdown; charset=utf-8',filename=f'TASK_{tid}.md')
            except ValueError as e:
                return self.respond({'error':str(e)},404)
        if path.startswith('/api/prompt/'):
            try:
                pid,aid=map(int,path.split('/')[-2:])
                return self.respond(self.server.store.exchange_prompt(pid,aid),content_type='text/plain; charset=utf-8')
            except ValueError as e: return self.respond({'error':str(e)},400)
        files = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
        if path in files:
            mime = 'text/html' if path=='/' else 'application/javascript' if path.endswith('.js') else 'text/css'
            return self.respond((ROOT/'static'/files[path]).read_bytes(),content_type=mime+'; charset=utf-8')
        self.respond({'error':'No encontrado.'},404)
    def do_POST(self):
        self.mutate()
    def do_PUT(self):
        self.mutate()
    def mutate(self):
        if not self.headers_ok(write=True):
            return self.respond({'error':'Sesión local inválida. Recarga la página.'},403)
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= MAX_BODY:
                return self.respond({'error':'Tamaño de solicitud inválido (máximo 5 MB).'},413)
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                raise ValueError('Se requiere JSON.')
            obj = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            if path=='/api/context-import/preview' and self.command=='POST':
                return self.respond(self.server.store.preview_context_import(obj))
            if path=='/api/context-import/apply' and self.command=='POST':
                return self.respond(self.server.store.apply_context_import(obj))
            if path=='/api/exchange/preview' and self.command=='POST':
                return self.respond(self.server.store.preview_exchange(obj))
            if path=='/api/accounts' and self.command=='POST':
                return self.respond(self.server.store.save_account(obj))
            if path=='/api/skills/source' and self.command=='POST':
                return self.respond(self.server.store.save_skill_source(obj))
            if path=='/api/skills/source/delete' and self.command=='POST':
                return self.respond(self.server.store.delete_skill_source(obj))
            if path=='/api/skills/scan' and self.command=='POST':
                return self.respond(self.server.store.scan_skill_sources(obj))
            if path=='/api/skills/preferences' and self.command=='POST':
                return self.respond(self.server.store.save_skill_preferences(obj))
            if path=='/api/skills/recommend' and self.command=='POST':
                return self.respond(self.server.store.recommend_skills(obj))
            if path=='/api/sources' and self.command=='POST':
                return self.respond(self.server.store.save_sources(obj))
            if path=='/api/exchange/apply' and self.command=='POST':
                return self.respond(self.server.store.apply_exchange(obj))
            if path=='/api/ask' and self.command=='POST':
                return self.respond(self.server.store.ask(obj))
            if path=='/api/seed' and self.command=='POST':
                result = self.server.store.seed()
            elif path=='/api/import' and self.command=='POST':
                result = self.server.store.import_snapshot(obj)
                self.server.token = secrets.token_urlsafe(32)
            else:
                parts = path.strip('/').split('/')
                if len(parts) not in (2,3) or parts[0]!='api' or parts[1] not in ('projects','tasks','events'):
                    return self.respond({'error':'Ruta inválida.'},404)
                if (self.command=='POST' and len(parts)!=2) or (self.command=='PUT' and (len(parts)!=3 or parts[1]=='events')):
                    return self.respond({'error':'Método inválido.'},405)
                result = self.server.store.save(parts[1],obj,int(parts[2]) if len(parts)==3 else None)
            self.respond(result)
        except RuntimeError as e:
            self.respond({'error':str(e)},409)
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
            self.respond({'error':str(e)},400)
        except Exception:
            self.respond({'error':'No se pudo guardar. Revisa permisos y espacio del directorio de datos.'},500)

def make_server(store, port=8765):
    server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.authority = f'127.0.0.1:{server.server_port}'
    server.token = secrets.token_urlsafe(32)
    server.store = store
    return server

def main():
    parser = argparse.ArgumentParser(description='Proyecta: centro local de proyectos')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data-dir',type=Path,default=data_home())
    parser.add_argument('--no-browser',action='store_true')
    args = parser.parse_args()
    store = Store(args.data_dir/'proyecta.sqlite3')
    try:
        server = make_server(store,args.port)
    except OSError as e:
        parser.exit(1,f'No se pudo abrir el puerto {args.port}: {e}. Prueba --port 8766.\n')
    url = 'http://'+server.authority
    print(f'Proyecta {VERSION}\nAbre {url}\nDatos: {store.path}\nCtrl+C para detener.',flush=True)
    if not args.no_browser:
        threading.Timer(.5,lambda:webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=='__main__':
    main()
