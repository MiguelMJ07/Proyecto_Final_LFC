// Rail status light for the legacy minimization page (it has its own script and helpers).
(function () {
  async function ping() {
    const dot = document.getElementById("serverDot"), txt = document.getElementById("serverText");
    if (!dot) return;
    try { const r = await fetch("/health"); dot.className = "dot " + (r.ok ? "up" : "down"); txt.textContent = r.ok ? "Server connected" : "Server not reachable"; }
    catch (_) { dot.className = "dot down"; txt.textContent = "Server not reachable"; }
  }
  document.addEventListener("DOMContentLoaded", () => {
    ping(); setInterval(ping, 15000);
    // NFA handed over by the grammar page / hub (regular grammar -> NFA bridge)
    try {
      const nfa = localStorage.getItem("fl.nfa"), box = document.getElementById("nfaInput");
      if (nfa && box && location.hash === "#nfa") { box.value = JSON.stringify(JSON.parse(nfa), null, 2); localStorage.removeItem("fl.nfa"); box.scrollIntoView(); }
    } catch (_) {}
  });
})();
