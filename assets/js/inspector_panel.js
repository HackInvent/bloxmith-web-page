import { withProperties } from "./properties.js";

import { mountEditor } from "./common.js";

/** Mount this release’s editor using its surface root, host API and saved context. */
function mountOwned(root, api, context) {
  return mountEditor(root, api, context);
}

/** Keep the block behavior and add properties-only accessibility. */
export function mount(root, ...args) {
  return withProperties(mountOwned).call(this, root, ...args);
}
