# screentime-analyzer

Analyse your iPhone screen time data — privately on your own machine, or send your data for a personalised report.

---

## Requirements

- macOS (Sonoma or later recommended)
- iPhone with **Share Across Devices** enabled: Settings → Screen Time → Share Across Devices
- Python 3.11+

---

## Setup

```bash
git clone https://github.com/romanoshiliarhopoulos/ScreetimeExtractor.git
cd ScreetimeExtractor
make install
```

---

## Step 1 — Extract your data

```bash
make extract
```

Reads the binary Biome database at `~/Library/Biome/streams/restricted/App.InFocus` and writes `screentime.csv`.

> **Permissions:** Your terminal needs Full Disk Access. Go to **System Settings → Privacy & Security → Full Disk Access** and add Terminal (or iTerm2).

---

## Step 2 — Generate charts

```bash
make charts
```

Writes two PDF reports:
- `screentime_report.pdf` — full report across all apps
- `instagram_report.pdf` — Instagram doomscroll deep-dive

Open them immediately:

```bash
make open
```

To generate only the Instagram report:

```bash
make charts-instagram
```

---

## Step 3 — LLM analysis

All statistics are computed locally. Only aggregated numbers (no raw session data) are sent to the API.

### Option A — Automatic via Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make agent
```

Writes the narrative report to `agent_report.md`. Get an API key at [console.anthropic.com](https://console.anthropic.com).

To analyse a different app:

```bash
make agent APP=com.google.ios.youtube
```

### Option B — Paste into any chatbot (no API key needed)

```bash
make chatbot-prompt
```

Writes `chatbot_prompt.txt` — a single file containing the system prompt and your stats JSON. Open it, copy everything, and paste into [Claude.ai](https://claude.ai), ChatGPT, or any other chatbot.

To just dump the raw stats JSON:

```bash
make stats
```

---

## Option C — Send your data for a report

If you'd rather have a report generated for you:

```bash
screentime submit
```

Creates `screentime_submission_<date>.zip`. Then:

1. Open a new issue at [github.com/romanoshiliarhopoulos/ScreetimeExtractor/issues](https://github.com/romanoshiliarhopoulos/ScreetimeExtractor/issues)
2. Title: **Report Request**
3. Attach the `.zip` file
4. You'll receive a personalised PDF report back

> **Privacy note:** This shares your raw session data (app bundle IDs + timestamps). Use Steps 2–3 above if you prefer to keep your data private.

---

## All commands

| Command | What it does |
|---|---|
| `make install` | Install the package and all dependencies |
| `make extract` | Read Biome database → `screentime.csv` |
| `make charts` | Generate both PDF reports |
| `make charts-instagram` | Generate Instagram doomscroll PDF only |
| `make agent` | LLM narrative via Anthropic API → `agent_report.md` |
| `make chatbot-prompt` | Write ready-to-paste prompt for Claude.ai / ChatGPT |
| `make stats` | Dump aggregated stats JSON (for manual pasting) |
| `make open` | Open generated PDFs in Preview |
| `make clean` | Remove all generated CSV and PDF files |

Override defaults with variables:

```bash
make charts CSV=mydata.csv
make agent APP=com.google.ios.youtube MODEL=claude-sonnet-4-6
```

---

## What the reports cover

**`make charts` (full report)**
Daily totals · top apps · category breakdown · hourly heatmap · session length distributions · weekday vs weekend · first/last pickup times · binge session analysis · usage trend

**`make charts` (Instagram report)**
Session types (Glance / Scroll / Doomscroll / Binge) · doom streak detection · hourly heatmap · session length CDF · reopen loop · session escalation · first open of day · weekday vs weekend · daily intensity calendar

**`make agent` / `make chatbot-prompt` (LLM report)**
Numbers at a glance · overall usage · session anatomy (the binge paradox) · reopen loop · session escalation · doom streaks · time patterns (morning, night, weekday/weekend) · the real cost in hours · specific actionable recommendations

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
│       ├── cli.py          # screentime CLI entry point
│       ├── extract.py      # Biome → CSV extraction
│       ├── analyse.py      # Full PDF report
│       ├── instagram.py    # Instagram doomscroll PDF
│       └── agent.py        # LLM agent (stats → Claude → narrative)
├── agent_prompt.md         # System prompt for LLM analysis
├── Makefile                # All commands
├── pyproject.toml
└── README.md
```

---

## License

MIT
