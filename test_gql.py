import os
import requests
import json
from dotenv import load_dotenv

load_dotenv('C:/Users/krish/OneDrive/Desktop/Study/Krishna-Codes/.env')
LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")
CSRF_TOKEN = os.getenv("CSRF_TOKEN")

HEADERS = {
    'Cookie': f'LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={CSRF_TOKEN}',
    'X-CSRFToken': CSRF_TOKEN,
    'Referer': 'https://leetcode.com/',
    'Content-Type': 'application/json'
}

query = """
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    code
    lang {
      name
    }
    question {
      questionId
      titleSlug
      title
    }
  }
}
"""

res = requests.post(
    'https://leetcode.com/graphql', 
    headers=HEADERS, 
    json={'query': query, 'variables': {'submissionId': 1408078909}}
)
print("Status:", res.status_code)
print(json.dumps(res.json(), indent=2))
