# AY Policy Bot — Elevate Performance Academy

Monitors UK regulatory sources, detects gaps in Elevate's policy documents, drafts corrections, and routes them through a human-review gate before publishing.

## Demo slice (13 June 2026)

Detects the confirmed ADA jurisdiction error in the Accessibility and Inclusiveness Policy, drafts the correction, emails Malachi for approval, and publishes the approved version to Google Drive.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment variables
Copy `.env` and fill in your values:
```
ANTHROPIC_API_KEY=your-ay-api-key
REVIEWER_EMAIL=malachiavstreih@gmail.com
SENDER_EMAIL=your-gmail-address
APPROVE_BASE_URL=https://your-railway-url.railway.app/approve
```

### 3. Set up Google OAuth
- Go to console.cloud.google.com
- Create a project → Enable Drive API + Gmail API + Docs API
- Create OAuth credentials (Desktop app) → download as `credentials.json`
- Place `credentials.json` in the project root
- First run will open a browser for Google login — after that `token.json` handles it

### 4. Run the bot
```bash
cd src
python main.py
```

### 5. Run the approval webhook (separate terminal)
```bash
cd src
python approve_endpoint.py
```

## File structure

```
policy-bot/
├── src/
│   ├── main.py               # Orchestrator — run this
│   ├── read_policy.py        # Reads policy from Google Drive
│   ├── detect_gap.py         # Detects compliance gaps
│   ├── draft_correction.py   # Drafts corrections via Claude API
│   ├── send_review.py        # Sends review email via Gmail
│   ├── approve_endpoint.py   # Flask webhook for approve/reject
│   └── publish_draft.py      # Writes approved correction to Google Drive
├── data/
│   └── pending_reviews.json  # Tracks pending and actioned reviews
├── logs/                     # Run logs
├── .env                      # API keys (never commit this)
├── .gitignore
├── requirements.txt
└── README.md
```

## Cost estimate
- Claude API: ~£2–8/month
- Railway hosting: ~£0–5/month
- Gmail + Drive API: free
- **Total: under £13/month**
