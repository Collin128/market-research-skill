#!/usr/bin/env python3
"""
Exa-powered market research data collection.

Gathers competitive intelligence, customer voice, market dynamics, and deep
research for a given industry and set of competitor domains. Outputs a single
JSON file with all results deduplicated by URL.

Usage:
    python3 exa_research.py --industry "property management software" \
        --domains "appfolio.com,buildium.com" --output research_data.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

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
                    log(f"Rate limited, waiting 2s before retry...")
                    time.sleep(2)
                    continue
            raise
    return None


# ---------------------------------------------------------------------------
# Search Functions
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


def search_case_studies(exa: Exa, domains: List[str]) -> List[dict]:
    """Search for case studies on-site and off-site for each competitor."""
    log("Searching for case studies...")
    all_results = []

    for domain in domains:
        # On-site case studies
        try:
            response = exa_call(
                exa.search_and_contents,
                "case study OR customer story OR success story",
                include_domains=[domain],
                num_results=5,
                text={"max_characters": 8000},
            )
            for r in response.results:
                all_results.append(safe_result_to_dict(r))
        except Exception as e:
            log(f"Warning: on-site case study search failed for {domain}: {e}")

        # Off-site case studies
        company_name = domain.split(".")[0]
        try:
            response = exa_call(
                exa.search_and_contents,
                f"{company_name} case study OR customer story",
                exclude_domains=[domain],
                num_results=3,
                text={"max_characters": 5000},
            )
            for r in response.results:
                all_results.append(safe_result_to_dict(r))
        except Exception as e:
            log(f"Warning: off-site case study search failed for {domain}: {e}")

    results = dedup_results(all_results)
    log(f"Found {len(results)} case studies")
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


def search_industry_news(exa: Exa, industry: str) -> List[dict]:
    """Search for recent industry news."""
    log("Searching industry news...")
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    try:
        response = exa_call(
            exa.search_and_contents,
            industry,
            category="news",
            num_results=15,
            start_published_date=six_months_ago,
            text={"max_characters": 3000},
        )
        results = dedup_results([safe_result_to_dict(r) for r in response.results])
        log(f"Found {len(results)} news articles")
        return results
    except Exception as e:
        log(f"Warning: news search failed: {e}")
        return []


def search_expert_perspectives(exa: Exa, industry: str) -> List[dict]:
    """Search for expert/founder blog posts and perspectives."""
    log("Searching expert perspectives...")
    try:
        response = exa_call(
            exa.search_and_contents,
            industry,
            type="auto",
            category="personal site",
            num_results=10,
            text={"max_characters": 5000},
        )
        results = dedup_results([safe_result_to_dict(r) for r in response.results])
        log(f"Found {len(results)} expert perspectives")
        return results
    except Exception as e:
        log(f"Warning: expert perspective search failed: {e}")
        return []


def search_customer_voice(exa: Exa, industry: str, domains: List[str]) -> List[dict]:
    """Search for customer reviews, complaints, and sentiment per competitor."""
    log("Searching customer voice...")
    all_results = []

    query_templates = {
        "positive": ["{name} review", "{name} love OR recommend"],
        "negative": ["{name} complaints OR problems OR frustrating"],
        "fit": ["{name} best for OR perfect for", "{name} vs"],
        "anti_fit": ["{name} limitations OR switched from OR alternative"],
        "reddit": ["reddit {name}", "reddit {industry}"],
    }

    for domain in domains:
        company_name = domain.split(".")[0]

        for category, queries in query_templates.items():
            for query_template in queries:
                query = query_template.format(name=company_name, industry=industry)
                try:
                    response = exa_call(
                        exa.search_and_contents,
                        query,
                        type="auto",
                        num_results=3,
                        text={"max_characters": 2000},
                    )
                    for r in response.results:
                        d = safe_result_to_dict(r)
                        d["voice_category"] = category
                        d["competitor"] = domain
                        all_results.append(d)
                except Exception as e:
                    log(f"Warning: customer voice search failed ({query}): {e}")

    results = dedup_results(all_results)
    log(f"Found {len(results)} customer voice results")
    return results


def run_deep_research(exa: Exa, industry: str, domains: List[str]) -> Optional[dict]:
    """Run Exa Research API for structured deep research."""
    log("Starting deep research task...")
    competitor_list = ", ".join(domains)

    instructions = (
        f"Analyze the competitive landscape for the {industry} market. "
        f"Focus on these companies: {competitor_list}. "
        f"For each major player, identify: "
        f"1) Their primary target customer segment "
        f"2) Core value proposition and key differentiator "
        f"3) Pricing model (if publicly available) "
        f"4) Recent strategic moves (funding, acquisitions, product launches) "
        f"Also identify the 3-5 most significant trends shaping this market "
        f"in the last 12 months, including technology shifts, regulatory changes, "
        f"and customer behavior changes. "
        f"Finally, research the most common customer complaints and unmet needs "
        f"across these competitors."
    )

    try:
        task = exa_call(
            exa.research.create,
            instructions=instructions,
            model="exa-research-fast",
        )
        log(f"Research task created: {task.research_id}")

        result = exa.research.poll_until_finished(
            task.research_id,
            poll_interval=5000,
            timeout_ms=120000,
        )

        if result.status == "completed":
            log("Deep research completed")
            output = {}
            if hasattr(result, "output") and result.output:
                output["content"] = getattr(result.output, "content", None)
                output["parsed"] = getattr(result.output, "parsed", None)
            if hasattr(result, "cost_dollars"):
                output["cost_dollars"] = result.cost_dollars
            return output
        else:
            log(f"Warning: deep research ended with status: {result.status}")
            if hasattr(result, "error") and result.error:
                log(f"Error: {result.error}")
            return None

    except TimeoutError:
        log("Warning: deep research timed out after 120s")
        return None
    except Exception as e:
        log(f"Warning: deep research failed: {e}")
        return None


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

    data: Dict[str, Any] = {
        "metadata": {
            "industry": industry,
            "domains": domains,
            "auto_discovered": auto_discovered,
            "timestamp": datetime.now().isoformat(),
        },
        "similar_companies": [],
        "landing_pages": [],
        "case_studies": [],
        "market_conversation": [],
        "industry_news": [],
        "expert_perspectives": [],
        "customer_voice": [],
        "deep_research": None,
    }

    # Phase 1: Search API calls
    data["similar_companies"] = search_similar_companies(exa, domains)
    data["landing_pages"] = fetch_landing_pages(exa, domains)
    data["case_studies"] = search_case_studies(exa, domains)
    data["market_conversation"] = search_market_conversation(exa, industry)
    data["industry_news"] = search_industry_news(exa, industry)
    data["expert_perspectives"] = search_expert_perspectives(exa, industry)
    data["customer_voice"] = search_customer_voice(exa, industry, domains)

    # Phase 2: Deep Research API
    data["deep_research"] = run_deep_research(exa, industry, domains)

    # Summary stats
    total_results = sum(
        len(v) for k, v in data.items()
        if isinstance(v, list) and k != "metadata"
    )
    elapsed = time.time() - start_time

    data["metadata"]["total_results"] = total_results
    data["metadata"]["total_urls_deduped"] = len(seen_urls)
    data["metadata"]["elapsed_seconds"] = round(elapsed, 1)

    log(f"Research complete: {total_results} results in {elapsed:.1f}s")

    # Write output
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    log(f"Output written to: {output_path}")


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
