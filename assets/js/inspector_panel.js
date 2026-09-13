(function () {
  "use strict";
  const registry = window.CWBlockUiBlocks = window.CWBlockUiBlocks || {};
  registry.web_pageInspectorPanel = {mount(root, api, context) { window.CWWebPageEditor.mount(root, api, context); }};
})();
