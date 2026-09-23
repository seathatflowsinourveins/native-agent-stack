import asyncio, json, time
from browser_use import Browser

async def main():
    results = []
    browser = Browser(headless=True)
    await browser.start()
    t0 = time.time()
    try:
        await browser.navigate_to("http://127.0.0.1:8317/greeting.html")
        title = await browser.get_current_page_title()
        results.append({"task": "navigate_fixture", "success": True, "ms": int((time.time()-t0)*1000), "title": title})
    except Exception as e:
        results.append({"task": "navigate_fixture", "success": False, "ms": int((time.time()-t0)*1000), "error": str(e)[:300]})

    t0 = time.time()
    try:
        await browser.navigate_to("https://example.com")
        title = await browser.get_current_page_title()
        results.append({"task": "navigate_public_site", "success": True, "ms": int((time.time()-t0)*1000), "title": title})
    except Exception as e:
        results.append({"task": "navigate_public_site", "success": False, "ms": int((time.time()-t0)*1000), "error": str(e)[:300]})
    await browser.stop()
    print(json.dumps(results, indent=1))

asyncio.run(main())
