import asyncio, json, time
from crawl4ai import AsyncWebCrawler

async def main():
    results = []
    async with AsyncWebCrawler() as crawler:
        t0 = time.time()
        try:
            r = await crawler.arun(url="http://127.0.0.1:8317/greeting.html")
            results.append({"task": "crawl_fixture", "success": r.success, "ms": int((time.time()-t0)*1000),
                             "status_code": r.status_code, "markdown_snippet": (r.markdown or "")[:200]})
        except Exception as e:
            results.append({"task": "crawl_fixture", "success": False, "ms": int((time.time()-t0)*1000), "error": str(e)[:300]})

        t0 = time.time()
        try:
            r = await crawler.arun(url="https://example.com")
            results.append({"task": "crawl_public_site", "success": r.success, "ms": int((time.time()-t0)*1000),
                             "status_code": r.status_code, "markdown_snippet": (r.markdown or "")[:200]})
        except Exception as e:
            results.append({"task": "crawl_public_site", "success": False, "ms": int((time.time()-t0)*1000), "error": str(e)[:300]})
    print(json.dumps(results, indent=1))

asyncio.run(main())
