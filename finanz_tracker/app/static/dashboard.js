// Dashboard (0.8.0): ein-/ausklappbare Bereiche, Nettovermögen, Cashflow-Sankey, Ausgaben-Ring, Vermögensaufstellung.
(function () {
  "use strict";
  const datenEl = document.getElementById("dash-daten");
  if (!datenEl || !window.Diagramme) return;
  const D = JSON.parse(datenEl.textContent);
  const DG = window.Diagramme;
  const MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  const mk = (m) => MONATE[parseInt(m.slice(5, 7), 10) - 1] + " " + m.slice(2, 4);

  function lies(schl, standard) {
    try { const v = localStorage.getItem(schl); return v === null ? standard : JSON.parse(v); } catch (e) { return standard; }
  }
  function schreib(schl, wert) {
    try { localStorage.setItem(schl, JSON.stringify(wert)); } catch (e) { /* privat: egal */ }
  }

  // ---------------------------------------------------------------- Zeichnen je Bereich
  const zeichner = {};
  function zeichneBereich(id) {
    const s = document.querySelector(`[data-bereich="${id}"]`);
    if (s && !s.classList.contains("zu") && zeichner[id]) zeichner[id]();
  }

  // ---------------------------------------------------------------- Ein- und Ausklappen
  const ZU_KEY = "dashboard-bereiche-zu";
  let zu = lies(ZU_KEY, []);
  const bereiche = [...document.querySelectorAll("[data-bereich]")];
  function setze(s, offen, speichern) {
    const id = s.dataset.bereich;
    s.classList.toggle("zu", !offen);
    s.querySelector(".bereich-schalter").setAttribute("aria-expanded", offen ? "true" : "false");
    s.querySelector(".bereich-inhalt").hidden = !offen;
    if (speichern) {
      zu = zu.filter((x) => x !== id);
      if (!offen) zu.push(id);
      schreib(ZU_KEY, zu);
    }
    if (offen) zeichneBereich(id);
  }
  bereiche.forEach((s) => {
    if (zu.includes(s.dataset.bereich)) setze(s, false, false);
    s.querySelector(".bereich-schalter").addEventListener("click", () => setze(s, s.classList.contains("zu"), true));
  });
  requestAnimationFrame(() => document.body.classList.add("bereiche-bereit"));
  document.querySelectorAll("[data-alle-bereiche]").forEach((b) => b.addEventListener("click", () => {
    const auf = b.dataset.alleBereiche === "auf";
    bereiche.forEach((s) => setze(s, auf, true));
  }));

  // ---------------------------------------------------------------- Segment-Schalter
  function segment(attr, schl, standard, beiWahl) {
    const knoepfe = [...document.querySelectorAll(`[${attr}]`)];
    let wahl = lies(schl, standard);
    if (!knoepfe.some((b) => b.getAttribute(attr) === wahl)) wahl = standard;
    const markiere = () => knoepfe.forEach((b) => {
      const an = b.getAttribute(attr) === wahl;
      b.classList.toggle("an", an);
      b.setAttribute("aria-pressed", an ? "true" : "false");
    });
    knoepfe.forEach((b) => b.addEventListener("click", () => {
      wahl = b.getAttribute(attr); schreib(schl, wahl); markiere(); beiWahl(wahl);
    }));
    markiere();
    return () => wahl;
  }

  // ---------------------------------------------------------------- Nettovermögen
  const nvWahl = segment("data-nv-zeit", "dashboard-nv-zeit", "12", () => zeichneBereich("nettovermoegen"));
  zeichner.nettovermoegen = () => {
    const box = document.getElementById("dg-nv");
    if (!box) return;
    const z = nvWahl();
    const n = z === "alle" ? D.nv.labels.length : Math.min(D.nv.labels.length, parseInt(z, 10) + 1);
    const werte = D.nv.netto.slice(-n), labels = D.nv.labels.slice(-n);
    const delta = werte.length ? werte[werte.length - 1] - werte[0] : 0;
    const basis = werte.length ? Math.abs(werte[0]) : 0;
    const farbe = delta >= 0 ? "#0F6B5C" : "#B5475A";
    const el = document.getElementById("nv-delta");
    if (el) {
      const p = basis ? (delta / basis) * 100 : null;
      el.textContent = `${delta >= 0 ? "+" : "−"}${DG.zahl(Math.abs(delta), "€")}` +
        (p !== null ? ` (${delta >= 0 ? "+" : "−"}${Math.abs(p).toLocaleString("de-DE", { maximumFractionDigits: 1 })} %)` : "") +
        ` seit ${mk(labels[0] || "")}`;
      el.style.color = farbe;
    }
    DG.zeichne(box, { labels: labels.map(mk), einheit: "€", reihen: [{ name: "Nettovermögen", werte }] }, "flaeche",
      { hoehe: 230, farben: [farbe], ohneNull: true, ohnePunkte: werte.length > 13, ohneLegende: true, links: 64 });
  };

  // ---------------------------------------------------------------- Cashflow
  const cfWahl = segment("data-cf", "dashboard-cashflow", "monat", () => { zahlenCashflow(); zeichneBereich("cashflow"); });
  function zahlenCashflow() {
    const cf = D.cashflow[cfWahl()];
    if (!cf || cfWahl() === "monat") return; // Monatswerte kommen vom Server (mit Vormonat)
    const setze = (id, wert, unter, link) => {
      const k = document.getElementById(id);
      if (!k) return;
      k.querySelector("b").textContent = wert;
      k.querySelector(".klein").textContent = unter;
      if (link && k.tagName === "A") k.href = link;
    };
    const saldo = cf.einnahmen - cf.ausgaben;
    const zeitraum = `${mk(cf.von)} – ${mk(cf.bis)}`;
    setze("cf-ein", DG.zahl(cf.einnahmen, "€"), zeitraum, cf.url + "&art=einnahme");
    setze("cf-aus", DG.zahl(cf.ausgaben, "€"), zeitraum, cf.url + "&art=ausgabe");
    setze("cf-saldo", DG.zahl(saldo, "€"), cf.einnahmen > 0 ? `${Math.round((saldo / cf.einnahmen) * 100)} % der Einnahmen` : "–");
    document.querySelector("#cf-saldo b").classList.toggle("pos", saldo > 0);
  }
  const cfStart = document.getElementById("cf-ein") && {
    ein: document.getElementById("cf-ein").innerHTML, aus: document.getElementById("cf-aus").innerHTML,
    saldo: document.getElementById("cf-saldo").innerHTML,
    einHref: document.getElementById("cf-ein").href, ausHref: document.getElementById("cf-aus").href };
  document.querySelectorAll("[data-cf]").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.cf === "monat" && cfStart) {
      const e = document.getElementById("cf-ein"), a = document.getElementById("cf-aus");
      e.innerHTML = cfStart.ein; a.innerHTML = cfStart.aus; document.getElementById("cf-saldo").innerHTML = cfStart.saldo;
      e.href = cfStart.einHref; a.href = cfStart.ausHref;
    }
  }));
  zahlenCashflow();
  zeichner.cashflow = () => {
    const box = document.getElementById("dg-cashflow");
    const cf = D.cashflow[cfWahl()];
    if (!box || !cf) return;
    DG.zeichne(box, { quellen: cf.quellen, ziele: cf.ziele, mitte: "Einnahmen" }, "sankey", {
      link: (x, seite) => {
        location.href = cf.url + "&kategorie=" + (x.id === null ? "ohne" : x.id) + "&art=" + (seite === "quelle" ? "einnahme" : "ausgabe");
      },
    });
  };

  // ---------------------------------------------------------------- Ausgaben-Ring
  zeichner.ausgaben = () => {
    const box = document.getElementById("dg-ausgaben");
    if (!box || !D.ausgaben.reihen.length) return;
    const zeilen = [...document.querySelectorAll(".ausgaben-liste .katzeile[data-index]")];
    DG.zeichne(box, D.ausgaben, "donut", {
      farben: D.ausgaben.farben, ohneLegende: true, groesse: 210, mitteText: "Ausgaben",
      hover: (i) => {
        zeilen.forEach((z) => z.classList.toggle("hervor", i !== null && +z.dataset.index === i));
        box.querySelectorAll("path").forEach((p) => p.style.opacity = i === null || +p.dataset.index === i ? 1 : 0.35);
      },
      link: (r) => { location.href = D.ausgaben.url + "&kategorie=" + (r.id === null ? "ohne" : r.id); },
    });
  };
  document.querySelectorAll(".ausgaben-liste .katzeile[data-index]").forEach((z) => {
    const ring = () => document.querySelectorAll("#dg-ausgaben path");
    z.addEventListener("pointerenter", () => ring().forEach((p) => { p.style.opacity = +p.dataset.index === +z.dataset.index ? 1 : 0.35; }));
    z.addEventListener("pointerleave", () => ring().forEach((p) => { p.style.opacity = 1; }));
  });

  // ---------------------------------------------------------------- Vermögensaufstellung
  segment("data-bilanz", "dashboard-bilanz", "aktiva", (w) => zeigeSeite(w));
  function zeigeSeite(w) {
    document.querySelectorAll("[data-bilanz-seite]").forEach((s) => { s.hidden = s.dataset.bilanzSeite !== w; });
  }
  zeigeSeite(lies("dashboard-bilanz", "aktiva") === "passiva" ? "passiva" : "aktiva");
  zeichner.bilanz = () => {
    document.querySelectorAll(".spark[data-werte]").forEach((s) => {
      try {
        const w = JSON.parse(s.dataset.werte);
        // bei Schulden ist ein sinkender Verlauf gut
        const gut = s.closest("[data-umgekehrt]") ? w[w.length - 1] <= w[0] : w[w.length - 1] >= w[0];
        DG.spark(s, w, gut ? "#0F6B5C" : "#B5475A");
      } catch (e) { /* egal */ }
    });
  };

  // ---------------------------------------------------------------- 12-Monats-Verlauf
  zeichner.verlauf = () => {
    const box = document.getElementById("dg-verlauf");
    if (!box) return;
    const roh = D.verlauf.labels;
    DG.zeichne(box, Object.assign({}, D.verlauf, { labels: roh.map(mk) }), "balken", {
      hoehe: 230, farben: ["#8CC5B6", "#0F6B5C"],
      linkZeit: (i) => { const u = new URL(location.href); u.searchParams.set("monat", roh[i]); location.href = u.toString(); },
    });
  };

  // ---------------------------------------------------------------- Start und Größenänderung
  Object.keys(zeichner).forEach(zeichneBereich);
  let breite = window.innerWidth, timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (Math.abs(window.innerWidth - breite) < 8) return;
      breite = window.innerWidth;
      ["nettovermoegen", "cashflow", "ausgaben", "verlauf"].forEach(zeichneBereich);
    }, 150);
  });
})();
