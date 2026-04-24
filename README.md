# screentime-analyzer

Analyse your iPhone screen time data — privately on your own machine, or send your data for a personalised report.

---

## Requirements

- macOS (Sonoma or later recommended)
- iPhone with **Share Across Devices** enabled: Settings → Screen Time → Share Across Devices
- Python 3.11+

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/screentime-analyzer.git
cd screentime-analyzer

# Core install (extraction + PDF reports)
pip install .

# With LLM agent support
pip install ".[agent]"
```

---

## Step 1 — Extract your data

```bash
screentime extract
```

This reads the binary Biome database at `~/Library/Biome/streams/restricted/App.InFocus` and writes `screentime.csv` with columns: `app`, `start_time`, `end_time`, `duration_seconds`.

Your CSV stays on your machine. Nothing is sent anywhere at this step.

---

## Step 2 — Choose your path

### Option A — Generate reports yourself (fully private)

All processing happens locally. No data leaves your machine.

```bash
# Full screen time PDF report (all apps)
screentime analyze

# Instagram doomscroll PDF report
screentime instagram

# LLM narrative report — only aggregated stats are sent to the API, not raw session data
export ANTHROPIC_API_KEY=sk-ant-...
screentime agent

# Deep-dive on a specific app
screentime agent --app com.google.ios.youtube

# Save the agent report to a file
screentime agent --output report.md
```

### Option B — Send your data for a report

If you'd rather have a report generated for you:

```bash
screentime submit
```

This creates a `screentime_submission_<date>.zip`. Then:

1. Open a new issue at [github.com/YOUR_USERNAME/screentime-analyzer/issues](https://github.com/YOUR_USERNAME/screentime-analyzer/issues)
2. Title: **Report Request**
3. Attach the `.zip` file
4. You'll receive a personalised PDF report back

> **Privacy note:** This shares your raw session data (app bundle IDs + timestamps). Use Option A if you prefer to keep your data private.

---

## All commands

| Command | What it does |
|---|---|
| `screentime extract` | Read Biome database → `screentime.csv` |
| `screentime analyze` | Generate full PDF report (all apps) |
| `screentime instagram` | Generate Instagram doomscroll PDF |
| `screentime agent` | LLM narrative analysis (aggregated stats only sent to API) |
| `screentime submit` | Package CSV for submission |

Run `screentime <command> --help` for options.

---

## What the reports cover

**`screentime analyze`**
Daily totals · top apps · category breakdown · day × hour heatmap · session length distributions · weekday vs weekend · first/last pickup times · binge session analysis · usage trend (linear regression)

**`screentime instagram`**
Session types (Glance / Scroll / Doomscroll / Binge) · doom streak detection · hourly heatmap · CDF of session lengths · first open of day · weekday vs weekend · daily intensity calendar

**`screentime agent`** (LLM)
Executive summary · overall patterns · top app analysis · time-of-day habits · session anatomy · app deep-dive · hidden time cost (hours/year) · specific actionable recommendations

---

## CSV format

| Column | Type | Description |
|---|---|---|
| `app` | string | iOS bundle ID (e.g. `com.burbn.instagram`) |
| `start_time` | ISO 8601 | Session start |
| `end_time` | ISO 8601 | Session end |
| `duration_seconds` | float | Session length in seconds |

---

## Project structure

```
screentime-analyzer/
├── src/
│   └── screentime_analyzer/
│       ├── cli.py          # `screentime` CLI entry point
│       ├── extract.py      # Biome → CSV extraction
│       ├── analyse.py      # Full PDF report
│       ├── instagram.py    # Instagram doomscroll PDF
│       └── agent.py        # LLM agent (stats → Claude → narrative)
├── tools/
│   ├── APOLLO/             # Alternative extraction tool (forensic)
│   └── screentime2csv/     # Alternative extraction via knowledgeC.db
├── agent_prompt.md         # System prompt that drives the LLM analysis
├── pyproject.toml
└── README.md
```

---

## License

MIT
