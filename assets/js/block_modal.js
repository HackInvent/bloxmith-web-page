import { mountEditor } from "./common.js";

/** Mount this release’s editor using its surface root, host API and saved context. */
export function mount(root, api, context) {
  return mountEditor(root, api, context);
}
