// Shared client helpers for every page of the server.
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
}

// POST/GET JSON. Always resolves to {ok, status, data}; a network failure becomes a readable error.
async function api(url, body, method = body === undefined ? "GET" : "POST") {
  try {
    const res = await fetch(url, { method, headers: body === undefined ? {} : { "Content-Type": "application/json" },
                                   body: body === undefined ? undefined : JSON.stringify(body) });
    let data = null;
    try { data = await res.json(); } catch (_) { data = { error: `Unexpected response (HTTP ${res.status}).` }; }
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { error: "The server is not reachable. Is `python src/app.py` still running?" } };
  }
}

// Server status light in the rail.
async function pingServer() {
  const dot = $("#serverDot"), txt = $("#serverText");
  if (!dot) return;
  const r = await api("/health");
  dot.className = "dot " + (r.ok ? "up" : "down");
  txt.textContent = r.ok ? "Server connected" : "Server not reachable";
}
document.addEventListener("DOMContentLoaded", () => { pingServer(); setInterval(pingServer, 15000); });

// Graphviz (viz-js from CDN). If it cannot load, the DOT source is shown instead.
const vizReady = window.Viz ? Viz.instance() : Promise.reject(new Error("viz.js not loaded"));
function drawDot(el, dot) {
  return vizReady.then(viz => { const svg = viz.renderSVGElement(dot); el.replaceChildren(svg); return svg; })
    .catch(() => { el.replaceChildren(h("pre", {}, dot), h("div", { class: "note" }, "Graphviz is not available offline; showing its source.")); return null; });
}

// Parse tree (JSON from the server) -> DOT / indented text.
function treeToDot(tree, withAttrs = false) {
  const lines = ["digraph T { node [shape=plaintext, fontname=Helvetica]; edge [arrowhead=none];"];
  const stack = [tree];
  while (stack.length) {
    const n = stack.pop();
    const isTerm = n.prod === null && !/[A-Z]/.test(n.symbol);
    let label = esc(n.symbol);
    if (withAttrs && Object.keys(n.attrs).length) label += "<br/><font point-size=\"10\">" + Object.entries(n.attrs).map(([k, v]) => `${esc(k)}=${esc(v)}`).join(", ") + "</font>";
    lines.push(`n${n.id} [label=<${isTerm ? "<b>" + label + "</b>" : label}>];`);
    if (!n.children.length && n.prod !== null) { lines.push(`e${n.id} [label=<<i>&epsilon;</i>>]; n${n.id} -> e${n.id};`); }
    for (const c of n.children) { lines.push(`n${n.id} -> n${c.id};`); stack.push(c); }
  }
  lines.push("}");
  return lines.join("\n");
}
function treeToText(tree) {
  const out = [], stack = [[tree, 0]];
  while (stack.length) {
    const [n, d] = stack.pop();
    const at = Object.entries(n.attrs || {}).map(([k, v]) => `${k}=${v}`).join(", ");
    out.push("  ".repeat(d) + n.symbol + (at ? `  [${at}]` : ""));
    for (let i = n.children.length - 1; i >= 0; i--) stack.push([n.children[i], d + 1]);
  }
  return out.join("\n");
}

// Tabs: <div class="tabs" role="tablist"><button data-tab="x">..</button></div> + <section data-panel="x">
function initTabs(root = document) {
  $$(".tabs", root).forEach(bar => {
    const btns = $$("button[data-tab]", bar);
    const show = id => {
      btns.forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === id)));
      $$("[data-panel]", bar.parentElement).forEach(p => p.hidden = p.dataset.panel !== id);
    };
    btns.forEach(b => b.addEventListener("click", () => show(b.dataset.tab)));
    show(btns[0].dataset.tab);
  });
}
