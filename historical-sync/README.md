# LeetCode Historical Submissions Sync

This tool fetches **every accepted submission you've ever made** on LeetCode and commits them to your local Git repository. It perfectly complements tools like LeetHub v2 by filling in your past history. 

It preserves the problem title, difficulty, original code, and most importantly, sets the **Git commit date to match the exact time you originally solved the problem on LeetCode**.

## Features
- Fetches all historical accepted submissions using LeetCode APIs.
- Creates organized directories (`0001-two-sum/solution.cpp`).
- Generates a `README.md` with problem difficulty and description.
- Restores your GitHub contribution graph by backdating Git commits.
- Idempotent: Can be run multiple times. It remembers what it has processed.

## Prerequisites

- Python 3.7+ installed.
- Git installed and accessible from PowerShell.

## Setup Instructions

1. **Install Python dependencies:**
   Open PowerShell in this directory (`GitLeet`) and run:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Get your LeetCode Cookies:**
   - Go to [leetcode.com](https://leetcode.com) and log in.
   - Right-click anywhere on the page -> **Inspect** (or press F12) to open Developer Tools.
   - Go to the **Application** tab (or Storage tab).
   - Expand **Cookies** on the left panel and click on `https://leetcode.com`.
   - Find the value for `LEETCODE_SESSION` and copy it.
   - Find the value for `csrftoken` and copy it.

3. **Configure Environment Variables:**
   - Copy the `.env.example` file and rename it to `.env`:
     ```powershell
     cp .env.example .env
     ```
   - Open the new `.env` file and paste your cookie values.

## Running the Tool

To start syncing, simply run the Python script:
```powershell
py sync_leetcode.py
```
*(Note: If you get "Python was not found", you can use `py` instead of `python` on Windows, or disable the Python App Execution Alias in Windows Settings).*

The script will:
- Initialize a Git repository if one doesn't exist.
- Fetch all your submissions.
- Create files and commit them with historical dates.
- Save a `.sync_cache.json` file so it doesn't process duplicates if you run it again.

## Pushing to GitHub

Once the script finishes, push your newly imported history to GitHub:
```powershell
git remote add origin https://github.com/yourusername/your-repo-name.git
git push -u origin master  # or main
```

## Future Submissions

For future submissions, simply continue using the **LeetHub v2** Chrome extension. Since this script generates the exact same directory structure as LeetHub v2, they will work perfectly together in the same repository.
