/** Bind one editor root to its saved page context and the host action API. */
/**
 * Resolve one block text in the active language, from the catalog of the owning release.
 *
 * @param {HTMLElement} element - Element inside the mounted surface, carrying its release.
 * @param {string} key - Block catalog key.
 * @param {string} fallback - Authored English text.
 * @returns {string} Localized text.
 */
function text(element, key, fallback) {
  const release = element?.closest?.("[data-block-release]")?.dataset?.blockRelease || "";
  return window.CWI18n?.t?.(key, {}, fallback, release) ?? fallback;
}

export function mountEditor(root, api, context) {
  const status = root.querySelector("[data-page-status]");
  const save = root.querySelector("[data-page-save]");
  const fields = [...root.querySelectorAll("[data-page-field]")];
  let page = {...context.page}, busy = false;
  const scope = location.pathname.match(/^\/project\/([^/]+)\/blueprint\/([^/]+)\/instance\/([^/]+)/);
  /** Link only to the saved configuration, never an unsaved route draft. */
  function link() {
    const url = scope ? location.origin + "/pages/" + scope.slice(1).join("/") + "/" + encodeURIComponent(context.node_id) + "/" + page.path : "";
    root.querySelector("[data-page-url]").value = url;
    const anchor = root.querySelector("[data-page-open]");
    if (url) anchor.href = url;
    else { anchor.removeAttribute("href"); anchor.setAttribute("aria-disabled", "true"); }
  }
  link();
  root.addEventListener("input", () => { if (!busy) { save.disabled = Boolean(api.isReadOnly?.()); status.textContent = "Modifications non enregistrees."; } });
  save.addEventListener("click", async () => {
    if (busy || api.isReadOnly?.()) return;
    busy = true; save.disabled = true;
    try {
      const next = {...page};
      let title = context.title;
      fields.forEach(field => {
        const key = field.dataset.pageField;
        if (key === "title") title = field.value;
        else next[key] = key === "query_parameters" ? JSON.parse(field.value) : field.value;
      });
      fields.forEach(field => { field.disabled = true; });
      window.CWI18n?.setText?.(status, text(status, "block.web_page.saving", "Saving..."));
      if (!window.CWI18n?.setText) status.textContent = text(status, "block.web_page.saving", "Saving...");
      await api.applyAction("save_page", {page: next, title});
      page = next; link(); window.CWI18n?.set?.(status, "block.web_page.saved", {}, "Page saved. The link opens this version.");
    } catch (error) { window.CWI18n?.setText?.(status, error.message || text(status, "block.web_page.save_failed", "Saving failed."));
      if (!window.CWI18n?.setText) status.textContent = error.message || text(status, "block.web_page.save_failed", "Saving failed."); save.disabled = false; }
    finally { busy = false; fields.forEach(field => { field.disabled = Boolean(api.isReadOnly?.()); }); }
  });
  const tabs = [...root.querySelectorAll("[data-page-tab]")];
  /** Switch local panels without rebuilding controls or losing unsaved source text. */
  function select(tab) {
    tabs.forEach(item => { item.setAttribute("aria-selected", String(item === tab)); item.tabIndex = item === tab ? 0 : -1; });
    root.querySelectorAll("[data-page-panel]").forEach(panel => { panel.hidden = panel.dataset.pagePanel !== tab.dataset.pageTab; });
  }
  tabs.forEach((tab, index) => {
    tab.id = context.node_id + "-page-tab-" + index;
    const panel = root.querySelector('[data-page-panel="' + tab.dataset.pageTab + '"]');
    panel.id = context.node_id + "-page-panel-" + index;
    tab.setAttribute("aria-controls", panel.id); panel.setAttribute("aria-labelledby", tab.id);
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", event => {
      if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const target = tabs[event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      select(target); target.focus();
    });
  });
  if (api.isReadOnly?.()) fields.forEach(field => { field.disabled = true; });
}
