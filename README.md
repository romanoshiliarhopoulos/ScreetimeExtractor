# screentime-analyzer

Analyse your iPhone screen time data — privately on your own machine, or send your data for a personalised report.

---

## Requirements

- macOS (Sonoma or later recommended)
- iPhone with **Share Across Devices** enabled: Settings → Screen Time → Share Across Devices
- Python 3.11+
- Terminal with **Full Disk Access** (needed to read the Biome database)

> **Grant Full Disk Access:** System Settings → Privacy & Security → Full Disk Access → add Terminal (or iTerm2)

---

## Quick Start

```bash
git clone https://github.com/romanoshiliarhopoulos/ScreetimeExtractor.git
cd ScreetimeExtractor
make install    # install the package + all dependencies
make extract    # pull data from your iPhone → screentime.csv
make charts     # generate PDF reports
make open       # open them in Preview
```

---

## Step 1 — Install

```bash
make install
```

Installs the package and all Python dependencies (pandas, matplotlib, scipy, reportlab, anthropic, pyyaml, etc.).

---

## Step 2 — Extract your data

```bash
make extract
```

Reads the binary Biome database at `~/Library/Biome/streams/restricted/App.InFocus` and writes `screentime.csv`.

**Run this regularly** (weekly, monthly) to build up history. If `screentime.csv` already exists, new sessions are merged in and deduplicated — your data accumulates over time rather than being overwritten.

> Your terminal needs Full Disk Access or this step will fail with a permissions error.

---

## Step 3 — Configure which apps to analyse

Open `apps.yaml` in any text editor. It looks like this:

```yaml
report_title: "Social Media Doomscrolling Report"

apps:
  - name: Instagram
    bundle_id: com.burbn.instagram
    color: "#E1306C"

  - name: TikTok
    bundle_id: com.zhiliaoapp.musically
    color: "#010101"
```

**To add or remove apps**, edit the list. Each entry needs three fields:

| Field | What it is |
|---|---|
| `name` | Display name — shown in charts and the report title |
| `bundle_id` | The app's iOS identifier (see table below) |
| `color` | Any hex color code, e.g. `"#FF0000"` for red |

### Common bundle IDs

| App | Bundle ID |
|---|---|
| Instagram | `com.burbn.instagram` |
| TikTok | `com.zhiliaoapp.musically` |
| YouTube | `com.google.ios.youtube` |
| Twitter / X | `com.atebits.Tweetie2` |
| Reddit | `com.reddit.Reddit` |
| Snapchat | `com.toyopagroup.picaboo` |
| Facebook | `com.facebook.Facebook` |
| Threads | `com.burbn.barcelona` |

**Don't see your app?** Run this after extracting to list your most-used apps:

```bash
python3 -c "import pandas as pd; df=pd.read_csv('screentime.csv'); print(df['app'].value_counts().head(30))"
```

---

## Step 4 — Generate reports

```bash
make charts
```

Writes two PDF reports:
- `screentime_report.pdf` — full report across all apps
- `instagram_report.pdf` — doomscrolling deep-dive for your configured apps

Open them immediately:

```bash
make open
```

To regenerate only the doomscrolling report:

```bash
make charts-instagram
```

### What the doomscrolling report covers (18 pages)

| Page | What you see |
|---|---|
| Title | Overview stats, apps analysed, date range |
| Daily usage | Bar + 5-day rolling average |
| Weekly trends | Weekly totals + rolling median session length |
| Session types | Glance / Scroll / Doomscroll / Binge counts and hours |
| App comparison | Side-by-side stats across all configured apps |
| Hourly patterns | Sessions and time by hour of day |
| Day × Hour heatmap | When in the week usage is heaviest |
| Session distribution | Histogram + cumulative time chart |
| Monthly calendar | GitHub-style grid — darker = more time |
| Doom streaks | Duration distribution, when they happen, day-of-week |
| Streak calendar | Calendar view of which days had doom streaks |
| First open of day | What time you reach for the app first |
| Weekday vs weekend | Daily average + hourly profile comparison |
| Reopen loop | How quickly you reopen after closing |
| Session escalation | Do sessions get longer as the day goes on? |
| Night usage | 10pm–3am trend over time + by hour |
| Recovery days | How often you use it < 15 min or not at all |
| Daily intensity | Dot calendar — size and colour = minutes |

---

## Step 5 — LLM analysis (optional)

All statistics are computed locally. Only aggregated numbers (no raw session data) are sent to the API.

### Option A — Automatic via Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
make agent
```

Writes a narrative report to `agent_report.md`. Get an API key at [console.anthropic.com](https://console.anthropic.com).

To analyse a different app:

```bash
make agent APP=com.google.ios.youtube
```

### Option B — Paste into any chatbot (no API key needed)

```bash
make chatbot-prompt
```

Writes `chatbot_prompt.txt` — a single file with the system prompt and your stats JSON. Open it, copy everything, paste into [Claude.ai](https://claude.ai), ChatGPT, or any other chatbot.

To dump just the raw stats JSON:

```bash
make stats
```

---

## Option C — Send your data for a report

If you'd rather have a report generated for you:

1. Run `make extract` to get your CSV
2. Open a new issue at [github.com/romanoshiliarhopoulos/ScreetimeExtractor/issues](https://github.com/romanoshiliarhopoulos/ScreetimeExtractor/issues)
3. Title: **Report Request**, attach the CSV
4. You'll receive a personalised PDF report back

> **Privacy note:** This shares your raw session data (app bundle IDs + timestamps). Use Steps 4–5 above if you prefer to keep your data private.

---

## All commands

| Command | What it does |
|---|---|
| `make install` | Install the package and all dependencies |
| `make extract` | Read Biome database → `screentime.csv` |
| `make charts` | Generate both PDF reports |
| `make charts-instagram` | Generate doomscrolling PDF only |
| `make agent` | LLM narrative via Anthropic API → `agent_report.md` |
| `make chatbot-prompt` | Write ready-to-paste prompt for Claude.ai / ChatGPT |
| `make stats` | Dump aggregated stats JSON to stdout |
| `make open` | Open generated PDFs in Preview |
| `make clean` | Remove all generated CSV and PDF files |

Override defaults with variables:

```bash
make charts CSV=mydata.csv
make charts-instagram CONFIG=my_apps.yaml
make agent APP=com.google.ios.youtube MODEL=claude-sonnet-4-6
```

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
├── apps.yaml               # Configure which apps to analyse ← edit this
├── src/
│   └── screentime_analyzer/
│       ├── cli.py          # screentime CLI entry point
│       ├── extract.py      # Biome → CSV extraction
│       ├── analyse.py      # Full PDF report (all apps)
│       ├── instagram.py    # Doomscrolling PDF (configured apps)
│       └── agent.py        # LLM agent (stats → Claude → narrative)
├── agent_prompt.md         # System prompt for LLM analysis
├── Makefile
├── pyproject.toml
└── README.md
```

---

## License

MIT
