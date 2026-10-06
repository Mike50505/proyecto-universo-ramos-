"""Small SQLite read cache. Run with UR_BASE_URL and UR_API_KEY environment variables."""
import json
import os
import sqlite3
import urllib.request

base = os.environ['UR_BASE_URL'].rstrip('/')
token = os.environ['UR_API_KEY']
db = sqlite3.connect(os.environ.get('UR_CACHE_DB', 'consumer-cache.sqlite3'))
db.execute('CREATE TABLE IF NOT EXISTS parts (central_uuid TEXT PRIMARY KEY, payload TEXT NOT NULL)')
db.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, value TEXT NOT NULL)')

def get(path):
    req = urllib.request.Request(base + path, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def upsert(part):
    db.execute('INSERT INTO parts (central_uuid,payload) VALUES (?,?) ON CONFLICT(central_uuid) DO UPDATE SET payload=excluded.payload', (str(part['id']), json.dumps(part)))

row = db.execute("SELECT value FROM state WHERE name='cursor'").fetchone()
if row is None:
    bootstrap = get('/api/v1/bootstrap/')
    url = '/api/v1/parts/?page_size=200'
    while url:
        page = get(url)
        with db:
            for part in page['results']:
                upsert(part)
        url = page['next'].replace(base, '') if page['next'] else None
    cursor = bootstrap['changes_cursor']
else:
    cursor = row[0]

while True:
    from urllib.parse import quote
    page = get('/api/v1/changes/?limit=200&cursor=' + quote(cursor))
    with db:
        for event in page['results']:
            # Events contain the historical snapshot. Deactivation remains a stored record.
            snapshot = event['part']
            upsert({'id': event['part_id'], **snapshot})
        cursor = page['next_cursor']
        db.execute("INSERT INTO state(name,value) VALUES('cursor',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (cursor,))
    if not page['has_more']:
        break
print('Synchronized', db.execute('SELECT COUNT(*) FROM parts').fetchone()[0], 'parts')
