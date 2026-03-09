---
name: market-research
description: |
  Run competitive and market research for any industry. Use when a founder
  wants deep market analysis, competitive intelligence, or a strategy document.
  Takes an industry name and competitor domains as input.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
---

# Market Research Skill

You are running a multi-phase competitive and market research workflow. The goal is to produce a strategy document that reads like it was written by someone who spent months in the industry.

## Step 1: Parse Input

Parse `$ARGUMENTS` to extract:
- **Industry/market** (required) — the first quoted string or unquoted phrase before any domain-like arguments
- **Competitor domains** (optional) — comma-separated domains (e.g., `appfolio.com, buildium.com`)

Examples of valid invocations:
- `/market-research property management software appfolio.com, buildium.com, rentmanager.com`
- `/market-research "vertical SaaS for dentists" dentrix.com, opendental.com`
- `/market-research logistics fleet management`

**If no competitor domains are provided:**
Warn the user that providing competitor domains produces significantly better results. Use AskUserQuestion to ask them to provide a list of 2-8 competitor domains. Only proceed without domains if the user explicitly confirms they want auto-discovery.

## Step 2: Check Prerequisites

1. Verify `EXA_API_KEY` is set in the environment:
   ```bash
   echo $EXA_API_KEY | head -c 5
   ```
   If not set, tell the user: "Set your Exa API key with `export EXA_API_KEY=your_key`. Get one at https://exa.ai"

2. Check Python 3 is available:
   ```bash
   python3 --version
   ```

3. Ensure exa-py is installed:
   ```bash
   pip3 install -q exa-py 2>/dev/null
   ```

## Step 3: Run Exa Research Script

Run the research data collection script. The script uses a research-first architecture:
- **4 Research API tasks** run in parallel for deep analysis (competitive intelligence, customer voice, market dynamics, competitive moats)
- **3 Search API calls** run while research tasks process (similar companies, landing pages, tweets)

Ensure dependencies are installed, then run:

```bash
SKILL_DIR="$HOME/.claude/skills/market-research"
pip3 install -q exa-py pydantic 2>/dev/null
python3 "$SKILL_DIR/scripts/exa_research.py" \
  --industry "INDUSTRY_HERE" \
  --domains "DOMAIN1,DOMAIN2,DOMAIN3" \
  --output research_data.json
```

If `--domains` is empty, omit the flag — the script will auto-discover competitors.

The script logs progress to stderr. Let the user know research is underway and share progress as it streams. This typically takes 90-180 seconds. Budget: ~$1.50-2.50 per run.

## Step 4: Load Research Data

Read the generated `research_data.json` file. This contains:

### Search-based data
- `metadata` — industry, domains, timing, `research_costs` breakdown, `total_research_cost`
- `similar_companies` — discovered competitors via find_similar
- `landing_pages` — competitor homepage content
- `market_conversation` — tweets and social discussion

### Legacy keys (bridged from research output for backward compatibility)
- `case_studies` — flattened from research_competitive_intelligence
- `industry_news` — flattened from research_market_dynamics
- `expert_perspectives` — flattened from research_market_dynamics
- `customer_voice` — flattened from research_customer_voice
- `deep_research` — deprecated (always None)

### Structured research output (prefer these over legacy keys)
- `research_competitive_intelligence` — per-competitor profiles (target customer, value prop, differentiator, pricing, recent moves), case study insights, positioning gaps, underserved segments
- `research_customer_voice` — per-competitor sentiment (praise/complaint themes, switch reasons, notable quotes), universal complaints, unmet needs. **This is the highest-signal data — spend extra analytical effort here.**
- `research_market_dynamics` — trends with category/evidence/impact/timeframe, expert perspectives, predictions, notable news
- `research_competitive_moats` — per-competitor moat analysis (switching costs, network effects, scale advantages, data moats, brand strength, cornered resources), weakest moats marketwide, power vacuums, new entrant opportunities. **Feed this directly into Stage 3 (Seven Powers Analysis).**

## Step 5: Execute Questioning Chain

Read the questioning chain prompts from the skill directory:

```
~/.claude/skills/market-research/references/questioning-chain.md
```

Execute all five stages sequentially, using the research data as context:

### Stage 1: The Unspoken Insight
- Replace `{{industry}}` and `{{competitors}}` with actual values
- Generate 1-2 paragraphs
- Self-check: if the insight could apply to any industry, rewrite it

### Stage 2: Foundational Assumptions
- Reference Stage 1 output explicitly
- Generate 3 structural assumptions with all 4 sub-points each
- Each assumption must be specific to this market

### Stage 3: Seven Powers Analysis
- Reference Stages 1 and 2
- Apply Hamilton Helmer's Seven Powers framework to each competitor
- For each competitor: identify which powers they hold (with evidence), rate durability
- Identify which powers no competitor holds and the biggest power vacuum for a new entrant

### Stage 4: Investor Destruction Test
- Reference Stages 1, 2, and 3
- Generate 5 sharp Q&A pairs
- Rate each answer's evidence quality (STRONG/MODERATE/WEAK)
- Identify gaps explicitly

### Stage 5: Stress Test Loop
- Review Stage 4 answers
- Rate each 1-10
- Stress test anything scoring 7 or below
- **Maximum 2 iterations** — consolidate remaining gaps into Open Questions
- Do NOT loop more than twice

## Step 6: Generate Output Document

Read the output template:

```
~/.claude/skills/market-research/assets/output-template.md
```

Populate every section using:
- Research data for factual sections (Competitive Landscape, Case Studies, Customer Voice, Market Dynamics)
- Questioning chain outputs for analytical sections (Unspoken Insight, Foundational Assumptions, Seven Powers Analysis, Stress Test)
- Consolidated gaps for Open Questions
- All source URLs for the Sources section

Follow the inline guidance comments in the template for tone and length per section. Remove the HTML comments from the final output.

Save the completed document as:
```
market-research-[slug]-[YYYY-MM-DD].md
```

Where `[slug]` is the industry name lowercased with spaces replaced by hyphens (e.g., `market-research-property-management-software-2026-03-08.md`). Save in the user's current working directory.

## Step 7: Present Summary

After saving, tell the user:
1. Where the file was saved
2. A 3-4 sentence summary of the most important findings
3. How many sources were analyzed (from metadata)
4. Suggest they review the "Gaps & Open Questions" section for areas that need primary research

## Important Notes

- **Do not hallucinate.** Every claim in the output must trace back to the research data. If the data doesn't support a conclusion, say so in the Gaps section.
- **Be specific.** Generic insights are a failure mode. Every section should contain details that are specific to this industry and these competitors.
- **Preserve source URLs.** The Sources section should link to actual pages from the research data.
- **Handle sparse data gracefully.** If a section has minimal research data, write a shorter section and note the gap rather than padding with speculation.
- **Customer voice is the highest-signal section.** Spend extra analytical effort here — patterns in customer complaints and praise often reveal the real competitive dynamics.
