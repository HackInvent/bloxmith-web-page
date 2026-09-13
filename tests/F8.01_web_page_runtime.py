"""Block-owned normalization, UI actions and service use in both execution modes."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from blocs import get_block_definition
from bloxsmith_app.block_api import BlockDefinitionError, BlockRuntimeContext, BlockRuntimeResult
from bloxsmith_app.block_executor import BlockRuntimeExecutor
from bloxsmith_app.graph import PortDefinition
from bloxsmith_app.block_ui import render_block_modal


class WebPageBlockTests(unittest.TestCase):
    """Keep transformation expectations within the owning autonomous block."""

    def test_runtime_modes_and_multiple_inputs(self):
        block = get_block_definition("web_page")
        for mode in ("centralized", "zeromq_active"):
            with self.subTest(mode=mode):
                ports = [PortDefinition(id=index, name=name, direction="input") for index, name in enumerate(("in", "count", "raw"), 1)]
                context = BlockRuntimeContext(kind="web_page", node_id="web-test", run_id="test",
                    runtime_mode=mode, config=block.default_config(), input_ports=ports,
                    inputs={"in": '{"title":"Hello"}', "count": "0", "raw": "not JSON"})
                result = BlockRuntimeExecutor().execute(context)
                self.assertEqual(result.status, "success")
                self.assertEqual(result.outputs, [])
                self.assertEqual(result.metadata["web_page_publication"]["data"],
                                 {"inputs": {"in": {"title": "Hello"}, "count": 0, "raw": "not JSON"}})

    def test_failed_activation_does_not_commit_publication(self):
        block = get_block_definition("web_page")

        def fail(context):
            """Stage data before a controlled block failure."""
            context.services["web_pages"].publish({"bad": True})
            return BlockRuntimeResult(status="failed", error="expected")

        with patch.object(block, "execute_runtime", side_effect=fail):
            result = BlockRuntimeExecutor().execute(BlockRuntimeContext(kind="web_page", config=block.default_config()))
        self.assertNotIn("web_page_publication", result.metadata)

    def test_sources_remain_editable_and_are_escaped(self):
        block = get_block_definition("web_page")
        node = {"id": "web-test", "kind": "web_page", "title": "<title>", "config": block.default_config(),
                "inputs": [], "outputs": []}
        page = deepcopy(node["config"]["page"])
        page["html"] = '</textarea><script>alert(1)</script>%%css%%'
        result = block.handle_ui_action(action="save_page", values={"page": page}, node=node)
        self.assertEqual(result["node_patch"]["config"]["page"]["html"], page["html"])
        node["config"]["page"] = page
        card = block.render_node_card(node=node)
        self.assertIn("data-web-page-node-card", card["html"])
        self.assertIn("&lt;title&gt;", card["html"])
        self.assertIn("Page / index", card["html"])
        self.assertTrue(card["context"]["node_classes"])
        modal = block.render_modal(node=node)["html"]
        self.assertIn("&lt;/textarea&gt;", modal)
        self.assertIn("%%css%%", modal)
        self.assertNotIn("<script>alert", modal)
        error_modal = render_block_modal("web_page", {"node": node, "runtime": {"result": {"error": "Expected runtime error"}}})["html"]
        self.assertIn("Expected runtime error", error_modal)
        self.assertEqual(error_modal.count("data-block-modal-error-panel"), 1)
        page["path"] = "../admin"
        with self.assertRaises(BlockDefinitionError):
            block.handle_ui_action(action="save_page", values={"page": page}, node=node)
        self.assertIn("data-page-field", block.render_modal(node=node)["html"])


if __name__ == "__main__":
    unittest.main()
