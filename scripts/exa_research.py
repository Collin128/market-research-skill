#!/usr/bin/env python3
"""
Exa-powered market research data collection.

Leads with 4 focused Research API tasks for deep analysis, supplemented by
3 search calls for capabilities the Research API can't replicate (find_similar,
raw content fetching, tweet category filter).

Usage:
    python3 exa_research.py --industry "property management software" \
        --domains "appfolio.com,buildium.com" --output research_data.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel
except ImportError:
    print("ERROR: pydantic not installed. Run: pip3 install pydantic>=2.0", file=sys.stderr)
    sys.exit(1)

try:
    from exa_py import Exa
except ImportError:
    print("ERROR: exa-py not installed. Run: pip3 install exa-py", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

seen_urls: set = set()


def log(msg: str):
    """Log progress to stderr so stdout stays clean for JSON."""
    print(f"[exa-research] {msg}", file=sys.stderr)


def root_domain(url: str) -> str:
    """Extract root domain from a URL."""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        parts = parsed.netloc.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return parsed.netloc
    except Exception:
        return url


def dedup_results(results: list) -> list:
    """Deduplicate results by URL, tracking globally."""
    unique = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(r)
    return unique


def safe_result_to_dict(result) -> dict:
    """Convert an Exa result object to a serializable dict."""
    d = {
        "title": getattr(result, "title", None),
        "url": getattr(result, "url", None),
        "published_date": getattr(result, "published_date", None),
        "author": getattr(result, "author", None),
    }
    if getattr(result, "text", None):
        d["text"] = result.text
    if getattr(result, "highlights", None):
        d["highlights"] = result.highlights
    return d


def exa_call(func, *args, retries=1, **kwargs):
    """Call an Exa API function with retry on rate limit."""
    for attempt in range(retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str:
                if attempt < retries:
                    log("Rate limited, waiting 2s before retry...")
                    time.sleep(2)
                    continue
            raise
    return None


# ---------------------------------------------------------------------------
# Pydantic Output Schemas for Research Tasks
# ---------------------------------------------------------------------------

# Task 1: Competitive Intelligence & Case Studies
class CompetitorProfile(BaseModel):
    domain: str
    target_customer: str
    value_proposition: str
    key_differentiator: str
    pricing_model: Optional[str] = None
    recent_moves: list[str] = []

class CaseStudyInsight(BaseModel):
    competitor: str
    customer_name: Optional[str] = None
    customer_segment: str
    pain_point_solved: str
    key_outcome: str
    source_url: Optional[str] = None

class CompetitiveIntelligenceOutput(BaseModel):
    competitor_profiles: list[CompetitorProfile]
    case_study_insights: list[CaseStudyInsight]
    positioning_gaps: list[str]
    underserved_segments: list[str]

# Task 2: Customer Voice & Sentiment
class CompetitorSentiment(BaseModel):
    competitor: str
    praise_themes: list[str]
    complaint_themes: list[str]
    switch_to_reasons: list[str]
    switch_away_reasons: list[str]
    notable_quotes: list[str]

class CustomerVoiceOutput(BaseModel):
    competitor_sentiment: list[CompetitorSentiment]
    universal_complaints: list[str]
    unmet_needs: list[str]
    sentiment_sources: list[str]

# Task 3: Market Dynamics & Trends
class MarketTrend(BaseModel):
    trend: str
    category: str
    evidence: list[str]
    impact_level: str
    timeframe: str

class MarketDynamicsOutput(BaseModel):
    trends: list[MarketTrend]
    expert_perspectives: list[str]
    key_predictions: list[str]
    notable_news: list[str]

# Task 4: Competitive Moats & Power Dynamics
class CompetitorMoat(BaseModel):
    competitor: str
    switching_costs: Optional[str] = None
    network_effects: Optional[str] = None
    scale_advantages: Optional[str] = None
    data_moats: Optional[str] = None
    brand_strength: Optional[str] = None
    cornered_resources: Optional[str] = None
    overall_moat_strength: str

class CompetitiveMoatsOutput(BaseModel):
    competitor_moats: list[CompetitorMoat]
    weakest_moats_marketwide: list[str]
    power_vacuums: list[str]
    new_entrant_opportunities: list[str]


# ---------------------------------------------------------------------------
# Research Task Instructions
# ---------------------------------------------------------------------------

def build_competitive_intelligence_instructions(industry: str, domains: List[str]) -> str:
    competitor_list = ", ".join(domains)
    return (
        f"Research the competitive landscape for the {industry} market. "
        f"Focus on these companies: {competitor_list}. "
        f"For each competitor, determine: "
        f"1) Their primary target customer segment and ideal customer profile "
        f"2) Their core value proposition — what they promise customers "
        f"3) Their key differentiator — what makes them unique vs alternatives "
        f"4) Their pricing model if publicly available "
        f"5) Recent strategic moves in the last 12 months (funding rounds, acquisitions, major product launches, partnerships) "
        f"\n\nAlso find case studies and customer success stories for these competitors. "
        f"For each case study found, identify the customer segment, the pain point that was solved, "
        f"and the key outcome or result achieved. Look both on each competitor's own website "
        f"and on third-party sites. "
        f"\n\nFinally, identify positioning gaps — areas where no competitor has a strong position — "
        f"and underserved customer segments that existing players are ignoring or poorly serving."
    )


def build_customer_voice_instructions(industry: str, domains: List[str]) -> str:
    competitor_list = ", ".join(domains)
    return (
        f"Research customer sentiment and reviews for companies in the {industry} market. "
        f"Focus on these competitors: {competitor_list}. "
        f"Search reviews on G2, Capterra, TrustRadius, Reddit, industry forums, and social media. "
        f"\n\nFor each competitor, identify: "
        f"1) Common praise themes — what customers consistently love "
        f"2) Common complaint themes — what customers consistently dislike or find frustrating "
        f"3) Switch-to reasons — why customers chose this product over alternatives "
        f"4) Switch-away reasons — why customers left this product for competitors "
        f"5) Notable quotes that capture the customer experience (include source) "
        f"\n\nAcross the entire market, identify: "
        f"- Universal complaints that affect multiple or all competitors "
        f"- Unmet needs that customers repeatedly ask for but no one delivers well "
        f"- List all review sites and forums where you found sentiment data"
    )


def build_market_dynamics_instructions(industry: str, domains: List[str]) -> str:
    competitor_list = ", ".join(domains)
    return (
        f"Research the key trends and dynamics shaping the {industry} market. "
        f"Relevant companies include: {competitor_list}. "
        f"\n\nIdentify significant trends in these categories: "
        f"- Technology shifts (new capabilities, AI/automation, platform changes) "
        f"- Regulatory changes (new laws, compliance requirements, industry standards) "
        f"- Buyer behavior changes (how purchasing decisions are evolving) "
        f"- Funding and M&A activity (who is getting funded, who is acquiring whom) "
        f"- Disruption risks (new entrants, adjacent market encroachment, business model innovation) "
        f"\n\nFor each trend, provide: the trend description, its category, concrete evidence "
        f"(specific examples, data points, or events), impact level (high/medium/low), "
        f"and timeframe (already happening, 1-2 years, 3-5 years). "
        f"\n\nAlso gather expert perspectives — what industry analysts, founders, and thought leaders "
        f"are saying about where this market is heading. Include key predictions and notable recent news."
    )


def build_competitive_moats_instructions(industry: str, domains: List[str]) -> str:
    competitor_list = ", ".join(domains)
    return (
        f"Analyze competitive moats and power dynamics for companies in the {industry} market. "
        f"Focus on: {competitor_list}. "
        f"Use Hamilton Helmer's Seven Powers framework as a lens. "
        f"\n\nFor each competitor, research and assess: "
        f"1) Switching costs — what makes it hard for customers to leave? (data lock-in, integrations, workflow dependency, contracts) "
        f"2) Network effects — does the product get better as more people use it? (marketplace dynamics, community, data network effects) "
        f"3) Scale advantages — do they benefit from scale in ways competitors can't match? (cost advantages, distribution, operational scale) "
        f"4) Data moats — do they have proprietary data that improves their product? (training data, benchmarks, usage data) "
        f"5) Brand strength — is their brand a meaningful competitive advantage? (trust, recognition, category association) "
        f"6) Cornered resources — do they control unique resources? (patents, exclusive partnerships, key talent, regulatory licenses) "
        f"7) Overall moat strength rating (strong/moderate/weak) with justification "
        f"\n\nAt the market level, identify: "
        f"- Which moats are weakest across all competitors (biggest vulnerability) "
        f"- Where power vacuums exist (areas where no one has established dominance) "
        f"- Best opportunities for a new entrant based on moat analysis"
    )


# ---------------------------------------------------------------------------
# Research Task Runner
# ---------------------------------------------------------------------------

def run_research_task(
    exa: Exa,
    name: str,
    instructions: str,
    output_schema,
    model: str = "exa-research",
    timeout_ms: int = 180000,
) -> dict:
    """Create a research task, poll until done, return parsed output + cost.

    Returns dict with keys: 'parsed' (Pydantic model dict or None),
    'cost' (cost dict or None), 'status' (str).
    """
    try:
        task = exa_call(
            exa.research.create,
            instructions=instructions,
            model=model,
            output_schema=output_schema,
        )
        log(f"  [{name}] Task created: {task.research_id} (model={model})")

        result = exa.research.poll_until_finished(
            task.research_id,
            poll_interval=5000,
            timeout_ms=timeout_ms,
            output_schema=output_schema,
        )

        if result.status == "completed":
            cost = None
            if hasattr(result, "cost_dollars") and result.cost_dollars:
                cost = {
                    "total": getattr(result.cost_dollars, "total", None),
                    "num_pages": getattr(result.cost_dollars, "num_pages", None),
                    "num_searches": getattr(result.cost_dollars, "num_searches", None),
                    "reasoning_tokens": getattr(result.cost_dollars, "reasoning_tokens", None),
                }

            parsed = None
            if hasattr(result, "parsed_output") and result.parsed_output:
                parsed = result.parsed_output.model_dump()
            elif hasattr(result, "output") and result.output:
                if hasattr(result.output, "parsed") and result.output.parsed:
                    parsed = result.output.parsed

            log(f"  [{name}] Completed (cost: ${cost['total']:.2f})" if cost and cost.get("total") else f"  [{name}] Completed")
            return {"parsed": parsed, "cost": cost, "status": "completed"}
        else:
            error_msg = getattr(result, "error", None) if hasattr(result, "error") else None
            log(f"  [{name}] Ended with status: {result.status}" + (f" — {error_msg}" if error_msg else ""))
            return {"parsed": None, "cost": None, "status": result.status}

    except TimeoutError:
        log(f"  [{name}] Timed out after {timeout_ms // 1000}s")
        return {"parsed": None, "cost": None, "status": "timeout"}
    except Exception as e:
        log(f"  [{name}] Failed: {e}")
        return {"parsed": None, "cost": None, "status": "error"}


# ---------------------------------------------------------------------------
# Search Functions (KEEP: 3 that Research API can't replace)
# ---------------------------------------------------------------------------

def search_similar_companies(exa: Exa, domains: List[str]) -> List[dict]:
    """Find similar companies using find_similar_and_contents."""
    log("Finding similar companies...")
    all_results = []
    seen_root_domains = set(root_domain(d) for d in domains)

    for domain in domains:
        try:
            url = f"https://{domain}" if "://" not in domain else domain
            response = exa_call(
                exa.find_similar_and_contents,
                url,
                num_results=5,
                text={"max_characters": 3000},
                exclude_source_domain=True,
            )
            for r in response.results:
                rd = root_domain(r.url)
                if rd not in seen_root_domains:
                    seen_root_domains.add(rd)
                    all_results.append(safe_result_to_dict(r))
                    if len(all_results) >= 20:
                        break
        except Exception as e:
            log(f"Warning: find_similar failed for {domain}: {e}")

        if len(all_results) >= 20:
            break

    results = dedup_results(all_results)
    log(f"Found {len(results)} similar companies")
    return results


def fetch_landing_pages(exa: Exa, domains: List[str]) -> List[dict]:
    """Fetch landing page content for each competitor domain."""
    log("Fetching competitor landing pages...")
    all_results = []

    for domain in domains:
        try:
            response = exa_call(
                exa.search_and_contents,
                domain,
                type="auto",
                include_domains=[domain],
                num_results=1,
                text={"max_characters": 10000},
            )
            for r in response.results:
                all_results.append(safe_result_to_dict(r))
        except Exception as e:
            log(f"Warning: landing page fetch failed for {domain}: {e}")

    results = dedup_results(all_results)
    log(f"Fetched {len(results)} landing pages")
    return results


def search_market_conversation(exa: Exa, industry: str) -> List[dict]:
    """Search for tweets/social conversation about the industry."""
    log("Searching market conversation (tweets)...")
    try:
        response = exa_call(
            exa.search_and_contents,
            industry,
            category="tweet",
            num_results=25,
            highlights={"num_sentences": 3},
        )
        results = dedup_results([safe_result_to_dict(r) for r in response.results])
        log(f"Found {len(results)} tweets")
        return results
    except Exception as e:
        log(f"Warning: tweet search failed: {e}")
        return []


def auto_discover_competitors(exa: Exa, industry: str) -> List[str]:
    """Discover competitor domains when none are provided."""
    log("Auto-discovering competitors...")
    try:
        response = exa_call(
            exa.search_and_contents,
            industry,
            category="company",
            num_results=15,
            text={"max_characters": 3000},
        )
        domains = []
        seen = set()
        for r in response.results:
            rd = root_domain(r.url)
            if rd not in seen:
                seen.add(rd)
                domains.append(rd)

        log(f"Discovered {len(domains)} competitor domains: {', '.join(domains)}")
        return domains
    except Exception as e:
        log(f"Error: auto-discovery failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Bridge: Convert structured research output to legacy format
# ---------------------------------------------------------------------------

def bridge_case_studies(intel: Optional[dict]) -> List[dict]:
    """Convert CompetitiveIntelligenceOutput to legacy case_studies format."""
    if not intel:
        return []
    return [
        {
            "title": f"{cs.get('competitor', 'Unknown')} — {cs.get('customer_segment', 'Case Study')}",
            "text": f"Pain point: {cs.get('pain_point_solved', 'N/A')}. Outcome: {cs.get('key_outcome', 'N/A')}.",
            "url": cs.get("source_url"),
            "competitor": cs.get("competitor"),
        }
        for cs in intel.get("case_study_insights", [])
    ]


def bridge_customer_voice(voice: Optional[dict]) -> List[dict]:
    """Convert CustomerVoiceOutput to legacy customer_voice format."""
    if not voice:
        return []
    results = []
    for cs in voice.get("competitor_sentiment", []):
        for quote in cs.get("notable_quotes", []):
            results.append({
                "title": f"Customer quote — {cs.get('competitor', 'Unknown')}",
                "text": quote,
                "competitor": cs.get("competitor"),
                "voice_category": "quote",
            })
        for complaint in cs.get("complaint_themes", []):
            results.append({
                "title": f"Complaint theme — {cs.get('competitor', 'Unknown')}",
                "text": complaint,
                "competitor": cs.get("competitor"),
                "voice_category": "negative",
            })
        for praise in cs.get("praise_themes", []):
            results.append({
                "title": f"Praise theme — {cs.get('competitor', 'Unknown')}",
                "text": praise,
                "competitor": cs.get("competitor"),
                "voice_category": "positive",
            })
    return results


def bridge_industry_news(dynamics: Optional[dict]) -> List[dict]:
    """Convert MarketDynamicsOutput to legacy industry_news format."""
    if not dynamics:
        return []
    return [
        {"title": item, "text": item}
        for item in dynamics.get("notable_news", [])
    ]


def bridge_expert_perspectives(dynamics: Optional[dict]) -> List[dict]:
    """Convert MarketDynamicsOutput to legacy expert_perspectives format."""
    if not dynamics:
        return []
    return [
        {"title": item, "text": item}
        for item in dynamics.get("expert_perspectives", [])
    ]


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(industry: str, domains: List[str], output_path: str):
    """Run the full research pipeline and write results to JSON."""
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        print("ERROR: EXA_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    exa = Exa(api_key)
    auto_discovered = False

    if not domains:
        domains = auto_discover_competitors(exa, industry)
        auto_discovered = True
        if not domains:
            print("ERROR: No competitor domains found or provided.", file=sys.stderr)
            sys.exit(1)

    log(f"Starting research for: {industry}")
    log(f"Competitors: {', '.join(domains)}")
    start_time = time.time()

    # ------------------------------------------------------------------
    # PHASE 1: Fire research tasks + run search calls
    # Research tasks are created and start running server-side immediately.
    # While they run (~60-120s), we execute the 3 search calls (~5-10s).
    # ------------------------------------------------------------------

    log("Phase 1: Creating research tasks...")
    task_ids = {}

    # Create all 4 research tasks (non-blocking — returns immediately)
    try:
        t1 = exa_call(
            exa.research.create,
            instructions=build_competitive_intelligence_instructions(industry, domains),
            model="exa-research",
            output_schema=CompetitiveIntelligenceOutput,
        )
        task_ids["competitive_intelligence"] = t1.research_id
        log(f"  [competitive_intelligence] Created: {t1.research_id}")
    except Exception as e:
        log(f"  [competitive_intelligence] Failed to create: {e}")

    try:
        t2 = exa_call(
            exa.research.create,
            instructions=build_customer_voice_instructions(industry, domains),
            model="exa-research-pro",
            output_schema=CustomerVoiceOutput,
        )
        task_ids["customer_voice"] = t2.research_id
        log(f"  [customer_voice] Created: {t2.research_id} (exa-research-pro)")
    except Exception as e:
        log(f"  [customer_voice] Failed to create: {e}")

    try:
        t3 = exa_call(
            exa.research.create,
            instructions=build_market_dynamics_instructions(industry, domains),
            model="exa-research",
            output_schema=MarketDynamicsOutput,
        )
        task_ids["market_dynamics"] = t3.research_id
        log(f"  [market_dynamics] Created: {t3.research_id}")
    except Exception as e:
        log(f"  [market_dynamics] Failed to create: {e}")

    try:
        t4 = exa_call(
            exa.research.create,
            instructions=build_competitive_moats_instructions(industry, domains),
            model="exa-research",
            output_schema=CompetitiveMoatsOutput,
        )
        task_ids["competitive_moats"] = t4.research_id
        log(f"  [competitive_moats] Created: {t4.research_id}")
    except Exception as e:
        log(f"  [competitive_moats] Failed to create: {e}")

    log(f"Phase 1: Running {len(task_ids)} research tasks. Executing search calls while they run...")

    # Run search calls while research tasks process server-side
    similar_companies = search_similar_companies(exa, domains)
    landing_pages = fetch_landing_pages(exa, domains)
    market_conversation = search_market_conversation(exa, industry)

    # ------------------------------------------------------------------
    # PHASE 2: Poll research tasks
    # ------------------------------------------------------------------

    log("Phase 2: Polling research tasks...")
    research_results = {}
    research_costs = {}

    # Task 1: Competitive Intelligence
    if "competitive_intelligence" in task_ids:
        try:
            result = exa.research.poll_until_finished(
                task_ids["competitive_intelligence"],
                poll_interval=5000,
                timeout_ms=180000,
                output_schema=CompetitiveIntelligenceOutput,
            )
            parsed = None
            cost = None
            if result.status == "completed":
                if hasattr(result, "parsed_output") and result.parsed_output:
                    parsed = result.parsed_output.model_dump()
                elif hasattr(result, "output") and result.output and hasattr(result.output, "parsed"):
                    parsed = result.output.parsed
                if hasattr(result, "cost_dollars") and result.cost_dollars:
                    cost = {"total": getattr(result.cost_dollars, "total", None)}
                log(f"  [competitive_intelligence] Completed" + (f" (${cost['total']:.2f})" if cost and cost.get("total") else ""))
            else:
                log(f"  [competitive_intelligence] Status: {result.status}")
            research_results["competitive_intelligence"] = parsed
            research_costs["competitive_intelligence"] = cost
        except Exception as e:
            log(f"  [competitive_intelligence] Poll failed: {e}")
            research_results["competitive_intelligence"] = None
            research_costs["competitive_intelligence"] = None

    # Task 2: Customer Voice (with pro→standard fallback)
    if "customer_voice" in task_ids:
        try:
            result = exa.research.poll_until_finished(
                task_ids["customer_voice"],
                poll_interval=5000,
                timeout_ms=180000,
                output_schema=CustomerVoiceOutput,
            )
            parsed = None
            cost = None
            if result.status == "completed":
                if hasattr(result, "parsed_output") and result.parsed_output:
                    parsed = result.parsed_output.model_dump()
                elif hasattr(result, "output") and result.output and hasattr(result.output, "parsed"):
                    parsed = result.output.parsed
                if hasattr(result, "cost_dollars") and result.cost_dollars:
                    cost = {"total": getattr(result.cost_dollars, "total", None), "model": "exa-research-pro"}
                log(f"  [customer_voice] Completed (pro)" + (f" (${cost['total']:.2f})" if cost and cost.get("total") else ""))
            else:
                log(f"  [customer_voice] Pro failed with status: {result.status}, retrying with exa-research...")
                parsed, cost = _retry_customer_voice_standard(exa, industry, domains)
            research_results["customer_voice"] = parsed
            research_costs["customer_voice"] = cost
        except Exception as e:
            log(f"  [customer_voice] Pro poll failed: {e}, retrying with exa-research...")
            parsed, cost = _retry_customer_voice_standard(exa, industry, domains)
            research_results["customer_voice"] = parsed
            research_costs["customer_voice"] = cost
    else:
        # Pro creation failed, try standard directly
        log("  [customer_voice] Pro creation failed, trying exa-research...")
        parsed, cost = _retry_customer_voice_standard(exa, industry, domains)
        research_results["customer_voice"] = parsed
        research_costs["customer_voice"] = cost

    # Task 3: Market Dynamics
    if "market_dynamics" in task_ids:
        try:
            result = exa.research.poll_until_finished(
                task_ids["market_dynamics"],
                poll_interval=5000,
                timeout_ms=180000,
                output_schema=MarketDynamicsOutput,
            )
            parsed = None
            cost = None
            if result.status == "completed":
                if hasattr(result, "parsed_output") and result.parsed_output:
                    parsed = result.parsed_output.model_dump()
                elif hasattr(result, "output") and result.output and hasattr(result.output, "parsed"):
                    parsed = result.output.parsed
                if hasattr(result, "cost_dollars") and result.cost_dollars:
                    cost = {"total": getattr(result.cost_dollars, "total", None)}
                log(f"  [market_dynamics] Completed" + (f" (${cost['total']:.2f})" if cost and cost.get("total") else ""))
            else:
                log(f"  [market_dynamics] Status: {result.status}")
            research_results["market_dynamics"] = parsed
            research_costs["market_dynamics"] = cost
        except Exception as e:
            log(f"  [market_dynamics] Poll failed: {e}")
            research_results["market_dynamics"] = None
            research_costs["market_dynamics"] = None

    # Task 4: Competitive Moats
    if "competitive_moats" in task_ids:
        try:
            result = exa.research.poll_until_finished(
                task_ids["competitive_moats"],
                poll_interval=5000,
                timeout_ms=180000,
                output_schema=CompetitiveMoatsOutput,
            )
            parsed = None
            cost = None
            if result.status == "completed":
                if hasattr(result, "parsed_output") and result.parsed_output:
                    parsed = result.parsed_output.model_dump()
                elif hasattr(result, "output") and result.output and hasattr(result.output, "parsed"):
                    parsed = result.output.parsed
                if hasattr(result, "cost_dollars") and result.cost_dollars:
                    cost = {"total": getattr(result.cost_dollars, "total", None)}
                log(f"  [competitive_moats] Completed" + (f" (${cost['total']:.2f})" if cost and cost.get("total") else ""))
            else:
                log(f"  [competitive_moats] Status: {result.status}")
            research_results["competitive_moats"] = parsed
            research_costs["competitive_moats"] = cost
        except Exception as e:
            log(f"  [competitive_moats] Poll failed: {e}")
            research_results["competitive_moats"] = None
            research_costs["competitive_moats"] = None

    # ------------------------------------------------------------------
    # PHASE 3: Assemble output JSON
    # ------------------------------------------------------------------

    log("Phase 3: Assembling output...")

    intel = research_results.get("competitive_intelligence")
    voice = research_results.get("customer_voice")
    dynamics = research_results.get("market_dynamics")
    moats = research_results.get("competitive_moats")

    total_research_cost = sum(
        (c or {}).get("total", 0) or 0
        for c in research_costs.values()
    )
    elapsed = time.time() - start_time

    data: Dict[str, Any] = {
        # Metadata
        "metadata": {
            "industry": industry,
            "domains": domains,
            "auto_discovered": auto_discovered,
            "timestamp": datetime.now().isoformat(),
            "research_costs": research_costs,
            "total_research_cost": round(total_research_cost, 2),
        },

        # From search calls (unchanged)
        "similar_companies": similar_companies,
        "landing_pages": landing_pages,
        "market_conversation": market_conversation,

        # Legacy keys (bridged from research output)
        "case_studies": bridge_case_studies(intel),
        "industry_news": bridge_industry_news(dynamics),
        "expert_perspectives": bridge_expert_perspectives(dynamics),
        "customer_voice": bridge_customer_voice(voice),
        "deep_research": None,  # deprecated

        # New structured research output
        "research_competitive_intelligence": intel,
        "research_customer_voice": voice,
        "research_market_dynamics": dynamics,
        "research_competitive_moats": moats,
    }

    # Summary stats
    total_results = sum(
        len(v) for k, v in data.items()
        if isinstance(v, list) and k != "metadata"
    )

    data["metadata"]["total_results"] = total_results
    data["metadata"]["total_urls_deduped"] = len(seen_urls)
    data["metadata"]["elapsed_seconds"] = round(elapsed, 1)

    log(f"Research complete: {total_results} results in {elapsed:.1f}s (research cost: ${total_research_cost:.2f})")

    # Write output
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    log(f"Output written to: {output_path}")


def _retry_customer_voice_standard(exa: Exa, industry: str, domains: List[str]):
    """Retry customer voice research with standard model as fallback."""
    try:
        result_data = run_research_task(
            exa,
            name="customer_voice_retry",
            instructions=build_customer_voice_instructions(industry, domains),
            output_schema=CustomerVoiceOutput,
            model="exa-research",
            timeout_ms=180000,
        )
        cost = result_data.get("cost")
        if cost:
            cost["model"] = "exa-research"
        return result_data.get("parsed"), cost
    except Exception as e:
        log(f"  [customer_voice_retry] Also failed: {e}")
        return None, None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Exa-powered market research")
    parser.add_argument("--industry", required=True, help="Industry/market to research")
    parser.add_argument("--domains", default="", help="Comma-separated competitor domains")
    parser.add_argument("--output", default="research_data.json", help="Output JSON path")
    args = parser.parse_args()

    domains = [d.strip() for d in args.domains.split(",") if d.strip()] if args.domains else []
    run_pipeline(args.industry, domains, args.output)


if __name__ == "__main__":
    main()
