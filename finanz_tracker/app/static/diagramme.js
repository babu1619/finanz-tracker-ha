// Eigene, kleine Diagramm-Bibliothek (SVG, ohne Internet). Zeichnet Säulen, gestapelte Säulen, waagerechte Balken,
// Linien, Flächen, Ring/Torte, Tabelle, Kennzahl und Wärmekarte aus {labels, reihen:[{name, werte, vorjahr}], einheit}.
(function () {
  "use strict";
  const FARBEN = ["#0F6B5C", "#C98A12", "#3B6FB6", "#B5475A", "#6A8F3A", "#7A5BA8", "#2F9C9C", "#A0662E", "#5E6B66", "#D16BA5", "#8A9A2B", "#44546A"];
  const NS = "http://www.w3.org/2000/svg";

  function zahl(wert, einheit) {
    if (einheit === "€") {
      const e = Math.round(wert / 100);
      return e.toLocaleString("de-DE") + " €";
    }
    return Math.round(wert).toLocaleString("de-DE");
  }
  function kurz(wert, einheit) {
    const e = einheit === "€" ? wert / 100 : wert;
    const a = Math.abs(e);
    let t;
    if (a >= 1e6) t = (e / 1e6).toLocaleString("de-DE", { maximumFractionDigits: 1 }) + " Mio";
    else if (a >= 1e4) t = Math.round(e / 1000).toLocaleString("de-DE") + " T";
    else t = Math.round(e).toLocaleString("de-DE");
    return einheit === "€" ? t + " €" : t;
  }
  function el(name, attrs, eltern) {
    const n = document.createElementNS(NS, name);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (eltern) eltern.appendChild(n);
    return n;
  }
  function html(tag, klasse, text) {
    const n = document.createElement(tag);
    if (klasse) n.className = klasse;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function farben(reihen) {
    // Vorjahresreihe bekommt die Farbe ihrer Grundreihe (heller/gestrichelt)
    const basis = {};
    let i = 0;
    return reihen.map((r) => {
      const name = r.name.replace(" (Vorjahr)", "");
      if (!(name in basis)) basis[name] = FARBEN[i++ % FARBEN.length];
      return basis[name];
    });
  }
  function schoeneSkala(min, max, n) {
    if (min === max) { max = max === 0 ? 1 : max * 1.2; min = Math.min(0, min); }
    const roh = (max - min) / n;
    const pot = Math.pow(10, Math.floor(Math.log10(Math.abs(roh))));
    const schritt = [1, 2, 2.5, 5, 10].map((f) => f * pot).find((s) => s >= roh) || roh;
    const lo = Math.floor(min / schritt) * schritt;
    const hi = Math.ceil(max / schritt) * schritt;
    const ticks = [];
    for (let v = lo; v <= hi + schritt / 2; v += schritt) ticks.push(v);
    return { lo, hi, ticks };
  }

  function legende(box, reihen, cols, optionen) {
    if (reihen.length < 2 && !optionen.immerLegende) return;
    const l = html("div", "dg-legende");
    reihen.forEach((r, i) => {
      const s = html("span", r.vorjahr ? "vj" : "");
      const f = html("i");
      f.style.background = cols[i];
      s.append(f, document.createTextNode(r.name + (optionen.prozente ? ` ${optionen.prozente[i]}` : "")));
      if (optionen.link && r.id && r.id !== "sonstige") {
        s.classList.add("klickbar");
        s.addEventListener("click", () => optionen.link(r));
      }
      l.append(s);
    });
    box.append(l);
  }

  function tooltip(box) {
    let t = box.querySelector(".dg-tooltip");
    if (!t) { t = html("div", "dg-tooltip"); t.hidden = true; box.append(t); }
    return t;
  }
  function zeigeTooltip(box, x, y, zeilen) {
    const t = tooltip(box);
    t.innerHTML = "";
    zeilen.forEach(([text, farbe, fett]) => {
      const z = html("div", fett ? "fett" : "");
      if (farbe) { const f = html("i"); f.style.background = farbe; z.append(f); }
      z.append(document.createTextNode(text));
      t.append(z);
    });
    t.hidden = false;
    const br = box.getBoundingClientRect();
    const tw = t.offsetWidth;
    t.style.left = Math.max(4, Math.min(x - br.left + 12, br.width - tw - 4)) + "px";
    t.style.top = Math.max(4, y - br.top - t.offsetHeight - 10) + "px";
  }

  // ------------------------------------------------------------------ Achsen-Diagramme
  function kartesisch(box, d, typ, optionen) {
    const reihen = d.reihen, labels = d.labels, n = labels.length;
    const cols = farben(reihen);
    const W = Math.max(box.clientWidth || 600, 280), H = optionen.hoehe || 260;
    const links = 58, rechts = 10, oben = 12, unten = n > 8 ? 46 : 30;
    const pw = W - links - rechts, ph = H - oben - unten;
    const gestapelt = typ === "gestapelt";
    let min = 0, max = 0;
    for (let i = 0; i < n; i++) {
      if (gestapelt) {
        let p = 0, m = 0;
        reihen.forEach((r) => { const v = r.werte[i]; if (v >= 0) p += v; else m += v; });
        max = Math.max(max, p); min = Math.min(min, m);
      } else {
        reihen.forEach((r) => { max = Math.max(max, r.werte[i]); min = Math.min(min, r.werte[i]); });
      }
    }
    const sk = schoeneSkala(min, max, 4);
    const y = (v) => oben + ph - ((v - sk.lo) / (sk.hi - sk.lo)) * ph;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", height: H, role: "img" });
    sk.ticks.forEach((t) => {
      el("line", { x1: links, x2: W - rechts, y1: y(t), y2: y(t), class: t === 0 ? "dg-null" : "dg-gitter" }, svg);
      el("text", { x: links - 6, y: y(t) + 4, "text-anchor": "end", class: "dg-achse" }, svg).textContent = kurz(t, d.einheit);
    });
    const spalte = pw / Math.max(n, 1);
    const xm = (i) => links + spalte * i + spalte / 2;
    const jede = Math.ceil(n / Math.max(1, Math.floor(pw / 46)));
    labels.forEach((l, i) => {
      if ((n - 1 - i) % jede !== 0) return; // vom letzten Wert aus zählen, damit nichts überlappt
      const t = el("text", { x: xm(i), y: H - unten + 16, "text-anchor": "middle", class: "dg-achse" }, svg);
      t.textContent = l;
    });
    if (typ === "balken" || gestapelt) {
      const gruppen = gestapelt ? 1 : reihen.length;
      const bw = Math.max(2, Math.min(38, (spalte * 0.74) / gruppen));
      for (let i = 0; i < n; i++) {
        let pos = 0, neg = 0;
        reihen.forEach((r, k) => {
          const v = r.werte[i];
          if (!v) return;
          let x, y0, y1;
          if (gestapelt) {
            x = xm(i) - bw / 2;
            if (v >= 0) { y0 = y(pos + v); y1 = y(pos); pos += v; } else { y0 = y(neg); y1 = y(neg + v); neg += v; }
          } else {
            x = xm(i) - (bw * gruppen) / 2 + k * bw;
            y0 = y(Math.max(v, 0)); y1 = y(Math.min(v, 0));
          }
          el("rect", { x: x + 0.5, y: y0, width: Math.max(1, bw - 1), height: Math.max(0.5, y1 - y0), fill: cols[k],
                       "fill-opacity": r.vorjahr ? 0.45 : 1, rx: 2 }, svg);
        });
      }
    } else {
      reihen.forEach((r, k) => {
        const pkt = r.werte.map((v, i) => [xm(i), y(v)]);
        const pfad = pkt.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
        if (typ === "flaeche" && pkt.length) {
          el("path", { d: `${pfad} L${pkt[pkt.length - 1][0]} ${y(Math.max(sk.lo, 0))} L${pkt[0][0]} ${y(Math.max(sk.lo, 0))} Z`,
                       fill: cols[k], "fill-opacity": r.vorjahr ? 0.08 : 0.16 }, svg);
        }
        el("path", { d: pfad, fill: "none", stroke: cols[k], "stroke-width": r.vorjahr ? 1.6 : 2.2,
                     "stroke-dasharray": r.vorjahr ? "5 4" : "", "stroke-linejoin": "round" }, svg);
        if (n <= 24) pkt.forEach((p) => el("circle", { cx: p[0], cy: p[1], r: 2.6, fill: cols[k] }, svg));
      });
    }
    // Trefferflächen je Spalte für den Tooltip
    const markierung = el("rect", { x: 0, y: oben, width: spalte, height: ph, class: "dg-markierung", visibility: "hidden" }, svg);
    for (let i = 0; i < n; i++) {
      const h = el("rect", { x: links + spalte * i, y: oben, width: spalte, height: ph, fill: "transparent" }, svg);
      const zeige = (e) => {
        markierung.setAttribute("x", links + spalte * i);
        markierung.setAttribute("visibility", "visible");
        const zeilen = [[labels[i], null, true]];
        let summe = 0;
        reihen.forEach((r, k) => { if (r.werte[i]) { zeilen.push([`${r.name}: ${zahl(r.werte[i], d.einheit)}`, cols[k]]); if (!r.vorjahr) summe += r.werte[i]; } });
        if (reihen.filter((r) => !r.vorjahr).length > 1) zeilen.push([`Summe: ${zahl(summe, d.einheit)}`, null, true]);
        zeigeTooltip(box, e.clientX, e.clientY, zeilen);
      };
      h.addEventListener("pointermove", zeige);
      h.addEventListener("pointerdown", zeige);
      if (optionen.linkZeit) h.addEventListener("click", () => optionen.linkZeit(i));
      h.style.cursor = optionen.linkZeit ? "pointer" : "default";
    }
    svg.addEventListener("pointerleave", () => { markierung.setAttribute("visibility", "hidden"); tooltip(box).hidden = true; });
    box.append(svg);
    legende(box, reihen, cols, optionen);
  }

  function summen(d) {
    return d.reihen.map((r) => r.werte.reduce((a, b) => a + b, 0));
  }

  function horizontal(box, d, optionen) {
    const s = summen(d);
    const eintraege = d.reihen.map((r, i) => ({ r, v: s[i] })).filter((e) => e.v);
    const max = Math.max(1, ...eintraege.map((e) => Math.abs(e.v)));
    const cols = farben(d.reihen);
    const liste = html("div", "dg-hbalken");
    eintraege.forEach((e) => {
      const z = html("div", "zeile" + (optionen.link && e.r.id !== "sonstige" ? " klickbar" : ""));
      const name = html("span", "name", e.r.name);
      name.title = e.r.name;
      const spur = html("span", "spur");
      const b = html("span", "balken");
      b.style.width = (Math.abs(e.v) / max) * 100 + "%";
      b.style.background = cols[d.reihen.indexOf(e.r)];
      if (e.r.vorjahr) b.style.opacity = 0.45;
      spur.append(b);
      z.append(name, spur, html("span", "wert", zahl(e.v, d.einheit)));
      if (optionen.link && e.r.id !== "sonstige") z.addEventListener("click", () => optionen.link(e.r));
      liste.append(z);
    });
    box.append(liste);
  }

  function ring(box, d, typ, optionen) {
    const s = summen(d).map((v) => Math.max(0, v));
    const gesamt = s.reduce((a, b) => a + b, 0);
    const cols = farben(d.reihen);
    const W = 220, R = 100, r0 = typ === "donut" ? 62 : 0;
    const wrap = html("div", "dg-ring");
    const svg = el("svg", { viewBox: `0 0 ${W} ${W}`, width: W, height: W, role: "img" });
    let winkel = -Math.PI / 2;
    const c = W / 2;
    s.forEach((v, i) => {
      if (!v) return;
      const a = (v / gesamt) * Math.PI * 2;
      const gross = a > Math.PI ? 1 : 0;
      const p = (rad, w) => [c + rad * Math.cos(w), c + rad * Math.sin(w)];
      const [x1, y1] = p(R, winkel), [x2, y2] = p(R, winkel + Math.min(a, Math.PI * 2 - 0.0001));
      let pfad;
      if (r0) {
        const [x3, y3] = p(r0, winkel + Math.min(a, Math.PI * 2 - 0.0001)), [x4, y4] = p(r0, winkel);
        pfad = `M${x1} ${y1} A${R} ${R} 0 ${gross} 1 ${x2} ${y2} L${x3} ${y3} A${r0} ${r0} 0 ${gross} 0 ${x4} ${y4} Z`;
      } else {
        pfad = `M${c} ${c} L${x1} ${y1} A${R} ${R} 0 ${gross} 1 ${x2} ${y2} Z`;
      }
      const seg = el("path", { d: pfad, fill: cols[i], stroke: "#fff", "stroke-width": 1.5 }, svg);
      const zeige = (e) => zeigeTooltip(box, e.clientX, e.clientY, [[d.reihen[i].name, cols[i], true],
        [`${zahl(v, d.einheit)} · ${((v / gesamt) * 100).toLocaleString("de-DE", { maximumFractionDigits: 1 })} %`]]);
      seg.addEventListener("pointermove", zeige);
      seg.addEventListener("pointerdown", zeige);
      if (optionen.link && d.reihen[i].id !== "sonstige") { seg.style.cursor = "pointer"; seg.addEventListener("click", () => optionen.link(d.reihen[i])); }
      winkel += a;
    });
    svg.addEventListener("pointerleave", () => { tooltip(box).hidden = true; });
    if (r0) {
      el("text", { x: c, y: c - 2, "text-anchor": "middle", class: "dg-mitte" }, svg).textContent = kurz(gesamt, d.einheit);
      el("text", { x: c, y: c + 16, "text-anchor": "middle", class: "dg-achse" }, svg).textContent = "gesamt";
    }
    wrap.append(svg);
    box.append(wrap);
    const proz = s.map((v) => (gesamt ? Math.round((v / gesamt) * 100) + " %" : ""));
    legende(box, d.reihen, cols, Object.assign({}, optionen, { prozente: proz, immerLegende: true }));
  }

  function tabelle(box, d, optionen) {
    const wrap = html("div", "scroll");
    const t = html("table", "tab dg-tabelle");
    const kopf = html("tr");
    kopf.append(html("th", "", ""));
    const mitZeit = d.labels.length > 1;
    if (mitZeit) d.labels.forEach((l) => kopf.append(html("th", "zahl", l)));
    kopf.append(html("th", "zahl", "Summe"));
    const thead = html("thead"); thead.append(kopf); t.append(thead);
    const tb = html("tbody");
    const spalten = d.labels.map(() => 0);
    let gesamt = 0;
    d.reihen.forEach((r) => {
      const z = html("tr");
      const name = html("td", "", r.name);
      if (optionen.link && r.id !== "sonstige") { name.classList.add("klickbar"); name.addEventListener("click", () => optionen.link(r)); }
      z.append(name);
      let s = 0;
      r.werte.forEach((v, i) => { s += v; if (!r.vorjahr) spalten[i] += v; if (mitZeit) z.append(html("td", "zahl", v ? zahl(v, d.einheit) : "")); });
      if (!r.vorjahr) gesamt += s;
      z.append(html("td", "zahl fett", zahl(s, d.einheit)));
      tb.append(z);
    });
    t.append(tb);
    if (d.reihen.length > 1) {
      const f = html("tr", "summe");
      f.append(html("td", "", "Summe"));
      if (mitZeit) spalten.forEach((v) => f.append(html("td", "zahl", zahl(v, d.einheit))));
      f.append(html("td", "zahl fett", zahl(gesamt, d.einheit)));
      const tf = html("tfoot"); tf.append(f); t.append(tf);
    }
    wrap.append(t);
    box.append(wrap);
  }

  function kennzahl(box, d) {
    const akt = d.reihen.filter((r) => !r.vorjahr), vj = d.reihen.filter((r) => r.vorjahr);
    const s = d.summe !== undefined ? d.summe : akt.reduce((a, r) => a + r.werte.reduce((x, y) => x + y, 0), 0);
    const k = html("div", "dg-kennzahl");
    k.append(html("div", "wert", zahl(s, d.einheit)));
    if (vj.length) {
      const v = vj.reduce((a, r) => a + r.werte.reduce((x, y) => x + y, 0), 0);
      const p = v ? Math.round(((s - v) / Math.abs(v)) * 100) : null;
      k.append(html("div", "leise", `Vorjahr ${zahl(v, d.einheit)}${p !== null ? ` · ${p > 0 ? "+" : ""}${p} %` : ""}`));
    }
    if (d.labels.length > 1) k.append(html("div", "leise", `Ø ${zahl(s / d.labels.length, d.einheit)} je Zeitabschnitt`));
    box.append(k);
  }

  function heatmap(box, d, optionen) {
    const max = Math.max(1, ...d.reihen.flatMap((r) => r.werte.map(Math.abs)));
    const wrap = html("div", "scroll");
    const t = html("table", "dg-heatmap");
    const kopf = html("tr");
    kopf.append(html("th"));
    d.labels.forEach((l) => kopf.append(html("th", "", l)));
    t.append(kopf);
    d.reihen.forEach((r) => {
      const z = html("tr");
      const name = html("th", "name", r.name);
      if (optionen.link && r.id !== "sonstige") { name.classList.add("klickbar"); name.addEventListener("click", () => optionen.link(r)); }
      z.append(name);
      r.werte.forEach((v, i) => {
        const c = html("td");
        const a = Math.abs(v) / max;
        c.style.background = v ? `rgba(${v < 0 ? "181,71,90" : "15,107,92"},${0.08 + a * 0.82})` : "transparent";
        c.style.color = a > 0.55 ? "#fff" : "inherit";
        c.textContent = v ? kurz(v, d.einheit) : "";
        c.title = `${r.name} · ${d.labels[i]}: ${zahl(v, d.einheit)}`;
        z.append(c);
      });
      t.append(z);
    });
    wrap.append(t);
    box.append(wrap);
  }

  function zeichne(box, d, typ, optionen) {
    optionen = optionen || {};
    box.innerHTML = "";
    if (!d || !d.reihen || !d.reihen.length || d.reihen.every((r) => r.werte.every((v) => !v))) {
      box.append(html("p", "leer", "Keine Daten für diese Auswahl und diesen Zeitraum."));
      return;
    }
    if (["balken", "gestapelt", "linie", "flaeche"].includes(typ)) {
      if (d.labels.length < 2 && typ !== "balken" && typ !== "gestapelt") return horizontal(box, d, optionen);
      return kartesisch(box, d, typ, optionen);
    }
    if (typ === "horizontal") return horizontal(box, d, optionen);
    if (typ === "donut" || typ === "torte") return ring(box, d, typ, optionen);
    if (typ === "tabelle") return tabelle(box, d, optionen);
    if (typ === "kennzahl") return kennzahl(box, d);
    if (typ === "heatmap") return heatmap(box, d, optionen);
    return kartesisch(box, d, "balken", optionen);
  }

  window.Diagramme = { zeichne, zahl };
})();
