import copy
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
import io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Store, make_server

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'data.sqlite3')
        self.p=dict(name='Proyecto áé',company='Savetek',goal='MVP',status='activo',priority='alta',next_action='Probar',repository='https://example.com/repo',branch='dev')
        self.store.save('projects',self.p)
    def tearDown(self):
        self.temp.cleanup()
    def task(self,**changes):
        obj=dict(project_id=1,title='Exportación XLSX',status='pendiente',needs_me=True,owner='Samuel',notes='Revisar archivo',evidence='')
        obj.update(changes)
        return obj
    def test_persistence_after_reopen(self):
        self.store.save('tasks',self.task())
        reopened=Store(self.store.path).snapshot()
        self.assertEqual(reopened['projects'][0]['name'],'Proyecto áé')
        self.assertEqual(len(reopened['tasks']),1)
        self.assertEqual(len(reopened['events']),2)
    def test_completion_requires_evidence(self):
        with self.assertRaises(ValueError): self.store.save('tasks',self.task(status='completada'))
        snap=self.store.save('tasks',self.task(status='completada',evidence='Prueba #14: archivo abierto; 200 filas.'))
        self.assertEqual(snap['tasks'][0]['status'],'completada')
    def test_stale_edit_is_rejected(self):
        old=self.store.snapshot()['projects'][0]
        first=dict(old,name='Nuevo')
        self.store.save('projects',first,1)
        with self.assertRaises(RuntimeError): self.store.save('projects',old,1)
        self.assertEqual(self.store.snapshot()['projects'][0]['name'],'Nuevo')
    def test_roundtrip_and_preimport_backup(self):
        self.store.save('tasks',self.task())
        original=self.store.snapshot()
        p=dict(original['projects'][0],name='Otro')
        self.store.save('projects',p,1)
        result=self.store.import_snapshot(original)
        for key in ('projects','tasks','events'):self.assertEqual(result[key],original[key])
        backups=list(Path(self.temp.name).glob('before-import-*.json'))
        self.assertEqual(len(backups),1)
        self.assertEqual(json.loads(backups[0].read_text())['projects'][0]['name'],'Otro')
    def test_invalid_import_cannot_delete_state(self):
        before=self.store.snapshot()
        bad=copy.deepcopy(before)
        bad['tasks']=[dict(id=1,project_id=999)]
        with self.assertRaises(ValueError): self.store.import_snapshot(bad)
        self.assertEqual(self.store.snapshot()['projects'],before['projects'])
        bad=copy.deepcopy(before);del bad['projects'][0]['branch']
        with self.assertRaises(KeyError): self.store.import_snapshot(bad)
        self.assertEqual(self.store.snapshot()['projects'],before['projects'])
    def test_dangerous_url_rejected(self):
        for url in ('javascript:alert(1)','file:///etc/passwd','https:///missing-host'):
            with self.assertRaises(ValueError):self.store.save('projects',dict(self.p,repository=url))
    def test_task_cannot_attach_to_missing_project(self):
        with self.assertRaises(ValueError):self.store.save('tasks',self.task(project_id=999))
    def test_context_contains_decisions_evidence_and_constraints(self):
        self.store.save('events',dict(project_id=1,kind='decision',actor='Samuel',text='No modificar main.',evidence='Autorización registrada.'))
        self.store.save('tasks',self.task(status='completada',evidence='200 filas verificadas.'))
        text=self.store.context(1)
        self.assertIn('No modificar main.',text)
        self.assertIn('200 filas verificadas.',text)
        self.assertIn('Rama: dev',text)
    def test_local_query_uses_only_registered_sources(self):
        self.store.save('tasks',self.task(status='bloqueada'))
        result=self.store.ask(dict(project_id=1,question='¿Qué está bloqueado?'))
        self.assertIn('Exportación XLSX',result['answer'])
        self.assertEqual(result['sources'],['Tarea #1'])
        result=self.store.ask(dict(project_id=1,question='¿Qué sigue?'))
        self.assertIn('Probar',result['answer'])
        result=self.store.ask(dict(project_id=1,question='ornitorrinco'))
        self.assertEqual(result['sources'],[])
    def test_parallel_writes_have_complete_ledger(self):
        errors=[]
        def write(i):
            try:self.store.save('tasks',self.task(title=f'Tarea {i}'))
            except Exception as e:errors.append(e)
        threads=[threading.Thread(target=write,args=(i,)) for i in range(12)]
        for t in threads:t.start()
        for t in threads:t.join()
        snap=self.store.snapshot()
        self.assertFalse(errors)
        self.assertEqual(len(snap['tasks']),12)
        self.assertEqual(len(snap['events']),13)

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'db.sqlite3')
        self.server=make_server(self.store,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://'+self.server.authority
        self.token=self.server.token
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,data=None,headers=None,method=None):
        h={'Content-Type':'application/json','X-Proyecta-Token':self.token}
        h.update(headers or {})
        req=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers=h,method=method)
        try:
            r=urllib.request.urlopen(req)
            return r.status,r.read(),r.headers
        except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
    def test_browser_assets_and_json(self):
        for path in ('/','/app.js','/style.css','/api/session','/api/state'):
            status,body,headers=self.request(path)
            self.assertEqual(status,200)
            self.assertTrue(body)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertEqual(self.request('/../../app.py')[0],404)
    def test_cross_origin_and_host_protection(self):
        self.assertEqual(self.request('/api/seed',{},headers={'X-Proyecta-Token':''})[0],403)
        self.assertEqual(self.request('/api/seed',{},headers={'Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.request('/api/state',headers={'Host':'evil.example'})[0],403)
    def test_seed_export_restore_and_stale_session(self):
        status,body,_=self.request('/api/seed',{})
        self.assertEqual(status,200)
        snap=json.loads(body)
        self.assertEqual(len(snap['projects']),4)
        self.assertEqual(self.request('/api/seed',{})[0],400)
        status,body,_=self.request('/api/export')
        self.assertEqual(status,200)
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            self.assertEqual(len(z.namelist()),5)
            self.assertIn('DEMO',z.read('proyecto-1/PROJECT_STATUS.md').decode())
        self.assertEqual(self.request('/api/import',snap)[0],200)
        self.assertEqual(self.request('/api/seed',{})[0],403)
        _,body,_=self.request('/api/session');self.token=json.loads(body)['token']
        self.assertEqual(self.request('/api/ask',dict(project_id=1,question='estado'))[0],200)
    def test_invalid_requests_and_stale_edits(self):
        self.assertEqual(self.request('/api/projects',{})[0],400)
        self.assertEqual(self.request('/api/projects',dict(name='MVP',company='S',status='activo',priority='alta'))[0],200)
        old=self.store.snapshot()['projects'][0]
        self.assertEqual(self.request('/api/projects/1',dict(old,name='Primero'),method='PUT')[0],200)
        self.assertEqual(self.request('/api/projects/1',dict(old,name='Segundo'),method='PUT')[0],409)
        self.assertEqual(self.request('/api/ask',dict(project_id=404,question='estado'))[0],400)

if __name__=='__main__':unittest.main()
