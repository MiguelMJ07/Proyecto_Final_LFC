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

  document.addEventListener("DOMContentLoaded", () => { titles(); reveal(); rotators(); derivations(); counters(); });
})();
