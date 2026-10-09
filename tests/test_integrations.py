import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import Store
from mcp_bridge import serve

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'db')
        self.store.save('projects',dict(name='RIPO',company='Savetek',status='activo',priority='alta',next_action='Anterior'))
        self.store.save_account(dict(provider='claude',label='Samuel',workspace='Trabajo',enabled=True))
        self.set_sources(True,True)
        self.obj=dict(project_id=1,account_id=1,summary={'schema':'proyecta.summary.v1','source_ref':'chat-123','state':{'next_action':'Probar exports','latest_progress':'Preview implementado, pendiente de prueba'},'decisions':['No modificar main']})
    def tearDown(self):self.temp.cleanup()
    def set_sources(self,s,d):
        return self.store.save_sources(dict(project_id=1,version=self.store.snapshot()['projects'][0]['version'],sources=[dict(account_id=1,sync_state=s,sync_decisions=d)]))
    def apply(self,obj=None):
        obj=obj or self.obj;preview=self.store.preview_exchange(obj)
        return self.store.apply_exchange(dict(obj,version=preview['version'],selected=[i['digest'] for i in preview['items'] if i['allowed']]))
    def test_selection_idempotency_and_provenance(self):
        snap=self.apply();self.assertEqual(snap['projects'][0]['next_action'],'Probar exports')
        self.assertEqual(sum(e['kind']=='decision' for e in snap['events']),1)
        self.assertIn('Claude · Samuel',[e['actor'] for e in snap['events']])
        self.assertEqual(snap['events'],self.apply()['events'])
        self.assertEqual(Store(self.store.path).snapshot()['imported_items'],snap['imported_items'])
    def test_decisions_only_does_not_replace_state(self):
        self.set_sources(False,True);snap=self.apply()
        self.assertEqual(snap['projects'][0]['next_action'],'Anterior')
        preview=self.store.preview_exchange(self.obj)
        forbidden=next(i['digest'] for i in preview['items'] if not i['allowed'])
        with self.assertRaises(ValueError):self.store.apply_exchange(dict(self.obj,version=preview['version'],selected=[forbidden]))
    def test_stale_preview_is_atomic(self):
        preview=self.store.preview_exchange(self.obj)
        self.store.save('events',dict(project_id=1,kind='decision',actor='Usuario',text='Cambio simultáneo'))
        before=self.store.snapshot()
        with self.assertRaises(RuntimeError):self.store.apply_exchange(dict(self.obj,version=preview['version'],selected=[i['digest'] for i in preview['items']]))
        self.assertEqual(before['events'],self.store.snapshot()['events'])
    def test_full_conversations_are_rejected_without_storage(self):
        for summary in ({'conversations':['secret']},dict(self.obj['summary'],messages=['secret']),dict(self.obj['summary'],state={'repository':'https://evil.test'})):
            with self.assertRaises(ValueError):self.store.preview_exchange(dict(self.obj,summary=summary))
        self.assertFalse(self.store.snapshot()['imported_items'])
    def test_disabled_or_unselected_account_is_rejected(self):
        self.store.save_account(dict(id=1,provider='claude',label='Samuel',enabled=False))
        with self.assertRaises(ValueError):self.store.preview_exchange(self.obj)
    def test_partial_selection(self):
        preview=self.store.preview_exchange(self.obj)
        snap=self.store.apply_exchange(dict(self.obj,version=preview['version'],selected=[preview['items'][-1]['digest']]))
        self.assertEqual(snap['projects'][0]['next_action'],'Anterior')
        self.assertEqual(len(snap['imported_items']),1)
    def test_backup_restore_profiles_and_old_backup(self):
        self.apply();snap=self.store.snapshot();self.store.import_snapshot(snap)
        for key in ('accounts','project_sources','imported_items'):self.assertEqual(snap[key],self.store.snapshot()[key])
        bad=copy.deepcopy(snap);bad['accounts'][0]['provider']='invalid'
        with self.assertRaises(ValueError):self.store.import_snapshot(bad)
        self.assertEqual(snap['accounts'],self.store.snapshot()['accounts'])
        for key in ('accounts','project_sources','imported_items'):del snap[key]
        self.store.import_snapshot(snap);self.assertEqual(self.store.snapshot()['accounts'],[])
    def test_mcp_readonly_and_pinned_write(self):
        def run(messages,writable=False):
            stdout=io.StringIO()
            with patch('sys.stdin',io.StringIO(''.join(json.dumps(m)+'\n' for m in messages))),patch('sys.stdout',stdout):serve(self.store,1,1,writable)
            return [json.loads(l) for l in stdout.getvalue().splitlines()]
        response=run([{'id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},{'id':2,'method':'tools/list'}])
        self.assertEqual(response[0]['result']['protocolVersion'],'2025-06-18')
        self.assertNotIn('apply_summary',[t['name'] for t in response[1]['result']['tools']])
        self.assertTrue(run([{'id':3,'method':'tools/call','params':{'name':'apply_summary','arguments':{}}}])[0]['result']['isError'])
        preview=self.store.preview_exchange(self.obj)
        response=run([{'id':4,'method':'tools/call','params':{'name':'apply_summary','arguments':dict(summary=self.obj['summary'],version=preview['version'],selected=[preview['items'][-1]['digest']])}}],True)
        self.assertNotIn('isError',response[0]['result'])

from test_app import HttpTests as _HttpTests
class IntegrationHttpTests(unittest.TestCase):
    setUp = _HttpTests.setUp
    tearDown = _HttpTests.tearDown
    request = _HttpTests.request
    def test_exchange_routes_and_security(self):
        self.request('/api/projects',dict(name='RIPO',company='Savetek',status='activo',priority='alta'))
        self.assertEqual(self.request('/api/accounts',dict(provider='chatgpt_business',label='Business',enabled=True))[0],200)
        p=self.store.snapshot()['projects'][0]
        self.assertEqual(self.request('/api/sources',dict(project_id=1,version=p['version'],sources=[dict(account_id=1,sync_state=True,sync_decisions=True)]))[0],200)
        obj=dict(project_id=1,account_id=1,summary={'schema':'proyecta.summary.v1','state':{'next_action':'Validar'},'decisions':['No tocar main']})
        code,body,_=self.request('/api/exchange/preview',obj);self.assertEqual(code,200);preview=json.loads(body)
        payload=dict(obj,version=preview['version'],selected=[i['digest'] for i in preview['items']])
        self.assertEqual(self.request('/api/exchange/apply',payload,headers={'X-Proyecta-Token':''})[0],403)
        self.assertEqual(self.request('/api/exchange/apply',payload)[0],200)
        self.assertEqual(self.request('/api/exchange/apply',payload)[0],409)
        self.assertEqual(self.request('/api/prompt/1/1')[0],200)
        self.assertEqual(self.request('/api/prompt/1/999')[0],400)

del _HttpTests
