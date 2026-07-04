import os
import time
import requests
import json
import subprocess
import logging
import argparse
from dotenv import load_dotenv
from datetime import datetime
from markdownify import markdownify as md
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Parse Arguments ---
parser = argparse.ArgumentParser(description="Sync LeetCode historical submissions to Git.")
parser.add_argument("--dry-run", action="store_true", help="Run without writing files or committing. Validates API endpoints on the first 5 submissions.")
parser.add_argument("--debug", action="store_true", help="Enable debug logging and print extended submission IDs.")
args = parser.parse_args()

# --- Configuration & Environment ---
load_dotenv()

LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")
CSRF_TOKEN = os.getenv("CSRF_TOKEN")
SYNC_MODE = os.getenv("SYNC_MODE", "full_history").lower()
DELAY = float(os.getenv("DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("RETRIES", "5"))
AUTO_PUSH = os.getenv("AUTO_PUSH", "false").lower() == "true"
REPO_PATH = os.getenv("REPO_PATH", ".").strip()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG if (args.dry_run or args.debug) else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("sync.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

if not LEETCODE_SESSION or not CSRF_TOKEN:
    logging.error("LEETCODE_SESSION or CSRF_TOKEN is not set in .env file.")
    exit(1)

# Ensure the repository path exists
os.makedirs(REPO_PATH, exist_ok=True)

HEADERS = {
    'Cookie': f'LEETCODE_SESSION={LEETCODE_SESSION}; csrftoken={CSRF_TOKEN}',
    'X-CSRFToken': CSRF_TOKEN,
    'Referer': 'https://leetcode.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
}

session = requests.Session()
retries = Retry(total=MAX_RETRIES, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))
session.headers.update(HEADERS)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPHQL_URL = "https://leetcode.com/graphql"
CACHE_FILE = os.path.join(REPO_PATH, '.sync_cache.json') # Tracks what is in this specific Git repo
PROBLEMS_CACHE_FILE = os.path.join(SCRIPT_DIR, '.problems_cache.json') # Global cache for descriptions
CODE_CACHE_FILE = os.path.join(SCRIPT_DIR, '.code_cache.json') # Global cache for source code

def run_git_command(git_args, cwd=REPO_PATH, env=None, fatal=True):
    """Executes a Git command and handles failures robustly."""
    if args.dry_run:
        logging.debug(f"[DRY RUN] Skipping git command: git {' '.join(git_args)}")
        cmd = git_args[0]
        if cmd == 'status':
            return "MOCK_CHANGES" # Ensure the commit block executes
        if cmd == 'rev-parse':
            return "true" # Pretend inside git repo
        if cmd == 'branch':
            return "main"
        if cmd == 'remote':
            return "origin"
        return "DRY_RUN_MOCK"
        
    try:
        result = subprocess.run(['git'] + git_args, cwd=cwd, env=env, check=True, capture_output=True, text=True, encoding='utf-8')
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command failed: git {' '.join(git_args)}")
        logging.error(e.stderr.strip())
        if fatal:
            logging.error("Fatal Git error encountered. Aborting.")
            exit(1)
        return None

def preflight_checks():
    logging.info(f"Performing pre-flight validations in {os.path.abspath(REPO_PATH)}...")
    
    # 1. Verify Git Repository
    if run_git_command(['rev-parse', '--is-inside-work-tree'], fatal=False) != 'true':
        logging.info("Git repository not found. Initializing...")
        run_git_command(['init'])
    else:
        logging.info("Git repository verified.")
        
    # 2. Verify Remote if Auto Push is enabled
    if AUTO_PUSH:
        remotes = run_git_command(['remote'])
        if not remotes:
            logging.error("AUTO_PUSH is true, but no git remote exists. Add a remote via 'git remote add origin <url>'.")
            exit(1)
            
    # 3. Verify Authentication and Cookies
    query = """
    query globalData {
      userStatus {
        isSignedIn
      }
    }
    """
    res = session.post(GRAPHQL_URL, json={'query': query})
    if res.status_code != 200:
        logging.error(f"Pre-flight Auth Check failed: HTTP {res.status_code}. Raw: {res.text}")
        exit(1)
    
    data = res.json()
    if 'errors' in data:
        logging.error(f"GraphQL Error during Auth Check: {data['errors']}. Raw: {json.dumps(data)}")
        exit(1)
        
    if not data.get('data', {}).get('userStatus', {}).get('isSignedIn'):
        logging.error("Auth Check failed: Invalid LEETCODE_SESSION or CSRF_TOKEN. Please update your cookies.")
        exit(1)
        
    logging.info("Pre-flight checks passed. Authentication verified.")

def fetch_all_problems():
    logging.info("Fetching all problems metadata from LeetCode...")
    res = session.get('https://leetcode.com/api/problems/algorithms/')
    if res.status_code != 200:
        logging.error(f"Failed to fetch problems map. HTTP {res.status_code}. Raw: {res.text}")
        exit(1)
    
    problems_data = res.json()
    problem_map = {}
    for item in problems_data['stat_status_pairs']:
        title = item['stat']['question__title']
        problem_map[title] = {
            'id': item['stat']['question_id'],
            'slug': item['stat']['question__title_slug'],
            'difficulty': item['difficulty']['level']
        }
    return problem_map

def get_question_details(slug):
    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        content
        topicTags {
          name
        }
      }
    }
    """
    try:
        res = session.post(GRAPHQL_URL, json={'query': query, 'variables': {'titleSlug': slug}})
        if res.status_code == 200:
            data = res.json()
            if 'errors' in data:
                logging.error(f"GraphQL Error fetching description for {slug}: {data['errors']}. Raw: {json.dumps(data)}")
                return None, None
            if data.get('data') and data['data'].get('question'):
                q = data['data']['question']
                tags = [tag['name'] for tag in q.get('topicTags', [])] if q.get('topicTags') else []
                return q.get('content', ''), tags
            else:
                logging.error(f"GraphQL Response missing 'question' data for {slug}. Raw: {json.dumps(data)}")
        else:
             logging.error(f"HTTP Error {res.status_code} fetching description for {slug}. Raw: {res.text}")
    except Exception as e:
        logging.error(f"Exception fetching description for {slug}: {e}")
    return None, None

def get_submission_code(sub_id, q_id=None, slug=None, timestamp=None, lang=None):
    code_cache = load_cache(CODE_CACHE_FILE)
    str_sub_id = str(sub_id)
    if str_sub_id in code_cache:
        return code_cache[str_sub_id]
        
    # Check fallback legacy folder in the script directory to prevent redownloading
    if all([q_id, slug, timestamp, lang]):
        ext = EXTENSIONS.get(lang, 'txt')
        sub_dt = datetime.fromtimestamp(timestamp)
        file_time_str = sub_dt.strftime("%Y-%m-%d_%H-%M-%S")
        old_dir = os.path.join(SCRIPT_DIR, format_directory_name(q_id, slug))
        old_file = os.path.join(old_dir, "submissions", f"{file_time_str}.{ext}")
        if os.path.exists(old_file):
            with open(old_file, 'r', encoding='utf-8') as f:
                code = f.read()
                code_cache[str_sub_id] = code
                save_cache(CODE_CACHE_FILE, code_cache)
                return code

    # Fetch from API if neither cache nor local file exists
    query = """
    query submissionDetails($submissionId: Int!) {
      submissionDetails(submissionId: $submissionId) {
        code
      }
    }
    """
    try:
        res = session.post(GRAPHQL_URL, json={'query': query, 'variables': {'submissionId': sub_id}})
        if res.status_code == 200:
            data = res.json()
            if 'errors' in data:
                logging.error(f"GraphQL Error fetching code for submission {sub_id}: {data['errors']}. Raw: {json.dumps(data)}")
                return None
            if data.get('data') and data['data'].get('submissionDetails'):
                code = data['data']['submissionDetails'].get('code')
                if code:
                    code_cache[str_sub_id] = code
                    save_cache(CODE_CACHE_FILE, code_cache)
                return code
            else:
                logging.error(f"GraphQL Response missing 'submissionDetails' code for {sub_id}. Raw: {json.dumps(data)}")
        else:
            logging.error(f"HTTP Error {res.status_code} fetching code for submission {sub_id}. Raw: {res.text}")
    except Exception as e:
        logging.error(f"Exception fetching code for submission {sub_id}: {e}")
    return None

def format_directory_name(q_id, slug):
    return f"{q_id:04d}-{slug}"

def get_difficulty_label(level):
    return {1: 'Easy', 2: 'Medium', 3: 'Hard'}.get(level, 'Unknown')

EXTENSIONS = {
    'cpp': 'cpp', 'python3': 'py', 'python': 'py', 'java': 'java', 'c': 'c',
    'csharp': 'cs', 'javascript': 'js', 'typescript': 'ts', 'go': 'go',
    'ruby': 'rb', 'swift': 'swift', 'kotlin': 'kt', 'rust': 'rs', 'php': 'php',
    'sql': 'sql', 'mysql': 'sql', 'oracle': 'sql',
}

def load_cache(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_cache(filepath, data):
    if args.dry_run:
        logging.debug(f"[DRY RUN] Skipping cache save to {filepath}")
        return
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_markdown(title, q_id, slug, difficulty, content_html, tags):
    content_md = md(content_html, heading_style="ATX") if content_html else ""
    tags_str = ", ".join(tags) if tags else "None"
    
    md_content = f"""<h2><a href="https://leetcode.com/problems/{slug}/">{q_id}. {title}</a></h2>
<h3>Difficulty: {difficulty}</h3>
<hr>

{content_md}

<br>
<hr>
<h3>Tags</h3>
<p>{tags_str}</p>

<h3>Complexity</h3>
<ul>
  <li><strong>Time Complexity:</strong> $O()$ </li>
  <li><strong>Space Complexity:</strong> $O()$ </li>
</ul>
"""
    return md_content

def main():
    if args.dry_run:
        logging.info("=== DRY RUN MODE ENABLED ===")
        logging.info("Will fetch FULL pagination history to validate API, then process exactly 5 submissions. Files/Git will NOT be modified.")

    preflight_checks()
    problem_map = fetch_all_problems()
    
    processed_ids = set(load_cache(CACHE_FILE).get('processed', []))
    problems_cache = load_cache(PROBLEMS_CACHE_FILE)
    
    logging.info("Fetching submissions history via GraphQL...")
    all_accepted = []
    offset = 0
    limit = 20
    last_key = None
    
    total_returned = 0
    pagination_requests = 0
    first_id = None
    last_id = None
    
    query_sub_list = """
    query submissionList($offset: Int!, $limit: Int!, $lastKey: String) {
      submissionList(offset: $offset, limit: $limit, lastKey: $lastKey) {
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
    
    while True:
        pagination_requests += 1
        variables = {'offset': offset, 'limit': limit, 'lastKey': last_key}
        
        if args.debug:
            logging.debug(f"[DEBUG] Executing GraphQL submissionList query:")
            logging.debug(f"[DEBUG] Query: {query_sub_list.strip()}")
            logging.debug(f"[DEBUG] Variables: {json.dumps(variables)}")
            
        res = session.post(GRAPHQL_URL, json={'query': query_sub_list, 'variables': variables})
        
        if res.status_code != 200:
            logging.error(f"Failed to fetch submissions at offset {offset}. HTTP {res.status_code}. Raw: {res.text}")
            break
            
        data = res.json()
        
        if args.debug and pagination_requests == 1:
            logging.debug(f"[DEBUG] Full GraphQL response for first page (excluding cookies): {json.dumps(data)}")
            
        if 'errors' in data:
            logging.error(f"GraphQL Error fetching submissions: {data['errors']}. Raw: {json.dumps(data)}")
            break
            
        if not data.get('data') or not data['data'].get('submissionList'):
            logging.error(f"API Response missing 'submissionList'. Raw: {json.dumps(data)}")
            break
            
        sl = data['data']['submissionList']
        subs = sl.get('submissions', [])
        
        if not subs:
            break
            
        total_returned += len(subs)
        
        if first_id is None and len(subs) > 0:
            first_id = subs[0]['id']
        if len(subs) > 0:
            last_id = subs[-1]['id']
            
        accepted_this_page = 0
        for sub in subs:
            if sub.get('statusDisplay') == 'Accepted':
                all_accepted.append(sub)
                accepted_this_page += 1
                
        last_key = sl.get('lastKey')
        has_next = sl.get('hasNext')
        
        if args.debug:
            logging.debug(f"[DEBUG] Page Stats -> offset: {offset}, records returned: {len(subs)}, accepted: {accepted_this_page}, hasNext: {has_next}, lastKey: {last_key}")
            
        if not has_next:
            break
            
        offset += limit
        time.sleep(DELAY)

    logging.info("--- Pagination Stats ---")
    logging.info(f"Total API requests made: {pagination_requests}")
    logging.info(f"Last offset reached: {offset}")
    logging.info(f"Total submissions returned: {total_returned}")
    logging.info(f"Total accepted submissions found: {len(all_accepted)}")
    
    if args.debug:
        logging.debug(f"[DEBUG] First submission ID retrieved: {first_id}")
        logging.debug(f"[DEBUG] Last submission ID retrieved: {last_id}")

    if not all_accepted:
        logging.info("No accepted submissions found on account.")
        return

    # 1. Timestamps correctly converted and sorted (GraphQL returns string timestamps)
    all_accepted.sort(key=lambda x: int(x['timestamp']))
    
    # 2. Duplicate submission modes
    if SYNC_MODE == 'latest_only':
        logging.info("SYNC_MODE is 'latest_only'. Filtering out older duplicates...")
        latest_subs = {}
        for sub in all_accepted:
            latest_subs[sub['title']] = sub
        pending_submissions = list(latest_subs.values())
    else:
        logging.info("SYNC_MODE is 'full_history'. Processing all submissions to build Git history...")
        pending_submissions = all_accepted
        
    to_process = [sub for sub in pending_submissions if sub['id'] not in processed_ids]
    
    if args.dry_run:
        logging.info(f"[DRY RUN] Found {len(to_process)} submissions. Processing restricted to exactly 5 test submissions.")
        to_process = to_process[:5]
    else:
        logging.info(f"Found {len(to_process)} new accepted submissions to process (out of {len(all_accepted)} total historical).")

    newly_processed = []
    skipped = 0
    start_time = time.time()

    try:
        for idx, sub in enumerate(to_process):
            sub_id = sub['id']
            title = sub['title']
            timestamp = int(sub['timestamp'])
            lang = sub['lang']
            
            elapsed = time.time() - start_time
            avg_time = elapsed / (idx if idx > 0 else 1)
            eta = avg_time * (len(to_process) - idx)
            
            logging.info(f"[{idx+1}/{len(to_process)}] {title} ({lang}) - ETA: {eta:.0f}s")
            
            if title not in problem_map:
                logging.warning(f"Could not find '{title}' in problem map. Skipping.")
                skipped += 1
                continue
                
            p_details = problem_map[title]
            q_id = p_details['id']
            slug = p_details['slug']
            difficulty = get_difficulty_label(p_details['difficulty'])
            
            dir_name = format_directory_name(q_id, slug)
            problem_dir = os.path.join(REPO_PATH, dir_name)
            
            if not args.dry_run:
                os.makedirs(problem_dir, exist_ok=True)
                os.makedirs(os.path.join(problem_dir, "submissions"), exist_ok=True)
            
            code = get_submission_code(sub_id, q_id=q_id, slug=slug, timestamp=timestamp, lang=lang)
            if not code:
                logging.error(f"Could not fetch code for submission {sub_id}. Skipping.")
                skipped += 1
                continue
                
            if args.dry_run:
                logging.info(f"[DRY RUN] Successfully fetched code length: {len(code)} characters.")
                
            ext = EXTENSIONS.get(lang, 'txt')
            sub_dt = datetime.fromtimestamp(timestamp)
            file_time_str = sub_dt.strftime("%Y-%m-%d_%H-%M-%S")
            
            latest_file = os.path.join(problem_dir, f"latest.{ext}")
            sub_file = os.path.join(problem_dir, "submissions", f"{file_time_str}.{ext}")
            
            if not args.dry_run:
                with open(latest_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                with open(sub_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                
            readme_file = os.path.join(problem_dir, "README.md")
            if slug not in problems_cache:
                time.sleep(DELAY)
                content_html, tags = get_question_details(slug)
                if content_html is not None:
                    if args.dry_run:
                        logging.info(f"[DRY RUN] Successfully fetched HTML description (length {len(content_html)}) and tags: {tags}")
                    problems_cache[slug] = {'content_html': content_html, 'tags': tags}
                    save_cache(PROBLEMS_CACHE_FILE, problems_cache)
                else:
                    logging.error(f"Could not fetch description for {slug}.")
                    
            if not args.dry_run and not os.path.exists(readme_file) and slug in problems_cache:
                html_content = problems_cache[slug]['content_html']
                tags = problems_cache[slug]['tags']
                md_content = generate_markdown(title, q_id, slug, difficulty, html_content, tags)
                with open(readme_file, 'w', encoding='utf-8') as f:
                    f.write(md_content)
            
            date_str = sub_dt.isoformat()
            run_git_command(['add', dir_name])
            
            status = run_git_command(['status', '--porcelain', dir_name])
            if status:
                commit_msg = f"Add solution for {title} ({lang})"
                env = os.environ.copy()
                env['GIT_AUTHOR_DATE'] = date_str
                env['GIT_COMMITTER_DATE'] = date_str
                
                run_git_command(['commit', '-m', commit_msg], env=env)
                logging.info(f" -> Committed with exact date {date_str}")
            else:
                logging.info(" -> No changes to commit (already identical).")
            
            newly_processed.append(sub_id)
            processed_ids.add(sub_id)
            save_cache(CACHE_FILE, {'processed': list(processed_ids)})
            
            time.sleep(DELAY)
            
    except KeyboardInterrupt:
        logging.warning("Process interrupted by user. Progress saved.")
    finally:
        logging.info("=== Sync Summary ===")
        logging.info(f"Successfully processed: {len(newly_processed)}")
        logging.info(f"Skipped/Failed: {skipped}")
        if args.dry_run:
            logging.info("[DRY RUN] Dry run completed safely.")
        
        if AUTO_PUSH and len(newly_processed) > 0 and not args.dry_run:
            logging.info("Auto-pushing to remote...")
            current_branch = run_git_command(['branch', '--show-current'])
            if current_branch:
                run_git_command(['push', 'origin', current_branch], fatal=False)
            else:
                logging.warning("Could not determine current branch for pushing.")
            
if __name__ == '__main__':
    main()
