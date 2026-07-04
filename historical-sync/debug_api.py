import os
import requests
from dotenv import load_dotenv

load_dotenv('.env')

LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")
CSRF_TOKEN = os.getenv("CSRF_TOKEN")

HEADERS = {
    'Cookie': f'LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={CSRF_TOKEN}',
    'X-CSRFToken': CSRF_TOKEN,
    'Referer': 'https://leetcode.com/',
    'User-Agent': 'Mozilla/5.0'
}

session = requests.Session()
session.headers.update(HEADERS)

print("Testing /api/submissions/")
offset = 0
limit = 20
while True:
    res = session.get(f'https://leetcode.com/api/submissions/?offset={offset}&limit={limit}')
    data = res.json()
    dump = data.get('submissions_dump', [])
    print(f"Offset {offset}: Retrieved {len(dump)} submissions. has_next: {data.get('has_next')}")
    if dump:
        print(f"  First ID: {dump[0]['id']}, Status: {dump[0]['status_display']}")
        print(f"  Last ID: {dump[-1]['id']}, Status: {dump[-1]['status_display']}")
    
    if not data.get('has_next'):
        break
    offset += limit

print("Testing GraphQL submissionList pagination...")
query = """
query submissionList($offset: Int!, $limit: Int!, $lastKey: String, $questionSlug: String) {
  submissionList(offset: $offset, limit: $limit, lastKey: $lastKey, questionSlug: $questionSlug) {
    lastKey
    hasNext
    submissions {
      id
      statusDisplay
      lang
      title
      titleSlug
      timestamp
    }
  }
}
"""
offset = 0
limit = 20
last_key = None
total_fetched = 0
accepted_fetched = 0

while True:
    variables = {'offset': offset, 'limit': limit, 'lastKey': last_key}
    res = session.post('https://leetcode.com/graphql', json={'query': query, 'variables': variables})
    if res.status_code == 200:
        data = res.json()
        if 'data' in data and data['data'].get('submissionList'):
            sl = data['data']['submissionList']
            subs = sl.get('submissions', [])
            total_fetched += len(subs)
            accepted = len([s for s in subs if s.get('statusDisplay') == 'Accepted'])
            accepted_fetched += accepted
            
            print(f"GraphQL Offset {offset}: Fetched {len(subs)} (AC: {accepted}), hasNext={sl.get('hasNext')}")
            
            last_key = sl.get('lastKey')
            if not sl.get('hasNext'):
                break
            offset += limit
        else:
            print("GraphQL error or empty data:", data)
            break
    else:
        print("GraphQL HTTP failed:", res.status_code, res.text)
        break

print(f"Total Submissions Fetched: {total_fetched}")
print(f"Total Accepted Fetched: {accepted_fetched}")

