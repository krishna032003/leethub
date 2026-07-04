<div align="center">
  <h1>🚀 LeetHub Sync</h1>
  <p><b>A seamless integration to automatically synchronize your LeetCode journey with GitHub.</b></p>
</div>

---

## 🌟 Overview

**LeetHub Sync** is a powerful two-part tool suite designed to completely automate your portfolio. It ensures every problem you solve is safely documented in GitHub with a clean, professional directory structure.

It consists of two main components:
1. **Web Extension (Real-time Sync):** A lightweight browser extension that runs silently in the background. The exact moment you hit "Submit" on LeetCode and receive an "Accepted" verdict, it instantly pushes the code to your GitHub repo.
2. **Historical Sync Script (Python):** A bulk downloading tool to fetch your *entire past history* of LeetCode submissions and recreate them as chronological Git commits.

---

## ⚡ 1. The Web Extension (Real-time Sync)

Never worry about manually copying and pasting your solutions again. The extension listens for successful submissions and securely commits them via the GitHub API.

### 🔧 Installation

1. Clone or download this repository to your local machine.
2. Open Google Chrome or Microsoft Edge and navigate to `chrome://extensions/`.
3. Toggle **Developer mode** to ON (usually in the top right corner).
4. Click **Load unpacked** in the top left.
5. Select the root folder of this repository (the folder containing `manifest.json`).

### ⚙️ Configuration

1. Click the LeetHub Sync extension icon in your browser toolbar.
2. Enter your **GitHub Personal Access Token**.
   > *To generate a token, go to GitHub -> Settings -> Developer settings -> Personal access tokens (classic). Generate a new token and ensure you check the `repo` scope.*
3. Enter your target repository in the format `username/repository` (e.g., `krishna032003/Krishna-Codes`).
4. Click **Save Settings**. 

You're done! Go solve a problem on LeetCode, and watch it magically appear on GitHub.

---

## 🕰️ 2. Historical Sync (Python Script)

If you have months or years of prior LeetCode history, the web extension cannot retroactively fetch them. That is where the Python script comes in.

### 🚀 Usage

1. Navigate to the `historical-sync/` directory.
2. Duplicate `.env.example` to a new file named `.env`.
3. Fill in your `LEETCODE_SESSION`, `CSRF_TOKEN`, and the `REPO_PATH` where your target repository is cloned locally.
4. Install dependencies and run the script:
   ```bash
   pip install -r requirements.txt
   python sync_leetcode.py
   ```

For highly detailed instructions, refer to the [Historical Sync README](historical-sync/README.md).

---

## 📁 Repository Architecture

All synced solutions (whether from the extension or the Python script) strictly adhere to this clean, scalable architecture:

```text
0001-two-sum/
├── README.md                     # Contains the official problem description & topic tags
├── latest.cpp                    # Overwritten with your most recent accepted solution
└── submissions/
    ├── 2021-04-15_14-30-22.cpp   # Permanent historical snapshots
    └── 2023-11-02_09-15-10.cpp
```

## 📜 License
MIT License
