# Web Page

<!-- block-metadata:start -->
[![Block version: 0.1.1](https://img.shields.io/badge/block-0.1.1-blue)](model.json)
[![BloxSmith compatibility: 1.0.9](https://img.shields.io/badge/BloxSmith-1.0.9-brightgreen)](compatibility.json)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Verified BloxSmith versions: **1.0.9** (bundled-block tests; see [test evidence](compatibility.json)).
<!-- block-metadata:end -->


## Overview

`web_page` publishes a web page whose HTML, CSS and JavaScript sources belong to the block. Inputs update its server-side data even when no browser is open. JavaScript runs only in the visitor's browser.

Block version: `0.1.1`. Declared and tested compatibility: BloxSmith `1.0.9`. The block uses generic executors in One Shot Simulation (`centralized`) and Active Runtime (`zeromq_active`), without its own HTTP server or socket.

## Static model

- One optional `in` input by default. Add and name inputs through the Ports context menu; each name becomes a key in `inputs`. Accepted types: `message/*`, `text/*` and `application/json`.
- No outputs: the result is the published page.
- `model.json.web_page.config_key = "page"` declares the generic capability to the framework.
- `config.page.path`: relative path, default `index`. Only letters, digits, `_`, `-` and `/`-separated segments; at most 160 characters, no leading `/` or `..`.
- `config.page.html`, `css`, `javascript`: embedded sources, at most 128 KiB each.
- `config.page.query_parameters`: object of default text values, for example `{"view":"complete"}`. At most 20 parameters; alphanumeric/underscore names starting with a letter (48 characters), values up to 1,024 characters.

## Runtime behavior

1. Saving the block in an instance makes its page accessible, even before Run.
2. Each execution collects current named-input values. A string containing valid JSON becomes an object, number, boolean or array; ordinary text stays text.
3. The block calls `context.services["web_pages"].publish({"inputs": values})`. A successful execution replaces the previous publication; a failed activation does not commit its publication.
4. The framework retains this publication in the instance's runtime result. Open visitors receive a WebSocket revision notification, then read the corresponding REST snapshot. A later visitor reads the latest data directly.
5. Saving source changes also updates open pages. Every revision reloads the isolated document and restarts its JavaScript, so visitor-local form state is not preserved.

Stop retains the latest data. Reset clears it without changing sources, ports or URL. Recovery after an application restart uses the normal saved session. Deleting the block removes the page. Changing its path invalidates the old URL for new visits.

Page URL:

```text
/pages/<workspace_project_id>/<graph_id>/<instance_id>/<node_id>/<path>
```

The modal and inspector display this URL. Duplication copies all sources but uses the new node ID, keeping pages independent. Nodes inside composites are resolved by their unique ID, without a composite path in the URL.

## Example

Value on input `in`: `{"title":"Project status","count":3}`.

HTML:

```html
<main>
  <h1>@inputs.in.title</h1>
  <p>@inputs.in.count items</p>
  <p id="view"></p>
</main>
```

JavaScript:

```js
document.getElementById("view").textContent = bloxPage.query.view;
console.log(bloxPage.data.inputs.in.count);
```

Opening the URL with `?view=compact` uses that value for this visitor only. Unknown or repeated parameters are rejected. Query parameters neither start the graph nor change its configuration.

References `@inputs.name`, `@inputs.name.field`, `@data.field` and `@query.name` insert escaped values into HTML. `@inputs` is shorthand for `@data.inputs`. Each key segment uses ASCII letters, digits or `_`, with no spaces around dots. Keys are case-sensitive. A missing key yields an empty string; numbers, booleans, objects, arrays and `null` display as JSON. Trailing punctuation remains: `@inputs.in.title.` displays the title followed by a period. References must be separated from adjacent text; an address such as `contact@inputs.in.title` is not interpreted.

To display a literal reference, double the `@`: `@@inputs.in.title` displays `@inputs.in.title` without reading the input. Inserted values are never reinterpreted as references. Only text and quoted HTML attribute values are substituted, for example `<span title="@inputs.in.title">@inputs.in.title</span>`. Unquoted attribute values remain literal.

Substitution applies only to HTML, not CSS/JavaScript sources, contents of `<script>`/`<style>`, `style`/`on...` attributes or HTML comments. JavaScript access remains `bloxPage.data.inputs.in.title` (or `bloxPage.data.inputs?.in?.title` before receiving data). This is not an expression engine: no loops, Python evaluation, server-side JS or raw HTML insertion from inputs. The former double-brace notation is not interpreted, and saved sources are not converted automatically.

## Versioned editor assets

The release declares its modal and inspector CSS/JavaScript in `model.json.ui_assets`.
Both entrypoints export `mount(root, api, context)` and share the module-local
`mountEditor` helper. They do not register bundled-kind browser globals. Editor CSS
is scoped to `[data-block-release="web_page@0.1.1"]` so other releases and the
application shell keep their own styles.

This repairs the versioned package editor opening without styles, tab handlers or
the saved page URL. It does not change published page sources or input processing.
For an explicitly linked development library, use the guarded **Recharger les blocs**
action after updating package files, then reload the blueprint browser tab. Managed
copies must be updated through the package installation workflow.

## Interface and security

The modal separates Page, HTML, CSS, JavaScript, Ports and Error. Error reuses the generic runtime diagnostic inside the modal's scrolling area. Changes stay local until Save. Tabs and runtime updates do not reset drafts. Closing without saving discards edits. The page link always opens the saved configuration. A rejected configuration shows its error in the modal and leaves fields editable without changing the saved page. The footer remains accessible with internal scrolling.

The browser renders content in an iframe with `sandbox="allow-scripts"`, without `allow-same-origin`, and with a restrictive CSP. Page code cannot access the parent DOM, cookies, network, management APIs, remote forms or nested frames. External scripts and stylesheets are not loaded. HTML/CSS/JS must be embedded in the configuration; `data:` images are allowed.

The page is accessible to anyone who can reach the application server. Its URL identifier is neither a secret nor authentication. Do not connect secrets to its inputs. Protect deployment with normal access controls before exposing it to the Internet. The sandbox isolates access, not the CPU cost of user-supplied JavaScript: open only trusted blueprints.

Limits: 256 KiB JSON publication, 512 KiB rendered HTML, 32 simultaneous WebSocket observers application-wide. Publication retains the latest state, not history or guaranteed delivery of every event. Server reconciliation is limited to two reads/second per observer; without events, checks occur about once per second.

## Verification

From the private `bloxmith-blocs` test workspace, run `python3 -B tests/run_tests.py web_page`. Captures go to ignored test results without hard-coded personal paths.

The following commands are for a prepared application test checkout, not a standalone clone of this block:

```sh
python3 -B blocs/web_page/tests/F8.01_web_page_runtime.py
python3 -B blocs/web_page/tests/F8.02_web_page_browser.py
python3 -B tests/F11.32_web_pages.py
python3 -B tests/F12.140_web_pages_http.py
```

The HTTP test executes a real graph in both engines. The browser test explicitly installs the package as `web_page@0.1.1` and uses real application assets and CSS, exercising desktop/mobile modals, loaded release styles, tab handlers, parent-context protection and WebSocket updates without periodic visitor-side HTTP polling. The runtime suite covers both `centralized` and `zeromq_active` modes. Tests cover HTML `@inputs`/`@data`/`@query` references, `@@` escaping, rendering limits, reference boundaries and unchanged JavaScript access.

## Compatibility policy

[compatibility.json](compatibility.json) records HackInvent's verified BloxSmith versions and test evidence. Only the versions listed above have been verified, using the block-owned suites in a **bundled-block test installation**. This is not a certification of managed-package installation, every browser/OS, or live provider availability. Other framework versions are unverified, not necessarily incompatible.

The block-version badge follows `model.json`, not a published Git tag. `unversioned` means that no block release version is declared; no number is inferred from the framework version. The framework still uses `model.json` for its runtime/install contract; the tester-owned JSON does not replace it. Official integration tests run in the private `bloxmith-blocs` workspace. Test helpers and the proprietary framework are not bundled in this public block repository.
