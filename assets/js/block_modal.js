(function () {
  "use strict";
  const registry = window.CWBlockUiBlocks = window.CWBlockUiBlocks || {};
  registry.web_page = {mount(root, api, context) { window.CWWebPageEditor.mount(root, api, context); }};
})();
