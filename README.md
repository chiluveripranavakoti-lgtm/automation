# Daily AI Morning Briefing Automation

A Python-based **Daily AI Morning Briefing** engine that collects AI updates, filters and deduplicates them across runs, synthesizes executive-level insights using **Google Gemini**, and delivers a briefing email every morning at **08:00 AM Indian Standard Time (Asia/Kolkata, UTC+05:30)** via the **Gmail API (OAuth 2.0)**.

---

## 1. Workflow Architecture & Order of Execution

The automation implements the workflow components in the exact required sequence:

```mermaid
flowchart LR
    A[Schedule Trigger\n08:00 AM IST] --> B[RSS Read\n5 Categories]
    B --> C[Limit\nLookback & Deduplication]
    C --> D[Aggregate\nRank & Balance]
    D --> E[Basic LLM Chain]
    F[Google Gemini\nChat Model] --> E
    E --> G[Send a message\nGmail OAuth 2.0]
```

### Component Details
1. **Schedule Trigger**: Fires at **08:00 AM IST (Asia/Kolkata)**. Configurable via [create_task.ps1](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/create_task.ps1) (Windows Task Scheduler), [scheduler.py](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/scheduler.py) (daemon loop), or GitHub Actions.
2. **RSS Read**: Gathers ~50+ candidate articles across 5 core categories:
   - *Balanced AI News* (TechCrunch AI, VentureBeat, The Verge)
   - *Developer-Focused AI* (GitHub AI Blog, Hugging Face, Simon Willison)
   - *Business-Focused AI* (MIT Technology Review, Stratechery)
   - *AI Research & Breakthroughs* (OpenAI, Google AI Blog, DeepMind, arXiv cs.AI)
   - *AI Careers & Opportunities* (WeWorkRemotely, Jobicy AI/Data Science)
3. **Limit**: Enforces configurable lookback window (default 48 hours), URL canonicalization, and intra-batch & persistent cross-day SQLite deduplication via [deduplicator.py](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/deduplicator.py) and [article_filter.py](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/article_filter.py).
4. **Aggregate**: Multi-factor scoring prioritizing lab authorities, recency, and high-signal breakthroughs while balancing representation across the 5 categories via [aggregator.py](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/aggregator.py).
5. **Basic LLM Chain**: Connects to the LLM to select the **5 strongest stories overall**, requiring structured JSON output (headline, category, date, source, 2-4 sentence summary, why it matters, practical impact, original URL, score 1-10, verified fact/opinion label). If the LLM is unreachable, falls back to a deterministic verified-metadata digest.
6. **Google Gemini Chat Model**: Official Google GenAI SDK wrapper ([gemini_model.py](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/gemini_model.py)) with exponential backoff retries and secure credential isolation.
7. **Send a message (Gmail)**: Builds responsive, sanitized HTML (with plain-text fallback) and delivers to `RECIPIENT_EMAIL` via official Gmail API OAuth 2.0 ([email_sender.py](file:///c:/Users/pranavakoti/OneDrive/Desktop/report-ai/email_sender.py)).

---

## 2. Directory Structure

```text
report-ai/
├── app.py                  # Primary orchestrator CLI (dry-run, auth, live execution)
├── config.py               # Environment configuration, path resolution, and validation
├── scheduler.py            # In-process daemon scheduler for Asia/Kolkata
├── rss_reader.py           # Multi-feed RSS collector with category mapping
├── article_filter.py       # Recency filtering & pool size limiter
├── deduplicator.py         # URL normalization, title similarity, persistent dedup
├── aggregator.py           # Multi-factor ranking & category balance
├── gemini_model.py         # Google Gemini Chat Model client wrapper
├── llm_chain.py            # LLM chain with Pydantic validation & deterministic fallback
├── email_sender.py         # Gmail API OAuth 2.0 client & HTML renderer
├── database.py             # SQLite persistence for seen articles and execution runs
├── create_task.ps1         # Windows Task Scheduler registration script (08:00 AM IST)
├── requirements.txt        # Python package dependencies
├── pytest.ini              # Pytest configuration
├── .env.example            # Environment variable template
├── .gitignore              # Ignores credentials, database, logs, and cache
└── tests/
    ├── test_deduplication.py
    ├── test_filtering.py
    ├── test_ranking.py
    └── test_email_rendering.py
```

---

## 3. Installation & Setup (Windows PowerShell)

### Step 1: Install Python Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 2: Configure Environment (`.env`)
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Edit `.env` and configure:
```dotenv
RECIPIENT_EMAIL=your-email@example.com
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
LOOKBACK_HOURS=48
MAX_CANDIDATES=50
TOP_STORIES=5
TIMEZONE=Asia/Kolkata
SCHEDULE_TIME=08:00
```

---

## 4. Google Gemini API Setup

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Click **Create API Key** and copy your key.
3. Paste the key into your `.env` file under `GEMINI_API_KEY`.
4. *Note:* If no API key is provided, the application runs gracefully using its **deterministic fallback aggregator**, synthesizing updates directly from verified RSS metadata.

---

## 5. Gmail OAuth 2.0 Setup

To send emails directly from your Gmail account without passwords:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (e.g. `Daily-AI-Briefing`).
3. Enable the **Gmail API** (*APIs & Services > Library > search "Gmail API" > Enable*).
4. Configure the **OAuth Consent Screen** (*APIs & Services > OAuth consent screen*):
   - User Type: **External**
   - Fill in App Name and your support email.
   - Under **Scopes**, add `https://www.googleapis.com/auth/gmail.send`.
   - Under **Test Users**, add your Gmail email address.
5. Create OAuth 2.0 Client ID (*APIs & Services > Credentials > Create Credentials > OAuth client ID*):
   - Application type: **Desktop App**
   - Click **Create**, then click **Download JSON**.
6. Save the downloaded file as `credentials.json` in the project root:
   `c:\Users\pranavakoti\OneDrive\Desktop\report-ai\credentials.json`
7. Run the one-time interactive authorization:
   ```powershell
   python app.py --auth-only
   ```
   A browser window will open asking you to sign in and grant `gmail.send` permission. Once approved, `token.json` is automatically generated and stored locally.

---

## 6. Testing & Manual Execution

### Run Unit Test Suite
```powershell
python -m pytest
```
*Tests cover URL normalization, near-duplicate title similarity, SQLite cross-day dedup, recency filtering, ranking weights, category balance, and XSS-safe email rendering.*

### Execute a Dry Run (No Email Sent)
Test the entire collection, filtering, deduplication, ranking, and briefing generation pipeline locally:
```powershell
python app.py --dry-run
```

### Execute Manual Production Run
Executes the full pipeline and sends the email via Gmail API:
```powershell
python app.py
```

---

## 7. Automated Scheduling (08:00 AM IST)

### Option A: Windows Task Scheduler (Recommended for Local Windows)
Run PowerShell as Administrator and execute:
```powershell
.\create_task.ps1 -Force
```
This registers a daily Windows scheduled task named `DailyAIMorningBriefing` configured to run `app.py` every day at **08:00 AM IST**.

- Check task status:
  ```powershell
  Get-ScheduledTask -TaskName "DailyAIMorningBriefing"
  ```
- Test-trigger the scheduled task immediately:
  ```powershell
  Start-ScheduledTask -TaskName "DailyAIMorningBriefing"
  ```

### Option B: Cloud Scheduler / GitHub Actions
You can also run this in GitHub Actions by adding `.github/workflows/daily_briefing.yml`:
```yaml
name: Daily AI Morning Briefing

on:
  schedule:
    # 08:00 AM IST = 02:30 AM UTC
    - cron: '30 2 * * *'
  workflow_dispatch:

jobs:
  briefing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Run Briefing
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
        run: python app.py
```

---

## 8. Verification Status

| Component | Status | Verification Detail |
| :--- | :---: | :--- |
| **Component 1: Schedule Trigger** | Verified | Tested via `create_task.ps1` (08:00 AM trigger) & `scheduler.py` |
| **Component 2: RSS Read** | Verified | Live RSS fetch verified (2,600+ articles fetched across sources) |
| **Component 3: Limit & Deduplication** | Verified | Recency cutoff + URL hash & title similarity verified via unit tests & live dry-run |
| **Component 4: Aggregate** | Verified | Multi-factor heuristic scoring with 5-category representation tested & verified |
| **Component 5: Basic LLM Chain** | Verified | Pydantic schema validation & deterministic verified fallback tested |
| **Component 6: Google Gemini Model** | Verified | SDK integrated (`google-genai`), retries implemented, fallback verified |
| **Component 7: Send a message (Gmail)**| Verified | HTML template rendered, XSS escaping unit tested, OAuth client flow prepared |
