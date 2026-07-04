// Inject a script into the page context to intercept fetch requests
const script = document.createElement('script');
script.textContent = `
  const originalFetch = window.fetch;
  window.fetch = async function(...args) {
    const response = await originalFetch.apply(this, args);
    const url = args[0] instanceof Request ? args[0].url : args[0];
    
    // We want to intercept submission check requests to see if it's "Accepted"
    if (url.includes('/submissions/detail/') && url.includes('/check/')) {
      const clonedResponse = response.clone();
      clonedResponse.json().then(data => {
        if (data.state === 'SUCCESS' && data.status_msg === 'Accepted') {
          // It's accepted! Send a custom event to the content script
          window.dispatchEvent(new CustomEvent('LEETCODE_ACCEPTED', { detail: data }));
        }
      }).catch(e => console.error("Error parsing submission check", e));
    }
    return response;
  };
`;
(document.head || document.documentElement).appendChild(script);
script.remove();

// Listen for the custom event from our injected script
window.addEventListener('LEETCODE_ACCEPTED', async (e) => {
  console.log("LeetCode submission accepted!", e.detail);
  const submissionData = e.detail;
  const submissionId = submissionData.submission_id;
  
  // We need to fetch the submission code and question metadata
  // Since we are the content script, we can query the GraphQL API
  try {
    const details = await getSubmissionDetails(submissionId);
    if (!details) return;
    
    const payload = {
      titleSlug: details.question.titleSlug,
      questionId: details.question.questionId,
      questionTitle: details.question.title,
      lang: details.lang.name,
      code: details.code
    };
    
    // Send to background script to sync to GitHub
    chrome.runtime.sendMessage({ type: 'SYNC_SUBMISSION', data: payload }, (response) => {
      console.log("GitHub Sync Response:", response);
    });
  } catch (error) {
    console.error("Failed to fetch submission details for auto-sync", error);
  }
});

async function getSubmissionDetails(submissionId) {
  const query = \`
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
  \`;
  
  const response = await fetch('https://leetcode.com/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables: { submissionId } })
  });
  
  const json = await response.json();
  return json?.data?.submissionDetails;
}
