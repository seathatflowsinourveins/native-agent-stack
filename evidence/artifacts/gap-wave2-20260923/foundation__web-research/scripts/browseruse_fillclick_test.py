import asyncio, json, time
from browser_use import Browser
from browser_use.browser.events import TypeTextEvent, ClickElementEvent

async def main():
    results = []
    browser = Browser(headless=True)
    await browser.start()
    t0 = time.time()
    try:
        await browser.navigate_to("http://127.0.0.1:8317/greeting.html")
        # populate selector map
        summary = await browser.get_browser_state_summary()
        name_idx = await browser.get_index_by_id("name")
        greet_idx = await browser.get_index_by_id("greet")
        status_idx = await browser.get_index_by_id("status")
        selector_map = await browser.get_selector_map()
        name_node = selector_map.get(name_idx)
        greet_node = selector_map.get(greet_idx)
        status_node = selector_map.get(status_idx)
        results.append({
            "task": "resolve_indices",
            "success": all([name_idx is not None, greet_idx is not None, status_idx is not None]),
            "name_idx": name_idx, "greet_idx": greet_idx, "status_idx": status_idx,
        })

        await browser.event_bus.dispatch(TypeTextEvent(node=name_node, text="Gap Wave 2 Fix", clear=True))
        results.append({"task": "fill_name", "success": True, "ms": int((time.time()-t0)*1000)})

        t1 = time.time()
        await browser.event_bus.dispatch(ClickElementEvent(node=greet_node))
        results.append({"task": "click_greet", "success": True, "ms": int((time.time()-t1)*1000)})

        # read back status text via a fresh state summary / cdp evaluate
        cdp_session = await browser.get_or_create_cdp_session()
        eval_result = await cdp_session.cdp_client.send.Runtime.evaluate(
            params={"expression": "document.getElementById('status').textContent"},
            session_id=cdp_session.session_id,
        )
        status_text = eval_result.get("result", {}).get("value")
        results.append({"task": "read_status_after_click", "success": status_text == "Hello, Gap Wave 2 Fix!", "status_text": status_text})
    except Exception as e:
        import traceback
        results.append({"task": "error", "success": False, "error": str(e)[:500], "trace": traceback.format_exc()[-1500:]})
    await browser.stop()
    print(json.dumps(results, indent=1))

asyncio.run(main())
