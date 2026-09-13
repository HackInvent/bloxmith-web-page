"""Own editable web sources and input projection; publication infrastructure stays generic."""

from dataclasses import asdict
from html import escape
import json
import re
from bloxsmith_app.block_api import (
    BlockDefinition, BlockDefinitionError, BlockRuntimeResult, WebPageDefinition, WebPageError,
    render_inspector_template, render_node_card_template,
)


def _reject_constant(value):
    """Leave non-finite JSON literals as plain input text rather than publishing NaN."""
    raise ValueError(value)


class WebPageBlock(BlockDefinition):
    """Publish current named input values, without executing any user JavaScript on the server."""

    kind = "web_page"

    def execute_runtime(self, context):
        """Normalize received inputs and stage a replacement page snapshot in either engine."""
        inputs = {}
        for key, value in context.input_values(include_ids=False).items():
            if isinstance(value, str):
                try:
                    value = json.loads(value, parse_constant=_reject_constant)
                except (ValueError, RecursionError):
                    pass
            inputs[str(key)] = value
        publisher = context.services.get("web_pages")
        if publisher is None:
            raise WebPageError("Service de publication web indisponible.")
        publisher.publish({"inputs": inputs})
        return BlockRuntimeResult(last_message=f"Page mise a jour : {len(inputs)} entree(s).",
            logs=[f"[web-page] {context.node_id}: nouvelle publication."],
            metadata={"input_count": len(inputs)})

    def ui_assets(self, surface="modal"):
        """Mount only block-owned editing behavior and styles, never page scripts in the editor."""
        if surface not in {"modal", "inspector_panel"}:
            return []
        return [{"kind": "css", "path": "assets/css/editor.css"},
                {"kind": "js", "path": "assets/js/common.js"},
                {"kind": "js", "path": f"assets/js/{'block_modal' if surface == 'modal' else 'inspector_panel'}.js"}]

    def handle_ui_action(self, *, action, values, node, payload=None):
        """Validate draft source and return a graph patch; mutations remain controller-owned."""
        if action != "save_page":
            return super().handle_ui_action(action=action, values=values, node=node, payload=payload)
        try:
            page = asdict(WebPageDefinition.from_config(values.get("page")))
        except WebPageError as error:
            raise BlockDefinitionError(str(error)) from error
        title = str(values.get("title") or node.get("title") or self.default_title()).strip()
        return {"node_patch": {"title": title, "config": {"page": page}}, "message": "Page enregistree.", "rerender_inspector": True}

    def _page(self, node):
        """Keep malformed saved sources editable instead of failing the entire modal."""
        raw = (node.get("config") or {}).get("page")
        return raw if isinstance(raw, dict) else dict(self.default_config()["page"])

    def _render(self, filename, node):
        """Escape source fields before inserting them into editor text controls."""
        page = self._page(node)
        values = {"title": node.get("title") or self.default_title(), **page}
        values["query_parameters"] = json.dumps(page.get("query_parameters", {}), ensure_ascii=False, indent=2)
        template = (self.directory / filename).read_text(encoding="utf-8")
        return re.sub(r"%%(title|path|html|css|javascript|query_parameters)%%",
                      lambda match: escape(str(values.get(match[1], "")), quote=True), template)

    def render_modal(self, *, node, payload=None):
        """Render an opaque source editor with stable tabs and a reachable sticky action bar."""
        html = self._render("block_modal.html", node).replace("%%ports%%", self._render_generic_modal_ports(node))
        html = html.replace("%%errors%%", self._render_generic_modal_error(payload or {}))
        return {"html": html, "context": {"node_id": node["id"], "page": self._page(node), "title": node.get("title", "Web Page")}}

    def render_inspector_panel(self, *, node, payload=None):
        """Offer endpoint editing and a link, leaving source editing in the dedicated modal."""
        html = render_inspector_template(template=self._render("inspector_panel.html", node),
            node={**node, "type": self.kind}, payload=payload or {}, show_duplicate=False)
        return {"html": html, "context": {"node_id": node["id"], "page": self._page(node), "title": node.get("title", "Web Page"), "full_panel": True}}

    def render_node_card(self, *, node, payload=None):
        """Display only the relative route, not the executable HTML or full input values."""
        return render_node_card_template(block=self, node=node, node_classes=["web-page-node"], replacements={
            "title": node.get("title") or self.default_title(), "preview": str(self._page(node).get("path", "index"))})
