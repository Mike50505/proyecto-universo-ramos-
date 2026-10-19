"""Small SQLite read cache. Run with UR_BASE_URL and UR_API_KEY environment variables."""
import json
import os
import sqlite3
import urllib.error
import urllib.request
from urllib.parse import quote

base = os.environ['UR_BASE_URL'].rstrip('/')
token = os.environ['UR_API_KEY']
include_samples = os.environ.get('UR_INCLUDE_SAMPLES', 'true').lower() == 'true'
db = sqlite3.connect(os.environ.get('UR_CACHE_DB', 'consumer-cache.sqlite3'))
db.execute('CREATE TABLE IF NOT EXISTS parts (central_uuid TEXT PRIMARY KEY, payload TEXT NOT NULL)')
db.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, value TEXT NOT NULL)')

class ResyncRequired(Exception):
    pass


def get(path):
    if path.startswith(base + '/'):
        path = path[len(base):]
    if not path.startswith('/') or path.startswith('//'):
        raise ValueError('Unexpected API URL')
    req = urllib.request.Request(base + path, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 409 and json.load(exc).get('code') == 'resync_required':
            raise ResyncRequired from exc
        raise

def upsert(part):
    if not include_samples and part.get('is_sample', False):
        db.execute('DELETE FROM parts WHERE central_uuid=?', (str(part['id']),))
        return
    db.execute('INSERT INTO parts (central_uuid,payload) VALUES (?,?) ON CONFLICT(central_uuid) DO UPDATE SET payload=excluded.payload', (str(part['id']), json.dumps(part)))

# Apply the local visibility policy even if no new events have arrived.
if not include_samples:
    with db:
        for central_uuid, payload in db.execute('SELECT central_uuid, payload FROM parts').fetchall():
            if json.loads(payload).get('is_sample', False):
                db.execute('DELETE FROM parts WHERE central_uuid=?', (central_uuid,))

policy = 'true' if include_samples else 'false'
previous_policy = db.execute("SELECT value FROM state WHERE name='include_samples'").fetchone()
if previous_policy is None or previous_policy[0] != policy:
    # Rebuild from the current snapshot when changing which records are retained.
    with db:
        db.execute("DELETE FROM state WHERE name='cursor'")
        db.execute("INSERT INTO state(name,value) VALUES('include_samples',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (policy,))

def save_changes(page):
    for event in page['results']:
        if event.get('excluded', False):
            db.execute('DELETE FROM parts WHERE central_uuid=?', (str(event['part_id']),))
        else:
            # Ordinary deactivation remains a stored record; permission exclusions do not.
            upsert({'id': event['part_id'], **event['part']})
    db.execute("INSERT INTO state(name,value) VALUES('cursor',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (page['next_cursor'],))


def change_pages(cursor):
    while True:
        page = get('/api/v1/changes/?limit=200&cursor=' + quote(cursor))
        yield page
        cursor = page['next_cursor']
        if not page['has_more']:
            break


def synchronize():
    row = db.execute("SELECT value FROM state WHERE name='cursor'").fetchone()
    if row is None:
        bootstrap = get('/api/v1/bootstrap/')
        url = bootstrap.get('parts_url', '/api/v1/parts/?page_size=200')
        # Replace the cache and cursor atomically, preserving the old cache on errors.
        with db:
            db.execute('DELETE FROM parts')
            while url:
                page = get(url)
                for part in page['results']:
                    upsert(part)
                url = page['next']
            for page in change_pages(bootstrap['changes_cursor']):
                save_changes(page)
    else:
        for page in change_pages(row[0]):
            with db:
                save_changes(page)


for attempt in range(3):
    try:
        synchronize()
        break
    except ResyncRequired:
        with db:
            db.execute("DELETE FROM state WHERE name='cursor'")
        if attempt == 2:
            raise
print('Synchronized', db.execute('SELECT COUNT(*) FROM parts').fetchone()[0], 'parts')
