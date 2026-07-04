chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'SYNC_SUBMISSION') {
    handleSubmission(request.data)
      .then(() => sendResponse({ status: 'Success' }))
      .catch((error) => sendResponse({ status: 'Error', message: error.message }));
    return true; // Indicates async response
  }
});

async function handleSubmission(data) {
  const { titleSlug, questionId, questionTitle, lang, code } = data;
  
  const result = await chrome.storage.local.get(['githubToken', 'githubRepo', 'syncLogs']);
  const token = result.githubToken;
  const repo = result.githubRepo;

  if (!token || !repo) {
    throw new Error('GitHub token or repository not configured.');
  }

  const paddedId = String(questionId).padStart(4, '0');
  const dirName = `${paddedId}-${titleSlug}`;
  
  // Extensions mapping
  const extMap = {
    'cpp': 'cpp', 'python3': 'py', 'python': 'py', 'java': 'java', 'c': 'c',
    'csharp': 'cs', 'javascript': 'js', 'typescript': 'ts', 'go': 'go',
    'ruby': 'rb', 'swift': 'swift', 'kotlin': 'kt', 'rust': 'rs', 'php': 'php',
    'sql': 'sql', 'mysql': 'sql', 'oracle': 'sql'
  };
  const ext = extMap[lang] || 'txt';
  
  const timestamp = new Date();
  const timeStr = timestamp.toISOString().replace(/[:.]/g, '-').slice(0, 19);
  
  // We will push to two paths: latest and submissions/
  const latestPath = `${dirName}/latest.${ext}`;
  const historyPath = `${dirName}/submissions/${timeStr}.${ext}`;
  
  const commitMsg = `Add solution for ${questionTitle} (${lang})`;

  try {
    // 1. Check if latest file exists to get its SHA (needed for updating)
    let latestSha = await getFileSha(token, repo, latestPath);
    
    // 2. Upload latest file
    await uploadFile(token, repo, latestPath, code, commitMsg, latestSha);
    
    // 3. Upload history file (never exists, so no SHA needed)
    await uploadFile(token, repo, historyPath, code, commitMsg);

    logSync(result.syncLogs, 'Success', `Synced ${questionTitle} (${lang})`);
  } catch (error) {
    logSync(result.syncLogs, 'Error', error.message);
    throw error;
  }
}

async function getFileSha(token, repo, path) {
  const url = `https://api.github.com/repos/${repo}/contents/${path}`;
  const response = await fetch(url, {
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json'
    }
  });

  if (response.status === 404) return null; // File doesn't exist
  if (!response.ok) throw new Error(`GitHub API error: ${response.statusText}`);
  
  const data = await response.json();
  return data.sha;
}

async function uploadFile(token, repo, path, content, message, sha = null) {
  const url = `https://api.github.com/repos/${repo}/contents/${path}`;
  
  // Base64 encode the content (Unicode safe)
  const base64Content = btoa(unescape(encodeURIComponent(content)));

  const body = {
    message: message,
    content: base64Content
  };
  
  if (sha) body.sha = sha;

  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(`Upload failed: ${errorData.message}`);
  }
}

function logSync(logs, status, message) {
  const currentLogs = logs || [];
  currentLogs.unshift({
    timestamp: Date.now(),
    status,
    message
  });
  
  chrome.storage.local.set({ syncLogs: currentLogs.slice(0, 50) });
}
