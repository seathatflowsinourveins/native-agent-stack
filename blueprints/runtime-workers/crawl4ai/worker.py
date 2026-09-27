#!/usr/bin/env python3
"""Thin native extraction recipe, adapted from the upstream pricing example.

v0.9.4 docs/examples/llm_extraction_openai_pricing.py:15-53;
docs/md_v2/core/fit-markdown.md; extraction_strategy.py:556-691,784-835.
Filtering is a separate native crawl before extraction so empty fit content cannot
silently fall back to unfiltered markdown (async_webcrawler.py:925-935).
"""
import asyncio
import hashlib
import json
import math
import os
import re
import uuid
from pathlib import Path


def model_for(config, arm):
    settings = config["llm"] if arm == "primary" else config["comparison"]
    model = os.environ.get(settings["model_env"], settings["model"])
    if not re.fullmatch(r"cx/gpt-6(?:-[A-Za-z0-9]+)+", model):
        raise ValueError("OmniRoute worker routes must select a cx/gpt-6 model")
    return model


def extraction_args(config, arm, schema, session):
    """Native extra_args override, per v0.9.4 utils.py:1825-1837.

    force_json_response retains native JSON parsing; this strict schema replaces
    its weaker json_object request. The frozen schema closes every object.
    """
    extra = {
        # Native utils injects 0.01; the pinned LiteLLM fork omits None values.
        "temperature": None,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "crawl4ai_product", "strict": True, "schema": schema,
        }},
        "max_tokens": config["llm"]["max_tokens"],
        "timeout": config["llm"]["timeout_seconds"],
        "num_retries": 0,
        "extra_headers": {"x-omniroute-session": session, "Idempotency-Key": uuid.uuid4().hex},
    }
    if arm == "comparison":
        extra["reasoning_effort"] = config["comparison"]["reasoning_effort"]
    return extra


async def extract(config, arm, fixture_base, output, artifact_dir):
    model = model_for(config, arm)
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig, LLMConfig
    from crawl4ai.content_filter_strategy import PruningContentFilterLXML
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    root = Path(__file__).parent
    schema = json.loads((root / "e2e/schema.json").read_text())
    content = config["content"]
    session = "crawl4ai-" + uuid.uuid4().hex
    browser = BrowserConfig(browser_type="chromium", headless=True, verbose=True)
    crawl_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        excluded_tags=content["excluded_tags"],
        word_count_threshold=1,
        page_timeout=30000,
        markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilterLXML(
            threshold=content["pruning_threshold"],
            threshold_type=content["pruning_threshold_type"],
            min_word_threshold=content["min_word_threshold"],
        )),
    )
    rows, measurements = [], []
    output.write_text(json.dumps({"records": []}))
    async with AsyncWebCrawler(config=browser) as crawler:
        for index, page in enumerate(config["e2e"]["pages"]):
            url = fixture_base + "/" + page
            crawled = await crawler.arun(url=url, config=crawl_config)
            if not crawled.success or not crawled.markdown:
                raise ValueError("native crawl failed")
            fit = crawled.markdown.fit_markdown
            estimate = math.ceil(len(fit.split()) * content["word_token_rate"]) if fit else 0
            if not fit or len(fit) > content["max_fit_characters"] or estimate > content["chunk_token_threshold"]:
                raise ValueError("filtered content empty or exceeds the frozen one-chunk budget")
            (artifact_dir / f"page-{index}.fit.md").write_text(fit)
            strategy = LLMExtractionStrategy(
                llm_config=LLMConfig(provider=config["llm"]["provider_prefix"] + model,
                                     api_token=config["llm"]["api_token"], base_url=config["llm"]["base_url"],
                                     backoff_max_attempts=1),
                schema=schema,
                extraction_type="schema",
                input_format="fit_markdown",
                force_json_response=True,
                instruction="Extract exactly the current product described in the article. Return one JSON object matching the schema, with no wrapper or extra keys. Keep price_usd as a two-decimal string. Do not infer facts from navigation or historical promotions.",
                chunk_token_threshold=content["chunk_token_threshold"],
                overlap_rate=content["overlap_rate"],
                word_token_rate=content["word_token_rate"],
                apply_chunking=False,
                extra_args=extraction_args(config, arm, schema, session),
            )
            extracted = await asyncio.to_thread(strategy.run, url, [fit])
            (artifact_dir / f"page-{index}.raw.json").write_text(json.dumps(extracted))
            if not isinstance(extracted, list) or len(extracted) != 1 or not isinstance(extracted[0], dict):
                raise ValueError("native extraction did not return exactly one product")
            row = dict(extracted[0])
            # Native non-JSON parsing can attach error=False; do not remove errors.
            if row.get("error") is False:
                del row["error"]
            rows.append(row)
            output.write_text(json.dumps({"records": rows}, indent=2))
            measurements.append({
                "page": page,
                "raw_markdown_bytes": len(crawled.markdown.raw_markdown.encode()),
                "fit_markdown_bytes": len(fit.encode()),
                "fit_sha256": hashlib.sha256(fit.encode()).hexdigest(),
                "estimated_chunk_tokens": estimate,
            })
    return measurements


if __name__ == "__main__":
    # Model read-back for container.sh; importing this file makes no provider call.
    print(model_for(json.loads((Path(__file__).parent / "config/worker.json").read_text()), "primary"))
