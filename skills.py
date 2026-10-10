"""Local, metadata-only skill catalog and transparent recommendation rules."""
import hashlib
import json
import os
import re
import stat
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


SKILL_PROVIDERS = {
    'shared': 'General / compartido',
    'codex': 'Codex',
    'claude_code': 'Claude Code',
    'claude': 'Claude',
    'chatgpt_personal': 'ChatGPT Personal',
    'chatgpt_business': 'ChatGPT Business',
    'chatgpt_work': 'ChatGPT Work',
    'other': 'Otro entorno',
}
MAX_SOURCES = 30
MAX_SKILLS_PER_SOURCE = 500
MAX_SKILL_BYTES = 65536
MAX_DESCRIPTION = 800
MAX_TAGS = 30
SOURCE_MODES = ('manual', 'on_task_open', 'on_task_edit')
_STOP = set('a al algo ante bajo con como contra cual cuales cuando de del desde donde durante e el ella ellas ellos en entre era es esa esas ese eso esos esta estas este esto estos fue ha hacia hasta la las le les lo los mas mi mis ni no o para pero por que se sin sobre su sus te tu tus un una unas uno unos y ya'.split())


def _clean(value, limit=240, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('Texto inválido o demasiado largo.')
    value = value.strip()
    if required and not value:
        raise ValueError('El texto es obligatorio.')
    return value


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        quote = value[0]
        value = value[1:-1]
        if quote == '"':
            value = bytes(value, 'utf-8').decode('unicode_escape') if '\\' in value else value
        else:
            value = value.replace("''", "'")
    return value


def _parse_frontmatter(raw, fallback_name):
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        raise ValueError('Falta el encabezado YAML inicial.')
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == '---'), None)
    if end is None or end > 80:
        raise ValueError('Encabezado YAML ausente o demasiado largo.')
    fields = {}
    tags = []
    current = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.match(r'^([A-Za-z][A-Za-z0-9_-]{0,50}):(?:\s*(.*))?$', line)
        if match and not line[:1].isspace():
            current = match.group(1).lower()
            fields[current] = match.group(2) or ''
            continue
        if current == 'tags' and re.match(r'^\s+-\s+', line):
            tags.append(_unquote(re.sub(r'^\s+-\s+', '', line)))
        elif current == 'description' and line[:1].isspace():
            fields[current] += ' ' + line.strip()
    name = _unquote(fields.get('name', '')) or fallback_name
    description = _unquote(fields.get('description', ''))
    tag_value = fields.get('tags', '').strip()
    if tag_value.startswith('[') and tag_value.endswith(']'):
        tags.extend(_unquote(x.strip()) for x in tag_value[1:-1].split(',') if x.strip())
    elif tag_value:
        tags.extend(_unquote(x.strip()) for x in tag_value.split(',') if x.strip())
    tags = list(dict.fromkeys(t[:80] for t in tags if isinstance(t, str) and t.strip()))[:MAX_TAGS]
    return {
        'name': _clean(name, 120, True),
        'description': _clean(description or 'Sin descripción en SKILL.md.', MAX_DESCRIPTION),
        'tags': tags,
    }


def _read_bounded_regular_file(path):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(path), flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SKILL_BYTES:
            raise ValueError('El archivo no es regular o supera el límite de 64 KB.')
        chunks = []
        remaining = MAX_SKILL_BYTES + 1
        while remaining:
            block = os.read(fd, min(8192, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        raw = b''.join(chunks)
        after = os.fstat(fd)
        if before.st_ino != after.st_ino or before.st_size != after.st_size or len(raw) != after.st_size:
            raise ValueError('El archivo cambió durante el escaneo.')
        if len(raw) > MAX_SKILL_BYTES:
            raise ValueError('El archivo supera el límite de 64 KB.')
        return raw, after
    finally:
        os.close(fd)


def _tokens(value):
    folded = ''.join(c for c in unicodedata.normalize('NFD', str(value).lower())
                     if unicodedata.category(c) != 'Mn')
    return {word for word in re.findall(r'[a-z0-9][a-z0-9_+#.-]{1,40}', folded)
            if word not in _STOP and len(word) > 1}


class Skills:
    """Mixin for Proyecta's SQLite-backed skill registry."""

    def init_skills(self, db):
        db.executescript('''
        CREATE TABLE IF NOT EXISTS skill_sources (
          id INTEGER PRIMARY KEY, label TEXT NOT NULL, provider TEXT NOT NULL,
          path TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
          UNIQUE(provider,path));
        CREATE TABLE IF NOT EXISTS skill_catalog (
          id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES skill_sources(id) ON DELETE CASCADE,
          relative_path TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL,
          tags TEXT NOT NULL, digest TEXT NOT NULL, modified_at INTEGER NOT NULL,
          UNIQUE(source_id,relative_path));
        CREATE TABLE IF NOT EXISTS skill_preferences (
          id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 1,
          mode TEXT NOT NULL DEFAULT 'manual', max_suggestions INTEGER NOT NULL DEFAULT 3);
        INSERT OR IGNORE INTO skill_preferences(id,enabled,mode,max_suggestions) VALUES(1,1,'manual',3);
        ''')
        db.execute('PRAGMA foreign_keys=ON')

    def _remove_skill_refs(self, db, skill_ids, reason):
        skill_ids = set(skill_ids)
        if not skill_ids:
            return
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        for task in db.execute('SELECT id,project_id,skill_refs FROM tasks').fetchall():
            try:
                refs = json.loads(task['skill_refs'] or '[]')
            except (TypeError, json.JSONDecodeError):
                refs = []
            kept = [ref for ref in refs if ref not in skill_ids]
            if len(kept) == len(refs):
                continue
            db.execute('UPDATE tasks SET skill_refs=?,version=version+1,updated_at=? WHERE id=?',
                       (json.dumps(kept), stamp, task['id']))
            db.execute('UPDATE projects SET version=version+1,updated_at=? WHERE id=?', (stamp, task['project_id']))
            db.execute('INSERT INTO events(project_id,kind,actor,text,evidence,created_at) VALUES(?,?,?,?,?,?)',
                       (task['project_id'], 'nota', 'Proyecta', f'{reason} en la tarea #{task["id"]}.', '', stamp))

    def skill_snapshot(self, db):
        sources = [dict(row) for row in db.execute('SELECT id,label,provider,path,enabled FROM skill_sources ORDER BY label COLLATE NOCASE,id')]
        skills = []
        for row in db.execute('''SELECT c.*,s.provider,s.label AS source_label,s.path AS source_path
                                 FROM skill_catalog c JOIN skill_sources s ON s.id=c.source_id
                                 ORDER BY c.name COLLATE NOCASE,c.id'''):
            item = dict(row)
            item['tags'] = json.loads(item['tags'])
            item['enabled'] = bool(next((s['enabled'] for s in sources if s['id'] == item['source_id']), 0))
            item['provider_label'] = SKILL_PROVIDERS.get(item['provider'], 'Otro entorno')
            skills.append(item)
        prefs = db.execute('SELECT enabled,mode,max_suggestions FROM skill_preferences WHERE id=1').fetchone()
        return {'skill_sources': sources, 'skills': skills,
                'skill_preferences': dict(prefs) if prefs else {'enabled': 1, 'mode': 'manual', 'max_suggestions': 3}}

    def discover_skill_directories(self):
        """List only conventional skill folders; never walk the user's home directory."""
        home = Path.home()
        app_root = Path(__file__).resolve().parent
        candidates = [
            (home / '.agents' / 'skills', 'Skills compartidas', 'shared'),
            (home / '.codex' / 'skills', 'Skills de Codex', 'codex'),
            (home / '.claude' / 'skills', 'Skills de Claude Code', 'claude_code'),
            (app_root / '.agents' / 'skills', 'Skills del proyecto', 'shared'),
            (app_root / '.codex' / 'skills', 'Skills del proyecto', 'codex'),
            (app_root / '.claude' / 'skills', 'Skills Claude Code del proyecto', 'claude_code'),
        ]
        found = []
        seen = set()
        with self.lock, self.connect() as db:
            registered = {(r['provider'], str(Path(r['path']).expanduser())) for r in db.execute('SELECT provider,path FROM skill_sources')}
        for path, label, provider in candidates:
            try:
                anchor = home if path.is_relative_to(home) else app_root
                current = anchor
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                    continue
                for part in path.relative_to(anchor).parts:
                    current = current / part
                    info = current.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        current = None
                        break
                if current is None or not stat.S_ISDIR(info.st_mode):
                    continue
            except OSError:
                continue
            normalized = str(path.resolve())
            key = (provider, normalized)
            if key in seen:
                continue
            seen.add(key)
            found.append({'label': label, 'provider': provider, 'path': normalized,
                          'registered': key in registered,
                          'discovery': 'filesystem',
                          'note': 'Directorio local detectado; se leerán únicamente metadatos SKILL.md.'})
        return found

    def validate_skill_snapshot(self, obj):
        sources = obj.get('skill_sources', [])
        catalog = obj.get('skills', [])
        prefs = obj.get('skill_preferences', {'enabled': 1, 'mode': 'manual', 'max_suggestions': 3})
        if not isinstance(sources, list) or not isinstance(catalog, list) or len(sources) > MAX_SOURCES or len(catalog) > 20000:
            raise ValueError('Catálogo de skills inválido o demasiado grande.')
        source_ids, source_keys = set(), set()
        for row in sources:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0 or row['id'] in source_ids:
                raise ValueError('Fuente de skills inválida.')
            if row.get('provider') not in SKILL_PROVIDERS or type(row.get('enabled')) not in (bool, int) or row['enabled'] not in (0, 1):
                raise ValueError('Proveedor o estado de fuente inválido.')
            label = _clean(row.get('label'), 120, True)
            path = Path(_clean(row.get('path'), 1000, True)).expanduser()
            if not path.is_absolute(): raise ValueError('La ruta de skills debe ser absoluta.')
            key = (row['provider'], str(path))
            if key in source_keys: raise ValueError('Fuente de skills duplicada.')
            source_ids.add(row['id']); source_keys.add(key)
        skill_ids, keys = set(), set()
        for row in catalog:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0 or row['id'] in skill_ids:
                raise ValueError('Skill inválido en respaldo.')
            if row.get('source_id') not in source_ids:
                raise ValueError('Una skill referencia una fuente inexistente.')
            rel = _clean(row.get('relative_path'), 300, True)
            if Path(rel).is_absolute() or '..' in Path(rel).parts:
                raise ValueError('La ruta relativa de una skill es inválida.')
            _clean(row.get('name'), 120, True); _clean(row.get('description'), MAX_DESCRIPTION)
            tags = row.get('tags', [])
            if not isinstance(tags, list) or len(tags) > MAX_TAGS or any(not isinstance(t, str) or len(t) > 80 for t in tags):
                raise ValueError('Etiquetas de skill inválidas.')
            if not re.fullmatch(r'[a-f0-9]{64}', str(row.get('digest', ''))) or type(row.get('modified_at')) is not int:
                raise ValueError('Huella o fecha de skill inválida.')
            key = (row['source_id'], rel)
            if key in keys: raise ValueError('Skill duplicado en una fuente.')
            keys.add(key); skill_ids.add(row['id'])
        if not isinstance(prefs, dict) or type(prefs.get('enabled')) not in (bool, int) or prefs.get('enabled') not in (0, 1) or prefs.get('mode') not in SOURCE_MODES or type(prefs.get('max_suggestions')) is not int or not 1 <= prefs['max_suggestions'] <= 3:
            raise ValueError('Preferencias del Asesor de skills inválidas.')
        return {'skill_sources': sources, 'skills': catalog, 'skill_preferences': prefs}

    def save_skill_source(self, obj):
        if not isinstance(obj, dict):
            raise ValueError('Fuente de skills inválida.')
        label = _clean(obj.get('label'), 120, True)
        provider = obj.get('provider')
        if provider not in SKILL_PROVIDERS:
            raise ValueError('Entorno de skills inválido.')
        raw_path = _clean(obj.get('path'), 1000, True)
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise ValueError('Selecciona una ruta absoluta del equipo local.')
        enabled = obj.get('enabled', True)
        if type(enabled) not in (bool, int) or enabled not in (0, 1):
            raise ValueError('Estado de fuente inválido.')
        sid = obj.get('id')
        with self.lock, self.connect() as db:
            if sid is None:
                db.execute('INSERT INTO skill_sources(label,provider,path,enabled) VALUES(?,?,?,?)',
                           (label, provider, str(path), int(enabled)))
            else:
                if type(sid) is not int or not db.execute('SELECT id FROM skill_sources WHERE id=?', (sid,)).fetchone():
                    raise ValueError('Fuente de skills inexistente.')
                existing = db.execute('SELECT label,provider,path FROM skill_sources WHERE id=?', (sid,)).fetchone()
                if (existing['label'], existing['provider'], existing['path']) != (label, provider, str(path)):
                    skill_ids = [r[0] for r in db.execute('SELECT id FROM skill_catalog WHERE source_id=?', (sid,))]
                    self._remove_skill_refs(db, skill_ids, f'Se actualizaron los skills de la fuente «{existing["label"]}»')
                    db.execute('DELETE FROM skill_catalog WHERE source_id=?', (sid,))
                db.execute('UPDATE skill_sources SET label=?,provider=?,path=?,enabled=? WHERE id=?',
                           (label, provider, str(path), int(enabled), sid))
        return self.snapshot()

    def delete_skill_source(self, obj):
        sid = obj.get('id') if isinstance(obj, dict) else None
        if type(sid) is not int:
            raise ValueError('Selecciona una fuente válida.')
        with self.lock, self.connect() as db:
            source = db.execute('SELECT label FROM skill_sources WHERE id=?', (sid,)).fetchone()
            if not source:
                raise ValueError('Fuente de skills inexistente.')
            skill_ids = [row[0] for row in db.execute('SELECT id FROM skill_catalog WHERE source_id=?', (sid,))]
            self._remove_skill_refs(db, skill_ids, f'Se quitaron skills de la fuente «{source["label"]}» eliminada')
            cur = db.execute('DELETE FROM skill_sources WHERE id=?', (sid,))
            if not cur.rowcount:
                raise ValueError('Fuente de skills inexistente.')
        return self.snapshot()

    def save_skill_preferences(self, obj):
        if not isinstance(obj, dict):
            raise ValueError('Preferencias inválidas.')
        enabled, mode, maximum = obj.get('enabled'), obj.get('mode'), obj.get('max_suggestions')
        if type(enabled) not in (bool, int) or enabled not in (0, 1):
            raise ValueError('Indica si las sugerencias están habilitadas.')
        if mode not in SOURCE_MODES:
            raise ValueError('Momento de sugerencia inválido.')
        if type(maximum) is not int or maximum < 1 or maximum > 3:
            raise ValueError('El máximo de sugerencias debe estar entre 1 y 3.')
        with self.lock, self.connect() as db:
            db.execute('UPDATE skill_preferences SET enabled=?,mode=?,max_suggestions=? WHERE id=1',
                       (int(enabled), mode, maximum))
        return self.snapshot()

    def scan_skill_sources(self, obj=None):
        source_id = None
        if obj is not None:
            if not isinstance(obj, dict) or set(obj) - {'source_id'}:
                raise ValueError('Solicitud de escaneo inválida.')
            source_id = obj.get('source_id')
            if source_id is not None and (type(source_id) is not int or source_id <= 0):
                raise ValueError('Fuente de skills inválida.')
        with self.lock, self.connect() as db:
            if source_id is None:
                source_rows = db.execute('SELECT * FROM skill_sources WHERE enabled=1 ORDER BY id').fetchall()
            else:
                source_rows = db.execute('SELECT * FROM skill_sources WHERE enabled=1 AND id=?', (source_id,)).fetchall()
                if not source_rows:
                    raise ValueError('La fuente no existe o está deshabilitada.')
            sources = [dict(row) for row in source_rows]
            totals = {'sources': len(sources), 'skills': 0, 'skipped': 0, 'errors': []}
            for source in sources:
                root = Path(source['path']).expanduser()
                try:
                    root_stat = root.lstat()
                    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
                        raise ValueError('La ruta no es un directorio regular o es un enlace simbólico.')
                    candidates = []
                    direct_skill = root / 'SKILL.md'
                    if direct_skill.exists() or direct_skill.is_symlink():
                        candidates.append((root, direct_skill))
                    for child in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
                        if child == root or child.name.startswith('.'):
                            continue
                        try:
                            info = child.lstat()
                        except OSError:
                            totals['skipped'] += 1
                            continue
                        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                            continue
                        candidates.append((child, child / 'SKILL.md'))
                        if len(candidates) > MAX_SKILLS_PER_SOURCE:
                            raise ValueError('La fuente supera el límite de 500 skills.')
                    scanned = []
                    for directory, file_path in candidates:
                        try:
                            info = file_path.lstat()
                            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                                totals['skipped'] += 1
                                continue
                            raw, current = _read_bounded_regular_file(file_path)
                            meta = _parse_frontmatter(raw, directory.name)
                            rel = str(file_path.relative_to(root))
                            scanned.append((rel, meta, hashlib.sha256(raw).hexdigest(), current.st_mtime_ns))
                        except FileNotFoundError:
                            continue
                        except (OSError, ValueError, UnicodeError) as error:
                            totals['skipped'] += 1
                            if len(totals['errors']) < 20:
                                totals['errors'].append({'source': source['label'], 'item': directory.name,
                                                         'reason': str(error)[:240]})
                    existing = {r['relative_path']: dict(r) for r in db.execute('SELECT id,relative_path FROM skill_catalog WHERE source_id=?', (source['id'],))}
                    seen_paths = set()
                    removed = []
                    for rel, meta, digest, mtime in scanned:
                        seen_paths.add(rel)
                        values = (meta['name'], meta['description'], json.dumps(meta['tags'], ensure_ascii=False), digest, mtime)
                        if rel in existing:
                            db.execute('UPDATE skill_catalog SET name=?,description=?,tags=?,digest=?,modified_at=? WHERE id=?', (*values, existing[rel]['id']))
                        else:
                            db.execute('INSERT INTO skill_catalog(source_id,relative_path,name,description,tags,digest,modified_at) VALUES(?,?,?,?,?,?,?)',
                                       (source['id'], rel, *values))
                    removed = [r['id'] for rel, r in existing.items() if rel not in seen_paths]
                    if removed:
                        self._remove_skill_refs(db, removed, f'Se quitaron skills ya no disponibles en «{source["label"]}»')
                        db.executemany('DELETE FROM skill_catalog WHERE id=?', [(sid,) for sid in removed])
                    totals['skills'] += len(scanned)
                except (OSError, ValueError) as error:
                    totals['skipped'] += 1
                    if len(totals['errors']) < 20:
                        totals['errors'].append({'source': source['label'], 'item': '', 'reason': str(error)[:240]})
            return {**self.skill_snapshot(db), 'scan': totals}

    def recommend_skills(self, obj):
        if not isinstance(obj, dict):
            raise ValueError('Solicitud de recomendación inválida.')
        from app import field
        context = ' '.join(field(obj, key, limit, False) for key, limit in (
            ('title', 240), ('objective', 2000), ('acceptance', 2000), ('notes', 2000), ('stage', 80)))
        if not context.strip():
            raise ValueError('Describe la tarea o su etapa para recomendar skills.')
        provider = obj.get('provider', 'shared')
        if provider not in SKILL_PROVIDERS:
            raise ValueError('Selecciona un entorno válido.')
        with self.lock, self.connect() as db:
            prefs = db.execute('SELECT * FROM skill_preferences WHERE id=1').fetchone()
            if not prefs['enabled']:
                return {'items': [], 'notice': 'El Asesor de skills está deshabilitado.'}
            requested = obj.get('limit', prefs['max_suggestions'])
            if type(requested) is not int or requested < 1:
                raise ValueError('El máximo de sugerencias debe ser un número entre 1 y 3.')
            limit = min(requested, min(3, prefs['max_suggestions']))
            task_tokens = _tokens(context)
            results = []
            for row in db.execute('''SELECT c.*,s.provider,s.label AS source_label,s.path AS source_path
                                     FROM skill_catalog c JOIN skill_sources s ON s.id=c.source_id
                                     WHERE s.enabled=1'''):
                if provider not in ('shared', 'other') and row['provider'] not in (provider, 'shared', 'other'):
                    continue
                tags = json.loads(row['tags'])
                name_terms = _tokens(row['name'])
                tag_terms = set().union(*(_tokens(tag) for tag in tags)) if tags else set()
                description_terms = _tokens(row['description'])
                name_hits = sorted(task_tokens & name_terms)
                tag_hits = sorted(task_tokens & tag_terms)
                description_hits = sorted(task_tokens & description_terms)
                score = 4 * len(tag_hits) + 3 * len(name_hits) + len(description_hits)
                if score <= 0:
                    continue
                reasons = []
                if tag_hits:
                    reasons.append('coinciden las etiquetas ' + ', '.join(tag_hits[:4]))
                if name_hits:
                    reasons.append('el nombre coincide en ' + ', '.join(name_hits[:4]))
                if description_hits:
                    reasons.append('la descripción coincide en ' + ', '.join(description_hits[:4]))
                compatibility = 'Compatible con el entorno elegido.' if row['provider'] in ('shared', provider) else 'Skill general; confirma la compatibilidad antes de usarlo.'
                results.append({'id': row['id'], 'name': row['name'], 'description': row['description'],
                                'provider': row['provider'], 'provider_label': SKILL_PROVIDERS.get(row['provider'], 'Otro entorno'),
                                'source_label': row['source_label'], 'path': str(Path(row['source_path']) / row['relative_path']),
                                'tags': tags, 'score': score, 'match_terms': sorted(set(tag_hits + name_hits + description_hits)),
                                'reason': 'Se sugiere porque ' + '; '.join(reasons) + '.', 'compatibility': compatibility})
            results.sort(key=lambda item: (-item['score'], item['name'].casefold(), item['id']))
            return {'items': results[:limit], 'notice': 'Sugerencias locales basadas en nombre, descripción y etiquetas. Proyecta no instala ni ejecuta skills.'}
