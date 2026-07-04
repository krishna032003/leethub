document.addEventListener('DOMContentLoaded', () => {
  const tokenInput = document.getElementById('github-token');
  const repoInput = document.getElementById('github-repo');
  const saveBtn = document.getElementById('save-btn');
  const statusMsg = document.getElementById('status-msg');
  const logsContainer = document.getElementById('logs-container');

  // Load existing settings
  chrome.storage.local.get(['githubToken', 'githubRepo', 'syncLogs'], (result) => {
    if (result.githubToken) tokenInput.value = result.githubToken;
    if (result.githubRepo) repoInput.value = result.githubRepo;
    
    if (result.syncLogs && result.syncLogs.length > 0) {
      renderLogs(result.syncLogs);
    }
  });

  // Save settings
  saveBtn.addEventListener('click', () => {
    const token = tokenInput.value.trim();
    const repo = repoInput.value.trim();

    if (!token || !repo) {
      showStatus('Please fill in both fields.', 'error');
      return;
    }

    chrome.storage.local.set({
      githubToken: token,
      githubRepo: repo
    }, () => {
      showStatus('Settings saved successfully!', 'success');
    });
  });

  function showStatus(msg, type) {
    statusMsg.textContent = msg;
    statusMsg.className = type;
    setTimeout(() => {
      statusMsg.textContent = '';
      statusMsg.className = '';
    }, 3000);
  }

  function renderLogs(logs) {
    logsContainer.innerHTML = '';
    logs.slice(0, 10).forEach(log => {
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      
      const time = new Date(log.timestamp).toLocaleTimeString();
      const statusColor = log.status === 'Success' ? 'green' : 'red';
      
      entry.innerHTML = `<strong>${time}</strong> - <span style="color:${statusColor}">${log.status}</span>: ${log.message}`;
      logsContainer.appendChild(entry);
    });
  }
});
