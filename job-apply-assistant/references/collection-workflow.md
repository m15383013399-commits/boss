# Collection Workflow

Use `scripts/collect_jobs.py` to convert recruiting pages into normalized job JSON for `run_phase1.py`.

## Supported Modes

### 1. HTML snapshot mode

Parse one or more saved HTML files:

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode html `
  --html-files "./snapshots/boss-search-1.html" `
  --output "./output/jobs.json"
```

Use this mode when:

- browser automation is not ready
- the user already saved page source from a logged-in session
- the site blocks direct scripted access

### 2. URL fetch mode

Fetch pages with `requests` and parse them:

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform liepin `
  --mode url `
  --urls "https://www.liepin.com/" `
  --output "./output/jobs.json"
```

Optional:

- pass `--cookie-header` when the user exports cookies from a logged-in browser

### 3. Browser mode

Open pages in a real browser and capture HTML after login:

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode browser `
  --browser chrome `
  --manual-login `
  --urls "https://www.zhipin.com/" `
  --snapshot-dir "./snapshots/boss" `
  --output "./output/jobs.json"
```

Use browser mode when:

- the page requires login
- the page needs client-side rendering
- the site blocks direct `requests`

### 4. Detached browser session and later attach

Use this when the user needs time to log in and navigate manually without keeping the capture command alive.

First launch a visible browser session with remote debugging:

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode browser `
  --session-launch `
  --browser chrome `
  --driver-path "./drivers/chromedriver.exe" `
  --browser-binary "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --user-data-dir "./job-apply-assistant/browser-profile" `
  --urls "https://www.bosszhipin.com/" `
  --output "./job-apply-assistant/output/browser-session.json"
```

Then, after the user has logged in and navigated to a search results page, attach and capture:

```powershell
python "./job-apply-assistant/scripts/collect_jobs.py" `
  --platform boss `
  --mode browser `
  --browser chrome `
  --driver-path "./drivers/chromedriver.exe" `
  --debugger-address "127.0.0.1:9222" `
  --urls "" `
  --wait-seconds 1 `
  --snapshot-dir "./snapshots/boss" `
  --output "./output/jobs.json"
```

In attach mode, the current tab is the one that gets captured. Open the target search results page before running the second command.

## Current Limitations

- Browser mode requires a working WebDriver.
- Live job detail expansion is not implemented yet.
- The parsers are heuristic and may need selector updates as site HTML changes.

## Recommended Near-Term Flow

1. Start with HTML snapshots from pages that the user can open while logged in.
2. Parse snapshots into normalized JSON.
3. Feed that JSON into `run_phase1.py`.
4. After selectors are stable, enable browser capture and later message sending.
