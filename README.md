# Market Research Skill for Claude Code

A Claude Code skill that compresses weeks of competitive and market research into a structured strategy document. Type `/market-research [industry] [competitor domains]` and get back analysis that reads like it came from someone with years in the space.

Combines [Exa's](https://exa.ai) semantic search and research APIs for automated intelligence gathering with Claude's reasoning for a multi-stage analytical workflow.

## What You Get

A comprehensive strategy document covering:

- **Competitive Landscape** — positioning map, target customers, differentiators
- **Case Study Analysis** — who competitors are winning with and how
- **Customer Voice** — unfiltered reviews, complaints, praise, Reddit threads
- **Market Dynamics** — trends, funding, regulatory shifts
- **The Unspoken Insight** — what separates winners from losers in this market
- **Foundational Assumptions** — structural assumptions the market is built on and how they break
- **Seven Powers Analysis** — Hamilton Helmer's framework applied to each competitor's moats and durability
- **Investor Destruction Test** — 5 sharp questions that expose real risks, with evidence-based answers
- **Gaps & Open Questions** — what still needs primary research

## Setup

### Prerequisites

- [Claude Code](https://claude.ai/claude-code) installed
- Python 3
- An [Exa API key](https://exa.ai)

### Install

1. Clone this repo into your Claude Code skills directory:

```bash
git clone https://github.com/Collin128/market-research-skill.git ~/.claude/skills/market-research
```

2. Install the Python dependency:

```bash
pip3 install -r ~/.claude/skills/market-research/scripts/requirements.txt
```

3. Set your Exa API key:

```bash
export EXA_API_KEY=your_key_here
```

Add the export to your shell profile (`.zshrc`, `.bashrc`, etc.) to persist it.

## Usage

```
/market-research property management software appfolio.com, buildium.com, rentmanager.com
```

```
/market-research "vertical SaaS for dentists" dentrix.com, opendental.com
```

```
/market-research logistics fleet management
```

Providing competitor domains produces significantly better results. The skill will prompt you for domains if you don't include them.

## How It Works

1. **Discovery & Expansion** — Uses Exa's search API to find similar companies, pull landing pages, case studies, tweets, news, expert perspectives, and customer reviews/complaints
2. **Deep Research** — Uses Exa's Research API for structured competitive positioning, market trends, and customer pain point analysis
3. **Questioning Chain** — Runs a 5-stage analytical chain (Unspoken Insight → Foundational Assumptions → Seven Powers Analysis → Investor Destruction Test → Stress Test Loop)
4. **Output Generation** — Synthesizes everything into a clean strategy document saved as markdown

Total runtime is typically 2-5 minutes. Exa API cost is approximately $1.50-5.50 per run depending on the number of competitors.

## File Structure

```
market-research/
├── SKILL.md                          # Skill orchestration instructions
├── scripts/
│   ├── exa_research.py               # Exa API data collection
│   └── requirements.txt              # Python dependencies
├── references/
│   └── questioning-chain.md          # 5-stage analytical prompt chain
└── assets/
    └── output-template.md            # Output document template
```

## License

MIT
