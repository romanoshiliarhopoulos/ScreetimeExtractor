## ── screentime-analyzer Makefile ─────────────────────────────────────────────
##
##  make install          Install the package + all dependencies
##  make extract          Extract data from macOS Biome → screentime.csv
##  make charts           Generate both PDF reports (all apps + Instagram)
##  make charts-all       Alias for charts
##  make charts-instagram Instagram doomscroll PDF only
##  make agent            Run LLM analysis via the Anthropic API (needs ANTHROPIC_API_KEY)
##  make stats            Dump aggregated stats JSON to stdout — paste into any chatbot
##  make chatbot-prompt   Write a ready-to-paste prompt file for Claude.ai / ChatGPT
##  make open             Open the generated PDFs in Preview
##  make clean            Remove generated CSV and PDF files
##  make help             Show this message

CSV        ?= screentime.csv
REPORT_PDF ?= screentime_report.pdf
IG_PDF     ?= instagram_report.pdf
AGENT_OUT  ?= agent_report.md
STATS_JSON ?= doomscroll_stats.json
CHATBOT_PROMPT ?= chatbot_prompt.txt
APP        ?= com.burbn.instagram
MODEL      ?= claude-opus-4-6

.PHONY: help install extract charts charts-all charts-instagram agent stats chatbot-prompt open clean

help:
	@grep -E '^##' Makefile | sed 's/^## //'

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	pip install -e ".[agent]"

# ── Data ──────────────────────────────────────────────────────────────────────

extract:
	screentime extract --output $(CSV)

# ── Charts ────────────────────────────────────────────────────────────────────

charts: charts-all

charts-all: $(CSV)
	screentime analyze  --csv $(CSV) --output $(REPORT_PDF)
	screentime instagram --csv $(CSV) --output $(IG_PDF)
	@echo ""
	@echo "Reports written:"
	@echo "  $(REPORT_PDF)"
	@echo "  $(IG_PDF)"

charts-instagram: $(CSV)
	screentime instagram --csv $(CSV) --output $(IG_PDF)

# ── Agent (Anthropic API) ─────────────────────────────────────────────────────

agent: $(CSV)
	@if [ -z "$$ANTHROPIC_API_KEY" ]; then \
		echo "ERROR: ANTHROPIC_API_KEY is not set."; \
		echo "Run: export ANTHROPIC_API_KEY=sk-ant-..."; \
		exit 1; \
	fi
	screentime agent --csv $(CSV) --app $(APP) --model $(MODEL) --output $(AGENT_OUT)
	@echo ""
	@echo "Agent report saved to $(AGENT_OUT)"

# ── Chatbot helpers (no API key needed) ──────────────────────────────────────
#   Use these to paste the analysis into Claude.ai, ChatGPT, or any chatbot.

# Dump just the stats JSON — paste it into any chatbot alongside the system prompt.
stats: $(CSV)
	@python3 -c "\
import json, sys; \
sys.path.insert(0, 'src'); \
from screentime_analyzer.agent import build_doomscroll_stats; \
stats = build_doomscroll_stats('$(CSV)', '$(APP)'); \
print(json.dumps(stats, indent=2))" | tee $(STATS_JSON)
	@echo ""
	@echo "Stats also written to $(STATS_JSON)"

# Combine the system prompt + stats JSON into one file ready to paste.
chatbot-prompt: $(CSV)
	@python3 -c "\
import json, sys; \
sys.path.insert(0, 'src'); \
from screentime_analyzer.agent import build_doomscroll_stats; \
from pathlib import Path; \
stats = build_doomscroll_stats('$(CSV)', '$(APP)'); \
prompt_path = Path('agent_prompt.md'); \
system = prompt_path.read_text() if prompt_path.exists() else ''; \
out = '=== SYSTEM PROMPT ===\n\n' + system; \
out += '\n\n=== YOUR DATA ===\n\n'; \
out += 'Here are my doomscrolling statistics. Please write the full analysis report.\n\n'; \
out += '\`\`\`json\n' + json.dumps(stats, indent=2) + '\n\`\`\`'; \
Path('$(CHATBOT_PROMPT)').write_text(out); \
print('Chatbot prompt written to $(CHATBOT_PROMPT)'); \
print('Open it, copy everything, and paste into Claude.ai or ChatGPT.')"

# ── Utilities ─────────────────────────────────────────────────────────────────

open:
	@[ -f $(REPORT_PDF)  ] && open $(REPORT_PDF)  || echo "$(REPORT_PDF) not found — run make charts first"
	@[ -f $(IG_PDF)      ] && open $(IG_PDF)       || echo "$(IG_PDF) not found — run make charts first"
	@[ -f $(AGENT_OUT)   ] && open $(AGENT_OUT)    || true

clean:
	rm -f $(CSV) $(REPORT_PDF) $(IG_PDF) $(AGENT_OUT) $(STATS_JSON) $(CHATBOT_PROMPT)
	@echo "Cleaned generated files."

# ── Guard: require CSV to exist ───────────────────────────────────────────────

$(CSV):
	@echo "$(CSV) not found. Run 'make extract' first."
	@exit 1
