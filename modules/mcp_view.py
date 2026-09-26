"""The diagram view shown inside chat apps that support MCP Apps.

A single self-contained HTML document, served as the ``ui://`` resource that
``render_graph`` and ``generate_diagram`` point to. The host renders it in a
sandboxed iframe and passes it the tool result, which already carries a
preview PNG, so the diagram appears immediately. Buttons call the server's
``open_diagram_file`` and ``diagram_file`` tools through the host to open
files on the user's machine, load the SVG at full resolution and copy the
graph JSON.

It talks to the host with raw JSON-RPC over ``postMessage`` as defined by the
MCP Apps specification (protocol version 2026-01-26), so it needs no
JavaScript library and no network access: the host's default Content Security
Policy allows inline scripts and ``data:`` images, which is all it uses.
Every value from the tool result is written with ``textContent``, never as
HTML.

Kept as a Python string rather than a separate file so it always ships inside
the package.
"""

VIEW_URI = "ui://terravision/diagram.html"

VIEW_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TerraVision diagram</title>
<style>
  :root {
    --bg: var(--color-background-primary, #ffffff);
    --bg2: var(--color-background-secondary, #f4f5f7);
    --fg: var(--color-text-primary, #1f2328);
    --fg2: var(--color-text-secondary, #59636e);
    --border: var(--color-border-primary, #d0d7de);
    --danger: var(--color-text-danger, #cf222e);
    --warning: var(--color-text-warning, #9a6700);
    --radius: var(--border-radius-md, 8px);
    --font: var(--font-sans, system-ui, -apple-system, "Segoe UI", sans-serif);
    --mono: var(--font-mono, ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: var(--color-background-primary, #0d1117);
      --bg2: var(--color-background-secondary, #161b22);
      --fg: var(--color-text-primary, #e6edf3);
      --fg2: var(--color-text-secondary, #9198a1);
      --border: var(--color-border-primary, #30363d);
      --danger: var(--color-text-danger, #ff7b72);
    }
  }
  :root[data-theme="dark"] {
    --bg: var(--color-background-primary, #0d1117);
    --bg2: var(--color-background-secondary, #161b22);
    --fg: var(--color-text-primary, #e6edf3);
    --fg2: var(--color-text-secondary, #9198a1);
    --border: var(--color-border-primary, #30363d);
    --danger: var(--color-text-danger, #ff7b72);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.4 var(--font); }
  body { padding: 12px; }
  header { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
  h1 { font-size: 16px; font-weight: 600; margin: 0; }
  .sub { color: var(--fg2); font-size: 12px; }
  .toolbar { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
  button {
    font: inherit; font-size: 13px; color: var(--fg); background: var(--bg2);
    border: 1px solid var(--border); border-radius: var(--radius); padding: 5px 10px; cursor: pointer;
  }
  button:hover { border-color: var(--fg2); }
  button:disabled { opacity: 0.5; cursor: default; }
  .spacer { flex: 1; }
  #stage {
    position: relative; height: 560px; overflow: hidden; background: #ffffff;
    border: 1px solid var(--border); border-radius: var(--radius); cursor: grab; touch-action: none;
  }
  #stage.dragging { cursor: grabbing; }
  #stage img { position: absolute; left: 0; top: 0; transform-origin: 0 0; user-select: none; -webkit-user-drag: none; }
  .fullscreen #stage { height: calc(100vh - 150px); }
  #message { padding: 24px; color: var(--fg2); }
  #message.error { color: var(--danger); white-space: pre-wrap; }
  #status { min-height: 18px; margin-top: 6px; color: var(--fg2); font-size: 12px; }
  #status.error { color: var(--danger); }
  pre {
    margin: 8px 0 0; padding: 10px; max-height: 320px; overflow: auto; background: var(--bg2);
    border: 1px solid var(--border); border-radius: var(--radius); font: 12px/1.45 var(--mono);
  }
  ul { margin: 6px 0 0; padding-left: 18px; color: var(--fg2); font-size: 12px; }
  #warnings { color: var(--warning); }
  #warnings li { margin-bottom: 2px; }
  li code { font-family: var(--mono); color: var(--fg); word-break: break-all; }
  li button.path {
    padding: 0; border: 0; background: none; text-align: left; cursor: pointer;
    font-family: var(--mono); font-size: 12px; color: var(--fg); text-decoration: underline;
    word-break: break-all;
  }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<header>
  <h1 id="title">TerraVision diagram</h1>
  <span class="sub" id="subtitle"></span>
</header>
<div class="toolbar" id="actions" hidden>
  <button id="open">Open image</button>
  <button id="edit">Edit in draw.io</button>
  <button id="reveal">Show in folder</button>
  <button id="copy">Copy JSON</button>
  <button id="json">Show JSON</button>
  <span class="spacer"></span>
  <button id="zoomout" title="Zoom out">&minus;</button>
  <button id="fit" title="Fit to view">Fit</button>
  <button id="zoomin" title="Zoom in">+</button>
  <button id="fullscreen" hidden>Full screen</button>
</div>
<div id="stage"><div id="message">Drawing the diagram&hellip;</div><img id="diagram" alt="Cloud architecture diagram" hidden></div>
<div id="status"></div>
<pre id="graph" hidden></pre>
<ul id="warnings" hidden></ul>
<ul id="files" hidden></ul>
<script>
(function () {
  "use strict";
  var PROTOCOL_VERSION = "2026-01-26";
  var APP_VERSION = "__VERSION__";
  var nextId = 1;
  var pending = {};
  var hostCaps = {};
  var hostContext = {};
  var result = null;
  var svgLoaded = false;
  var graphText = null;
  var view = { scale: 1, x: 0, y: 0, fitted: true };
  var $ = function (id) { return document.getElementById(id); };

  // ---- JSON-RPC over postMessage --------------------------------------------
  function post(message) { window.parent.postMessage(message, "*"); }
  function request(method, params) {
    var id = nextId++;
    post({ jsonrpc: "2.0", id: id, method: method, params: params || {} });
    return new Promise(function (resolve, reject) { pending[id] = { resolve: resolve, reject: reject }; });
  }
  function notify(method, params) { post({ jsonrpc: "2.0", method: method, params: params || {} }); }
  function respond(id, value) { post({ jsonrpc: "2.0", id: id, result: value || {} }); }

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) { return; }
    var msg = event.data;
    if (!msg || msg.jsonrpc !== "2.0") { return; }
    if (msg.method === undefined && msg.id !== undefined && pending[msg.id]) {
      var p = pending[msg.id];
      delete pending[msg.id];
      if (msg.error) { p.reject(new Error(msg.error.message || "Request failed")); }
      else { p.resolve(msg.result); }
      return;
    }
    switch (msg.method) {
      case "ui/notifications/tool-input": showInput(msg.params && msg.params.arguments); break;
      case "ui/notifications/tool-result": showResult(msg.params); break;
      case "ui/notifications/tool-cancelled": showMessage("Rendering was cancelled.", true); break;
      case "ui/notifications/host-context-changed": applyContext(msg.params || {}); break;
      case "ui/resource-teardown": respond(msg.id); break;
      case "ping": respond(msg.id); break;
      default:
        if (msg.id !== undefined && msg.method) {
          post({ jsonrpc: "2.0", id: msg.id, error: { code: -32601, message: "Method not found" } });
        }
    }
  });

  function callTool(name, args) {
    return request("tools/call", { name: name, arguments: args }).then(function (res) {
      if (!res) { throw new Error("No result"); }
      if (res.isError) { throw new Error(textOf(res) || "The tool reported an error"); }
      var data = res.structuredContent;
      // The MCP SDK wraps a tool's dictionary result as {"result": {...}}.
      if (data && data.result && typeof data.result === "object" && Object.keys(data).length === 1) {
        data = data.result;
      }
      if (data) { return data; }
      try { return JSON.parse(textOf(res)); } catch (e) { return {}; }
    });
  }
  function textOf(res) {
    var blocks = (res && res.content) || [];
    for (var i = 0; i < blocks.length; i++) { if (blocks[i].type === "text") { return blocks[i].text; } }
    return "";
  }

  // ---- Host context: theme, display mode ------------------------------------
  function applyContext(ctx) {
    for (var k in ctx) { hostContext[k] = ctx[k]; }
    if (hostContext.theme) { document.documentElement.setAttribute("data-theme", hostContext.theme); }
    var vars = hostContext.styles && hostContext.styles.variables;
    if (vars) {
      for (var name in vars) { if (vars[name]) { document.documentElement.style.setProperty(name, vars[name]); } }
    }
    document.body.classList.toggle("fullscreen", hostContext.displayMode === "fullscreen");
    $("fullscreen").textContent = hostContext.displayMode === "fullscreen" ? "Exit full screen" : "Full screen";
    var modes = hostContext.availableDisplayModes || [];
    $("fullscreen").hidden = modes.indexOf("fullscreen") < 0;
    if (view.fitted) { fit(); }
  }

  // ---- Rendering the result --------------------------------------------------
  function showInput(args) {
    if (args && args.title) { $("title").textContent = args.title; }
  }
  function showMessage(text, isError) {
    var m = $("message");
    m.textContent = text;
    m.className = isError ? "error" : "";
    m.hidden = false;
    $("diagram").hidden = true;
  }
  function setStatus(text, isError) {
    var s = $("status");
    s.textContent = text || "";
    s.className = isError ? "error" : "";
  }

  function showResult(res) {
    if (!res) { return; }
    if (res.isError) { showMessage(textOf(res) || "The diagram could not be drawn.", true); return; }
    var data = res.structuredContent;
    if (!data) { try { data = JSON.parse(textOf(res)); } catch (e) { data = {}; } }
    result = data || {};
    $("title").textContent = result.title || "Cloud architecture diagram";
    var parts = [];
    if (result.provider) { parts.push(String(result.provider).toUpperCase()); }
    if (result.node_count !== undefined) { parts.push(result.node_count + " nodes"); }
    $("subtitle").textContent = parts.join(" · ");

    var image = null;
    (res.content || []).forEach(function (b) { if (!image && b.type === "image") { image = b; } });
    if (image) {
      showImage("data:" + (image.mimeType || "image/png") + ";base64," + image.data);
      // Show the preview at once, then swap in the SVG so zooming stays sharp.
      loadSvg(false);
    } else if (canCallTools()) {
      loadSvg(true);
    } else {
      showMessage("The diagram was saved to the files listed below.", false);
    }
    listFiles();
    listWarnings();
    $("actions").hidden = false;
    var tools = canCallTools();
    ["open", "edit", "reveal", "copy", "json"].forEach(function (id) { $(id).hidden = !tools; });
    $("edit").hidden = !tools || !files().drawio;
    $("copy").hidden = $("json").hidden = !tools || !files().graph;
  }

  function files() { return (result && result.files) || {}; }
  function canCallTools() { return !!hostCaps.serverTools; }

  function listWarnings() {
    var list = $("warnings");
    list.textContent = "";
    ((result && result.warnings) || []).forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    list.hidden = list.children.length === 0;
  }

  function listFiles() {
    var list = $("files");
    list.textContent = "";
    var labels = { png: "Image", svg: "SVG", drawio: "draw.io", graph: "Graph JSON", pdf: "PDF", dot: "DOT" };
    var f = files();
    Object.keys(f).forEach(function (kind) {
      var li = document.createElement("li");
      li.appendChild(document.createTextNode((labels[kind] || kind) + ": "));
      var path = f[kind];
      if (canCallTools()) {
        // Clicking a path opens that file in its default app.
        var link = document.createElement("button");
        link.className = "path";
        link.title = "Open this file";
        link.textContent = path;
        link.onclick = function () {
          openFile(path, false, "Opened " + path.split(/[\\/]/).pop() + ".");
        };
        li.appendChild(link);
      } else {
        var code = document.createElement("code");
        code.textContent = path;
        li.appendChild(code);
      }
      list.appendChild(li);
    });
    list.hidden = list.children.length === 0;
  }

  // ---- Zoom and pan ------------------------------------------------------------
  function showImage(src) {
    var img = $("diagram");
    img.onload = function () { $("message").hidden = true; img.hidden = false; if (view.fitted) { fit(); } else { apply(); } };
    img.src = src;
  }
  function apply() {
    $("diagram").style.transform = "translate(" + view.x + "px," + view.y + "px) scale(" + view.scale + ")";
  }
  function fit() {
    var img = $("diagram"), stage = $("stage");
    if (!img.naturalWidth) { return; }
    var s = Math.min(stage.clientWidth / img.naturalWidth, stage.clientHeight / img.naturalHeight);
    view.scale = s;
    view.x = (stage.clientWidth - img.naturalWidth * s) / 2;
    view.y = (stage.clientHeight - img.naturalHeight * s) / 2;
    view.fitted = true;
    apply();
  }
  function zoomAt(factor, cx, cy) {
    var stage = $("stage");
    if (cx === undefined) { cx = stage.clientWidth / 2; cy = stage.clientHeight / 2; }
    var next = Math.max(0.05, Math.min(view.scale * factor, 40));
    view.x = cx - (cx - view.x) * (next / view.scale);
    view.y = cy - (cy - view.y) * (next / view.scale);
    view.scale = next;
    view.fitted = false;
    apply();
    if (factor > 1) { loadSvg(false); }
  }
  $("zoomin").onclick = function () { zoomAt(1.4); };
  $("zoomout").onclick = function () { zoomAt(1 / 1.4); };
  $("fit").onclick = fit;
  $("stage").addEventListener("wheel", function (e) {
    e.preventDefault();
    var r = e.currentTarget.getBoundingClientRect();
    zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  $("stage").addEventListener("dblclick", function (e) {
    if (view.fitted) { var r = e.currentTarget.getBoundingClientRect(); zoomAt(2.5, e.clientX - r.left, e.clientY - r.top); }
    else { fit(); }
  });
  (function () {
    var drag = null, stage = $("stage");
    stage.addEventListener("pointerdown", function (e) {
      drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
      stage.setPointerCapture(e.pointerId);
      stage.classList.add("dragging");
    });
    stage.addEventListener("pointermove", function (e) {
      if (!drag) { return; }
      view.x = drag.vx + e.clientX - drag.x;
      view.y = drag.vy + e.clientY - drag.y;
      view.fitted = false;
      apply();
    });
    function end() { drag = null; stage.classList.remove("dragging"); }
    stage.addEventListener("pointerup", end);
    stage.addEventListener("pointercancel", end);
  })();
  window.addEventListener("resize", function () { if (view.fitted) { fit(); } });

  // Swap the preview for the SVG, which stays sharp at any zoom, keeping the
  // on-screen size so the view does not jump. Also retried on zoom in case the
  // first load failed.
  function loadSvg(initial) {
    if (svgLoaded || !canCallTools() || !files().svg) { return; }
    svgLoaded = true;
    callTool("diagram_file", { path: files().svg }).then(function (file) {
      if (!file || !file.text) { return; }
      var img = $("diagram");
      var shownWidth = img.naturalWidth * view.scale;
      var src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(file.text)));
      img.onload = function () {
        $("message").hidden = true;
        img.hidden = false;
        if (initial || view.fitted || !shownWidth) { fit(); }
        else { view.scale = shownWidth / img.naturalWidth; apply(); }
      };
      img.src = src;
    }).catch(function () { svgLoaded = false; });
  }

  // ---- Buttons -----------------------------------------------------------------
  function openFile(path, reveal, done) {
    callTool("open_diagram_file", { path: path, reveal: !!reveal })
      .then(function () { setStatus(done); })
      .catch(function (e) { setStatus(e.message, true); });
  }
  $("open").onclick = function () { openFile(files().png, false, "Opened the image in your default viewer."); };
  $("edit").onclick = function () { openFile(files().drawio, false, "Opened the draw.io file. Save it there after editing."); };
  $("reveal").onclick = function () { openFile(files().png, true, "Opened the folder with the diagram files."); };

  function loadGraph() {
    if (graphText !== null) { return Promise.resolve(graphText); }
    return callTool("diagram_file", { path: files().graph }).then(function (file) {
      graphText = (file && file.text) || "";
      return graphText;
    });
  }
  $("json").onclick = function () {
    var pre = $("graph");
    if (!pre.hidden) { pre.hidden = true; $("json").textContent = "Show JSON"; return; }
    loadGraph().then(function (text) {
      pre.textContent = text;
      pre.hidden = false;
      $("json").textContent = "Hide JSON";
    }).catch(function (e) { setStatus(e.message, true); });
  };
  $("copy").onclick = function () {
    loadGraph().then(function (text) { return copyText(text); })
      .then(function () { setStatus("Copied the graph JSON."); })
      .catch(function (e) { setStatus("Could not copy: " + e.message, true); });
  };
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).catch(function () { return legacyCopy(text); });
    }
    return legacyCopy(text);
  }
  function legacyCopy(text) {
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(area);
      if (ok) { resolve(); } else { reject(new Error("the clipboard is not available here")); }
    });
  }
  $("fullscreen").onclick = function () {
    var mode = hostContext.displayMode === "fullscreen" ? "inline" : "fullscreen";
    request("ui/request-display-mode", { mode: mode }).then(function (r) {
      applyContext({ displayMode: (r && r.mode) || mode });
    }).catch(function () {});
  };

  // ---- Size reporting and start-up ------------------------------------------------
  var lastSize = "";
  function reportSize() {
    var w = Math.ceil(document.documentElement.scrollWidth);
    var h = Math.ceil(document.documentElement.scrollHeight);
    var key = w + "x" + h;
    if (key !== lastSize) { lastSize = key; notify("ui/notifications/size-changed", { width: w, height: h }); }
  }
  if (window.ResizeObserver) { new ResizeObserver(reportSize).observe(document.body); }

  request("ui/initialize", {
    appInfo: { name: "TerraVision diagram", version: APP_VERSION },
    appCapabilities: { availableDisplayModes: ["inline", "fullscreen"] },
    protocolVersion: PROTOCOL_VERSION
  }).then(function (init) {
    hostCaps = (init && init.hostCapabilities) || {};
    applyContext((init && init.hostContext) || {});
    notify("ui/notifications/initialized", {});
    reportSize();
  }).catch(function (e) {
    showMessage("This app could not start the diagram view: " + e.message, true);
  });
})();
</script>
</body>
</html>
"""
