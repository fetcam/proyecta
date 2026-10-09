import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Store


class SkillAdvisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'proyecta.sqlite3')
        self.store.save('projects', dict(name='Proyecta', company='Savetek', goal='Software',
                                         status='activo', priority='alta', next_action='Implementar'))
        self.skills = self.root / 'skills'
        self.skills.mkdir()
        (self.skills / 'python-testing').mkdir()
        (self.skills / 'python-testing' / 'SKILL.md').write_text(
            '---\nname: Python testing\ndescription: Escribe pruebas para aplicaciones Python.\ntags:\n  - python\n  - testing\n---\nNo se debe guardar el cuerpo completo.\n', encoding='utf-8')
        (self.skills / 'design').mkdir()
        (self.skills / 'design' / 'SKILL.md').write_text(
            '---\nname: Diseño visual\ndescription: Diseño de interfaces y experiencia.\ntags: [ui, visual]\n---\nTexto interno.\n', encoding='utf-8')
        self.source = self.store.save_skill_source(dict(label='Skills locales', provider='codex', path=str(self.skills)))['skill_sources'][0]

    def tearDown(self):
        self.temp.cleanup()

    def test_scan_indexes_metadata_and_recommendation_explains_matches(self):
        result = self.store.scan_skill_sources()
        self.assertEqual(result['scan']['skills'], 2)
        self.assertNotIn('No se debe guardar el cuerpo completo', json.dumps(result))
        recommendations = self.store.recommend_skills(dict(title='Agregar pruebas Python', objective='testing Python', provider='codex'))
        self.assertEqual(recommendations['items'][0]['name'], 'Python testing')
        self.assertIn('etiquetas', recommendations['items'][0]['reason'])
        self.assertIn('no instala ni ejecuta', recommendations['notice'])

    def test_scan_preserves_ids_and_source_delete_clears_task_associations(self):
        first = self.store.scan_skill_sources()['skills']
        skill_id = next(s['id'] for s in first if s['name'] == 'Python testing')
        self.store.save('tasks', dict(project_id=1, title='Pruebas Python', status='pendiente', needs_me=False,
                                      owner='Codex', notes='', evidence='', skill_refs=[skill_id]))
        scanned = self.store.scan_skill_sources()['skills']
        self.assertEqual(next(s['id'] for s in scanned if s['name'] == 'Python testing'), skill_id)
        self.store.delete_skill_source(dict(id=self.source['id']))
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot['tasks'][0]['skill_refs'], [])
        self.assertIn('eliminada', snapshot['events'][0]['text'])

    def test_preferences_are_bounded_and_provider_scoped(self):
        self.store.scan_skill_sources()
        self.store.save_skill_preferences(dict(enabled=True, mode='on_task_edit', max_suggestions=2))
        result = self.store.recommend_skills(dict(title='Diseño visual UI', provider='chatgpt_work', limit=3))
        self.assertEqual(len(result['items']), 0)
        self.assertEqual(self.store.snapshot()['skill_preferences']['mode'], 'on_task_edit')
        with self.assertRaises(ValueError):
            self.store.save_skill_preferences(dict(enabled=True, mode='always', max_suggestions=10))

    def test_symlink_skill_is_skipped(self):
        target = self.root / 'outside.md'
        target.write_text('---\nname: Link\ndescription: Not followed\n---\n', encoding='utf-8')
        (self.skills / 'linked').mkdir()
        (self.skills / 'linked' / 'SKILL.md').symlink_to(target)
        result = self.store.scan_skill_sources()
        self.assertEqual(result['scan']['skills'], 2)
        self.assertGreaterEqual(result['scan']['skipped'], 1)

    def test_discovery_lists_only_existing_conventional_directories(self):
        common = self.root / 'home' / '.agents' / 'skills'
        common.mkdir(parents=True)
        claude = self.root / 'home' / '.claude' / 'skills'
        claude.mkdir(parents=True)
        with patch('skills.Path.home', return_value=self.root / 'home'):
            found = self.store.discover_skill_directories()
        self.assertEqual({item['provider'] for item in found}, {'shared', 'claude_code'})
        self.assertEqual({item['path'] for item in found}, {str(common), str(claude)})
        self.assertTrue(all(item['discovery'] == 'filesystem' for item in found))
        self.assertTrue(all(not item['registered'] for item in found))

    def test_discovery_does_not_guess_chatgpt_account_skill_directories(self):
        home = self.root / 'home'
        (home / '.chatgpt' / 'skills').mkdir(parents=True)
        with patch('skills.Path.home', return_value=home):
            found = self.store.discover_skill_directories()
        self.assertFalse(any(item['provider'].startswith('chatgpt_') for item in found))


if __name__ == '__main__':
    unittest.main()
