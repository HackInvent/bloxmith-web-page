"""Real-shell editing, isolated page scripts and targeted WS refresh in Chromium."""

from pathlib import Path
import sys
import shutil
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
from playwright.sync_api import sync_playwright, expect as visible
from blocs import get_block_definition
from block_test_artifacts import artifact_path
from ui_smoke_common import (
    isolated_server, http_json, create_project_api, graph_payload, text_node, data_edge,
    node_payload_for_block, wait_for_run_predicate, stop_run_api,
    project_editor_url, wait_for_app_ready, expect,
)


def main():
    """Edit through the real shell and validate both the browser boundary and delivery UX."""
    with isolated_server() as server, sync_playwright() as playwright:
        # Exercise the exact-release host: bundled assets cannot detect a missing manifest.
        library = server.root_dir / "release-test-blocks"
        shutil.copytree(Path(__file__).resolve().parents[1], library / "web_page")
        management = "/api/application/block-management"
        http_json(server.base_url, management + "/settings", method="POST", payload={
            "block_sources": [{"id": "web-page-test", "type": "directory", "location": str(library)}]})
        candidates = http_json(server.base_url, management + "/discover", method="POST", payload={})["items"]
        http_json(server.base_url, management + "/install", method="POST", payload={
            "candidate_id": candidates[0]["candidate_id"]})
        node = node_payload_for_block(get_block_definition("web_page"))
        node["block_version"] = "0.1.0"
        node["position"] = {"x": 450, "y": 180}
        node["config"]["page"]["javascript"] += """
try { parent.document.title; document.body.dataset.parent = 'unsafe'; }
catch { document.body.dataset.parent = 'blocked'; }
try { document.cookie; document.body.dataset.cookie = 'unsafe'; }
catch { document.body.dataset.cookie = 'blocked'; }
fetch('/api/health').then(() => document.body.dataset.network = 'unsafe')
  .catch(() => document.body.dataset.network = 'blocked');
"""
        document = graph_payload("Web publication", [text_node("text-1", "Source", "Hello from the workflow", 70, 180), node],
                                 [data_edge("data-1", "text-1", 1, node["id"], 1)])
        project = create_project_api(server, document=document)["project"]
        graph_id, workspace_id = project["project_id"], project["workspace_project_id"]
        base = f"/api/web-pages/{workspace_id}/{graph_id}/1/{node['id']}"
        snapshot = http_json(server.base_url, base + "/snapshot")
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        try:
            page = context.new_page()
            requests, notifications, responses = [], [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("response", lambda response: responses.append(response.url))
            page.on("websocket", lambda socket: socket.on("framereceived", lambda value: notifications.append(value)))
            page.goto(server.base_url + snapshot["url"] + "?view=compact")
            frame = page.frame_locator("iframe")
            visible(frame.locator("h1")).to_have_text("Ma page web")
            visible(frame.locator("#detail")).to_have_text("Vue : compact")
            for probe in ("parent", "cookie", "network"):
                visible(frame.locator("body")).to_have_attribute("data-" + probe, "blocked")
            # Use the same persistent Run entry point as the editor, not the one-shot active API.
            run = http_json(server.base_url, f"/api/projects/{graph_id}/runs/prepare", method="POST", payload={})
            http_json(server.base_url, f"/api/runs/{run['run_id']}/active/control", method="POST", payload={
                "action": "publish_seed", "node_id": "text-1"})
            visible(frame.locator("pre")).to_have_text("Hello from the workflow", timeout=20000)
            http_json(server.base_url, f"/api/runs/{run['run_id']}/active/control", method="POST", payload={
                "action": "publish_output", "node_id": "text-1", "port_id": 1,
                "value": "Second live publication", "content_type": "text/plain"})
            visible(frame.locator("pre")).to_have_text("Second live publication", timeout=10000)
            expect(any("web_page.changed" in str(value) for value in notifications), "No page WS notification")
            count = len([url for url in requests if "/snapshot" in url])
            page.wait_for_timeout(2400)
            expect(count == len([url for url in requests if "/snapshot" in url]), "Browser polls snapshots while unchanged")
            stop_run_api(server, run["run_id"])
            wait_for_run_predicate(server, run["run_id"], lambda state: state["status"] in {"success", "cancelled"}, "Stop timed out")
            page.screenshot(path=artifact_path("web-page-published.png"))

            editor = context.new_page()
            wait_for_app_ready(editor, project_editor_url(server.base_url, graph_id, workspace_project_id=workspace_id))
            visible(editor.locator(f'.canvas-node[data-node-id="{node["id"]}"]')).to_contain_text(node["title"])
            editor.locator(f'.canvas-node[data-node-id="{node["id"]}"]').dblclick()
            modal = editor.locator(".web-page-modal")
            visible(modal).to_be_visible()
            expect(modal.evaluate("el => getComputedStyle(el).display === 'flex'"), "Release editor CSS did not load")
            expect(modal.locator(".web-page-scroll").evaluate("el => getComputedStyle(el).overflowY === 'auto'"),
                   "Editor lost its internal scroll area")
            visible(modal.locator("[data-page-url]")).to_have_value(server.base_url + snapshot["url"])
            visible(modal.locator("aside")).to_contain_text("@inputs.in.title")
            visible(modal.locator("aside")).to_contain_text("@@inputs.in.title")
            route = modal.locator('[data-page-field="path"]')
            route.fill("../forbidden")
            modal.locator("[data-page-save]").click()
            visible(modal.locator("[data-page-status]")).to_contain_text("Chemin relatif invalide")
            visible(route).to_be_enabled()
            expect(http_json(server.base_url, base + "/snapshot")["path"] == "index", "Invalid edit changed route")
            route.fill("index")
            modal.locator('[data-page-tab="html"]').click()
            source = modal.locator('[data-page-field="html"]')
            html = ('<main><h1>Published update</h1><pre title="@inputs.in">@inputs.in</pre><p id="detail"></p>'
                    '<p id="query">@query.view.</p><code>@@inputs.in</code><p id="js-value"></p>'
                    '<script>document.getElementById("js-value").textContent = '
                    'bloxPage.data.inputs.in + " / @inputs.in";</script></main>')
            source.fill(html)
            editor.wait_for_timeout(1500)
            visible(source).to_have_value(html)
            modal.locator('[data-page-tab="css"]').click()
            modal.locator('[data-page-tab="html"]').click()
            visible(source).to_have_value(html)
            modal.locator("[data-page-save]").click()
            visible(modal.locator("[data-page-status]")).to_contain_text("Page enregistree", timeout=10000)
            visible(frame.locator("h1")).to_have_text("Published update", timeout=10000)
            visible(frame.locator("pre")).to_have_text("Second live publication")
            visible(frame.locator("pre")).to_have_attribute("title", "Second live publication")
            visible(frame.locator("#query")).to_have_text("compact.")
            visible(frame.locator("code")).to_have_text("@inputs.in")
            visible(frame.locator("#js-value")).to_have_text("Second live publication / @inputs.in")
            page.screenshot(path=artifact_path("web-page-template-published.png"))
            modal.locator('[data-page-tab="page"]').click()
            editor.screenshot(path=artifact_path("web-page-modal-desktop.png"))
            editor.set_viewport_size({"width": 390, "height": 844})
            visible(modal.locator("[data-page-save]")).to_be_in_viewport()
            visible(modal.locator("[data-close-block-modal]")).to_be_in_viewport()
            expect(modal.evaluate("el => el.scrollWidth <= el.clientWidth + 1"), "Modal overflows horizontally")
            editor.screenshot(path=artifact_path("web-page-modal-mobile.png"))
            modal.locator("aside").scroll_into_view_if_needed()
            visible(modal.locator("aside")).to_be_in_viewport()
            visible(modal.locator("[data-page-save]")).to_be_in_viewport()
            editor.screenshot(path=artifact_path("web-page-modal-help-mobile.png"))
            modal.locator('[data-page-tab="html"]').focus()
            editor.keyboard.press("ArrowRight")
            visible(modal.locator('[data-page-tab="css"]')).to_have_attribute("aria-selected", "true")
            modal.locator('[data-page-tab="error"]').click()
            visible(modal.locator("[data-block-modal-no-error]")).to_have_text("Pas d'erreur.")
            modal.locator("[data-close-block-modal]").click()
            visible(modal).not_to_be_visible()
            # Neither script fetch nor self-navigation may load an administrative application URL.
            page.frames[1].evaluate("url => { location.href = url; }", server.base_url + "/api/health")
            page.wait_for_timeout(500)
            expect(not any("/api/health" in url for url in responses), "Sandbox navigated to the application API")
        finally:
            context.close()
            browser.close()
    print("[ok] F8.02_web_page_browser")


if __name__ == "__main__":
    main()
