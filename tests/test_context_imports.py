import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Store


def payload():
    return {
        'schema': 'proyecta.context.v1',
        'project': {'name': 'Atlas', 'company': 'Savetek', 'goal': 'Importar proyectos',
                    'status': 'activo', 'phase': 'MVP', 'next_action': 'Revisar componentes',
                    'repository': 'https://github.com/acme/atlas', 'branch': 'feature/import',
                    'documents': '', 'environment': 'Python'},
        'design': {'functional': 'Importar con revisión humana.', 'technical': 'SQLite con huellas.'},
        'components': [{'name': 'Parser', 'status': 'parcial', 'description': 'Lee el formato normalizado.',
                        'evidence': 'src/importer.py'}],
        'decisions': ['Las tareas importadas empiezan pendientes.'],
        'backlog': [{'title': 'Añadir pantalla de revisión', 'objective': 'Importar proyectos',
                     'acceptance': 'Se revisan los elementos antes de guardarlos.', 'priority': 'alta',
                     'dependencies': []}],
        'tests': [{'name': 'Prueba declarada', 'result': 'Pasa según la fuente', 'evidence': 'CI #12', 'date': ''}],
        'risks': ['Falta probar archivos grandes.'], 'latest_progress': 'Se completó el parser.'}


class ContextImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'data.sqlite3')

    def tearDown(self):
        self.temp.cleanup()

    def preview(self, project_id=None, data=None):
        return self.store.preview_context_import({
            'project_id': project_id, 'provider': 'claude', 'source_label': 'Atlas en Claude',
            'source_ref': 'https://claude.ai/project/atlas', 'payload': data or payload()})

    def apply(self, preview, selected=None):
        selected = selected or [x['digest'] for x in preview['items']]
        return self.store.apply_context_import({
            'project_id': preview['project_id'], 'version': preview['version'],
            'provider': preview['provider'], 'source_label': preview['source_label'],
            'source_ref': preview['source_ref'], 'payload': preview['payload'], 'selected': selected})

    def test_create_project_imports_provenance_and_pending_tasks(self):
        preview = self.preview()
        result = self.apply(preview)
        state = result['state']
        self.assertEqual(result['tasks_created'], 1)
        self.assertEqual(state['projects'][0]['name'], 'Atlas')
        self.assertEqual(state['tasks'][0]['status'], 'pendiente')
        self.assertTrue(all(row['certainty'] == 'declarado_en_fuente' for row in state['context_import_items']))
        dossier = self.store.context_dossier(result['project_id'])
        for phrase in ('Procedencia y certeza', 'declaradas por la fuente', 'Diseño funcional',
                       'Desarrollo esperado', 'Pruebas declaradas', 'Falta probar archivos grandes.'):
            self.assertIn(phrase, dossier)

    def test_new_project_uses_only_approved_project_metadata(self):
        preview = self.preview()
        selected = [x['digest'] for x in preview['items'] if not (x['kind'] == 'project' and x['key'] == 'repository')]
        result = self.apply(preview, selected)
        project = result['state']['projects'][0]
        self.assertEqual(project['name'], 'Atlas')
        self.assertEqual(project['repository'], '')
        no_name = [x['digest'] for x in preview['items'] if not (x['kind'] == 'project' and x['key'] == 'name')]
        with self.assertRaisesRegex(ValueError, 'seleccionar su nombre'):
            self.apply(self.preview(), no_name)

    def test_existing_project_partial_selection_and_deduplication(self):
        project = self.store.save('projects', {'name': 'Atlas actual', 'company': 'Savetek', 'goal': 'Actual',
            'status': 'activo', 'priority': 'media', 'next_action': 'Seguir', 'repository': '', 'branch': ''})['projects'][0]
        preview = self.preview(project['id'])
        project_name = next(x for x in preview['items'] if x['kind'] == 'project' and x['key'] == 'name')
        decision = next(x for x in preview['items'] if x['kind'] == 'decision')
        self.assertEqual(project_name['current'], 'Atlas actual')
        self.apply(preview, [project_name['digest'], decision['digest']])
        updated = self.store.snapshot()
        self.assertEqual(updated['projects'][0]['name'], 'Atlas')
        self.assertEqual(updated['tasks'], [])
        stored_payload = json.loads(updated['context_imports'][0]['payload_json'])
        self.assertEqual([x['digest'] for x in stored_payload['accepted_items']],
                         [project_name['digest'], decision['digest']])
        self.assertNotIn('tests', stored_payload)
        again = self.preview(project['id'])
        self.assertTrue(next(x for x in again['items'] if x['digest'] == decision['digest'])['duplicate'])

    def test_stale_project_review_and_invalid_payload_are_rejected(self):
        project = self.store.save('projects', {'name': 'Atlas', 'company': 'Savetek', 'goal': '', 'status': 'activo',
            'priority': 'media', 'next_action': '', 'repository': '', 'branch': ''})['projects'][0]
        preview = self.preview(project['id'])
        self.store.save('projects', dict(project, name='Cambio concurrente'), project['id'])
        with self.assertRaisesRegex(RuntimeError, 'cambió durante la revisión'):
            self.apply(preview)
        bad = copy.deepcopy(payload())
        bad['project']['repository'] = 'javascript:alert(1)'
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            self.preview(data=bad)
        bad = payload(); bad['unknown'] = 'campo'
        with self.assertRaisesRegex(ValueError, 'no admitidos'):
            self.preview(data=bad)

    def test_a_to_b_to_a_is_a_new_historical_change(self):
        project = self.store.save('projects', {'name': 'Inicio', 'company': 'Savetek', 'goal': '', 'status': 'activo',
            'priority': 'media', 'next_action': '', 'repository': '', 'branch': ''})['projects'][0]
        first = self.preview(project['id'])
        name_a = next(x for x in first['items'] if x['kind'] == 'project' and x['key'] == 'name')
        self.apply(first, [name_a['digest']])
        data_b = payload(); data_b['project']['name'] = 'Borealis'
        second = self.preview(project['id'], data_b)
        name_b = next(x for x in second['items'] if x['kind'] == 'project' and x['key'] == 'name')
        self.apply(second, [name_b['digest']])
        third = self.preview(project['id'])
        reversion = next(x for x in third['items'] if x['kind'] == 'project' and x['key'] == 'name')
        self.assertFalse(reversion['duplicate'])
        self.apply(third, [reversion['digest']])
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot['projects'][0]['name'], 'Atlas')
        self.assertEqual(len([x for x in snapshot['context_import_items'] if x['item_key'] == 'name']), 3)

    def test_import_records_survive_backup_roundtrip(self):
        preview = self.preview()
        original = self.apply(preview)['state']
        restored = self.store.import_snapshot(original)
        self.assertEqual(len(restored['context_imports']), 1)
        self.assertEqual(len(restored['context_import_items']), len(original['context_import_items']))


if __name__ == '__main__':
    unittest.main()
