import { CONFIG } from '../config.js';

document.addEventListener('DOMContentLoaded', () => {
  const unauthSection = document.getElementById('unauth-section');
  const authSection = document.getElementById('auth-section');
  const authBtn = document.getElementById('auth-btn');
  const repoSelect = document.getElementById('repo-select');
  const linkBtn = document.getElementById('link-btn');
  const statusMsg = document.getElementById('status-msg');
  const ghUsername = document.getElementById('gh-username');
  const logsContainer = document.getElementById('logs-container');

  // Load existing settings
  chrome.storage.local.get(['githubToken', 'githubRepo', 'githubUsername', 'syncLogs'], (result) => {
    if (result.githubToken) {
      showAuthSection(result.githubUsername, result.githubToken, result.githubRepo);
    }
    
    if (result.syncLogs && result.syncLogs.length > 0) {
      renderLogs(result.syncLogs);
    }
  });

  // OAuth Flow
  authBtn.addEventListener('click', () => {
    if (CONFIG.CLIENT_ID === "YOUR_CLIENT_ID_HERE") {
      showStatus("Please update config.js with your Client ID first!", "error");
      return;
    }

    const redirectUrl = chrome.identity.getRedirectURL();
    const authUrl = \`https://github.com/login/oauth/authorize?client_id=\${CONFIG.CLIENT_ID}&redirect_uri=\${encodeURIComponent(redirectUrl)}&scope=repo\`;

    chrome.identity.launchWebAuthFlow({
      url: authUrl,
      interactive: true
    }, async (redirectUrlWithCode) => {
      if (chrome.runtime.lastError || !redirectUrlWithCode) {
        showStatus(chrome.runtime.lastError ? chrome.runtime.lastError.message : 'Auth failed', 'error');
        return;
      }

      const url = new URL(redirectUrlWithCode);
      const code = url.searchParams.get('code');
      
      if (code) {
        await exchangeCodeForToken(code);
      }
    });
  });

  async function exchangeCodeForToken(code) {
    showStatus("Exchanging token...", "");
    try {
      const response = await fetch('https://github.com/login/oauth/access_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          client_id: CONFIG.CLIENT_ID,
          client_secret: CONFIG.CLIENT_SECRET,
          code: code
        })
      });

      const data = await response.json();
      if (data.access_token) {
        // Fetch user data
        const userRes = await fetch('https://api.github.com/user', {
          headers: { 'Authorization': \`token \${data.access_token}\` }
        });
        const userData = await userRes.json();

        chrome.storage.local.set({
          githubToken: data.access_token,
          githubUsername: userData.login
        }, () => {
          showAuthSection(userData.login, data.access_token);
          showStatus('Successfully authenticated!', 'success');
        });
      } else {
        showStatus('Failed to get access token.', 'error');
      }
    } catch (e) {
      showStatus(e.message, 'error');
    }
  }

  async function showAuthSection(username, token, savedRepo = null) {
    unauthSection.classList.add('hidden');
    authSection.classList.remove('hidden');
    ghUsername.textContent = username;

    try {
      const response = await fetch('https://api.github.com/user/repos?sort=updated&per_page=100', {
        headers: { 'Authorization': \`token \${token}\` }
      });
      const repos = await response.json();
      
      repoSelect.innerHTML = '';
      repos.forEach(repo => {
        const option = document.createElement('option');
        option.value = repo.full_name;
        option.textContent = repo.full_name;
        if (savedRepo && repo.full_name === savedRepo) option.selected = true;
        repoSelect.appendChild(option);
      });

      repoSelect.disabled = false;
      linkBtn.disabled = false;
    } catch (e) {
      showStatus("Failed to load repos", "error");
    }
  }

  // Link Repo
  linkBtn.addEventListener('click', () => {
    const selectedRepo = repoSelect.value;
    if (selectedRepo) {
      chrome.storage.local.set({ githubRepo: selectedRepo }, () => {
        showStatus(\`Linked to \${selectedRepo}\`, 'success');
      });
    }
  });

  function showStatus(msg, type) {
    statusMsg.textContent = msg;
    statusMsg.className = type;
    setTimeout(() => { statusMsg.textContent = ''; statusMsg.className = ''; }, 3000);
  }

  function renderLogs(logs) {
    logsContainer.innerHTML = '';
    logs.slice(0, 10).forEach(log => {
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      const time = new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      const statusColor = log.status === 'Success' ? 'green' : 'red';
      entry.innerHTML = \`<strong>\${time}</strong> - <span style="color:\${statusColor}">\${log.status}</span>: \${log.message}\`;
      logsContainer.appendChild(entry);
    });
  }
});
