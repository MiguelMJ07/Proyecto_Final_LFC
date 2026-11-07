// Visual effects of the server. Everything here is decoration: pages work without it, and nothing runs when the
// user asks for reduced motion (the final state is shown instead).
(function () {
  const calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---- scroll reveal ----
  function reveal() {
    if (calm || !("IntersectionObserver" in window)) return;
    document.documentElement.classList.add("fx");
    const items = $$(".card, .stage, .derive, .banner + *");
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: .08 });
    items.forEach((el, i) => { el.classList.add("reveal"); el.style.setProperty("--rd", (i % 4) * 70 + "ms"); io.observe(el); });
  }

  // ---- header depth: the light, the symbols and the cube follow the pointer ----
  function banners() {
    if (calm) return;
    $$("[data-banner]").forEach(b => {
      b.addEventListener("pointermove", e => {
        const r = b.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        b.style.setProperty("--mx", x.toFixed(3)); b.style.setProperty("--my", y.toFixed(3));
        b.style.setProperty("--px", (x - .5).toFixed(3)); b.style.setProperty("--py", (y - .5).toFixed(3));
      });
      b.addEventListener("pointerleave", () => { b.style.setProperty("--px", 0); b.style.setProperty("--py", 0); });
    });
  }

  // ---- symbols of the subject scattered on the ground and on the rail (same layout on every visit) ----
  function symbols() {
    const SYMS = ["ε", "δ", "Σ", "λ", "π", "∅", "∈", "→", "⇒", "∗", "$", "Γ", "∪", "ω", "φ", "⊢", "{ }", "ℓ"];
    const INK = "rgba(14,17,22,.085)", LIME = "rgba(150,196,20,.42)", RAIL = ["rgba(200,243,74,.28)", "rgba(255,255,255,.1)"];
    let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    function fill(host, cols, rows, pick, size) {
      let k = 0;
      for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
        if (rnd() < .22) continue;
        const s = document.createElement("span"); s.className = "sym"; s.textContent = SYMS[(k++ * 7 + r * 3 + c) % SYMS.length];
        s.style.left = ((c + .15 + rnd() * .7) / cols * 100).toFixed(1) + "%"; s.style.top = ((r + .1 + rnd() * .7) / rows * 100).toFixed(1) + "%";
        s.style.setProperty("--s", (size[0] + rnd() * (size[1] - size[0])).toFixed(2) + "rem");
        s.style.setProperty("--r", ((rnd() - .5) * 50).toFixed(0) + "deg"); s.style.setProperty("--d", (10 + rnd() * 50).toFixed(0));
        s.style.setProperty("--t", (7 + rnd() * 8).toFixed(1) + "s"); s.style.setProperty("--w", "-" + (rnd() * 9).toFixed(1) + "s");
        s.style.setProperty("--c", pick());
        host.append(s);
      }
    }
    const bg = document.createElement("div"); bg.className = "sym-bg"; bg.setAttribute("aria-hidden", "true");
    fill(bg, 10, 6, () => (rnd() < .22 ? LIME : INK), [2.2, 6]);
    document.body.prepend(bg);
    const rail = document.querySelector(".rail");
    if (rail) { const h = document.createElement("div"); h.className = "sym-rail"; h.setAttribute("aria-hidden", "true"); fill(h, 3, 4, () => RAIL[rnd() < .6 ? 0 : 1], [1.8, 3.6]); rail.append(h); }
    if (calm) return;
    addEventListener("pointermove", e => {
      const root = document.documentElement.style;
      root.setProperty("--gx", (e.clientX / innerWidth - .5).toFixed(3)); root.setProperty("--gy", (e.clientY / innerHeight - .5).toFixed(3));
    }, { passive: true });
  }

  // ---- the page title rises word by word ----
  function titles() {
    if (calm) return;
    $$(".banner h1").forEach(h => {
      let i = 0;
      (function wrap(n) {
        Array.from(n.childNodes).forEach(c => {
          if (c.nodeType === 3) {
            const f = document.createDocumentFragment();
            c.textContent.split(/(\s+)/).forEach(t => {
              if (!t) return;
              if (/^\s+$/.test(t)) { f.append(t); return; }
              const w = document.createElement("span"), x = document.createElement("span");
              w.className = "w"; x.textContent = t; x.style.setProperty("--i", i++); w.append(x); f.append(w);
            });
            c.replaceWith(f);
          } else if (c.nodeType === 1) wrap(c);
        });
      })(h);
    });
  }

  // ---- rotating live line in the banner ----
  function rotators() {
    $$("[data-rotate]").forEach(el => {
      const items = el.dataset.rotate.split("|"); if (items.length < 2 || calm) return;
      let i = 0;
      setInterval(() => {
        if (document.hidden) return;
        el.classList.add("out");
        setTimeout(() => { i = (i + 1) % items.length; el.textContent = items[i]; el.classList.remove("out"); }, 350);
      }, 3200);
    });
  }

  // ---- the derivation typed on the home banner ----
  function derivations() {
    $$("[data-derive]").forEach(box => {
      const steps = box.dataset.derive.split("|");
      box.replaceChildren();
      const parts = [];
      steps.forEach((s, i) => {
        if (i) { const a = document.createElement("span"); a.className = "ar"; a.textContent = "⇒"; box.append(a); parts.push(a); }
        const sp = document.createElement("span"); sp.className = "st"; sp.textContent = s; box.append(sp); parts.push(sp);
      });
      const nodes = parts.filter(p => p.classList.contains("st")), arrows = parts.filter(p => p.classList.contains("ar"));
      if (calm) { parts.forEach(p => p.classList.add("on")); return; }
      let k = 0;
      function tick() {
        if (k === 0) parts.forEach(p => p.classList.remove("on", "cur"));
        nodes.forEach(n => n.classList.remove("cur")); nodes[k].classList.add("on", "cur"); if (k) arrows[k - 1].classList.add("on");
        k++; if (k >= nodes.length) { k = 0; setTimeout(tick, 3200); } else setTimeout(tick, 900);
      }
      tick();
    });
  }

  // ---- numbers that count up ----
  function counters() {
    $$("[data-count]").forEach(el => {
      const end = +el.dataset.count; if (calm || !end) { el.textContent = end; return; }
      const t0 = performance.now(), dur = 1100;
      (function step(t) { const p = Math.min(1, (t - t0) / dur); el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(step); })(t0);
    });
  }

  // ---- confetti (used by practice mode when every answer is right) ----
  window.celebrate = function () {
    if (calm) return;
    let cv = document.getElementById("confetti");
    if (!cv) { cv = document.createElement("canvas"); cv.id = "confetti"; cv.setAttribute("aria-hidden", "true"); document.body.append(cv); }
    const ctx = cv.getContext("2d"); cv.width = innerWidth; cv.height = innerHeight;
    const colors = ["#0e1116", "#c8f34a", "#a9d62b", "#ffffff", "#4d5663"];
    const bits = Array.from({ length: 150 }, () => ({
      x: innerWidth / 2 + (Math.random() - .5) * 160, y: innerHeight * .62, vx: (Math.random() - .5) * 15, vy: -8 - Math.random() * 12,
      w: 6 + Math.random() * 7, h: 4 + Math.random() * 6, r: Math.random() * 6, vr: (Math.random() - .5) * .4, c: colors[(Math.random() * colors.length) | 0]
    }));
    let frames = 0;
    (function draw() {
      ctx.clearRect(0, 0, cv.width, cv.height);
      bits.forEach(b => { b.x += b.vx; b.y += b.vy; b.vy += .38; b.vx *= .99; b.r += b.vr;
        ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.r); ctx.fillStyle = b.c; ctx.globalAlpha = Math.max(0, 1 - frames / 130); ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h); ctx.restore(); });
      if (++frames < 130) requestAnimationFrame(draw); else cv.remove();
    })();
  };

  document.addEventListener("DOMContentLoaded", () => { symbols(); banners(); titles(); reveal(); rotators(); derivations(); counters(); });
})();
