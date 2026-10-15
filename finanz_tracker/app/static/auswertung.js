// Seite „Eigene Auswertungen“: Diagramme anlegen, bearbeiten, sortieren, speichern und zeichnen.
(function () {
  "use strict";
  const daten = JSON.parse(document.getElementById("dg-daten").textContent);
  const opt = daten.optionen;
  let diagramme = daten.diagramme || [];
  const raster = document.getElementById("dg-raster");
  const leer = document.getElementById("dg-leer");
  const dialog = document.getElementById("dg-editor");
  const form = document.getElementById("dg-form");
  const vorschau = document.getElementById("dg-vorschau");
  const csrf = (document.querySelector("input[name=csrf]") || {}).value || "";
  const cache = new Map();
  let bearbeitet = null; // Index oder -1 (neu)

  const auswahlListe = {
    kategorie: opt.kategorien, tag: opt.tags, person: opt.personen, konto: opt.konten, vertrag: opt.vertraege,
  };
  const filterName = { kategorie: "kategorie", tag: "tag", person: "person", konto: "konto", vertrag: "vertrag" };

  async function hole(k) {
    const schluessel = JSON.stringify(k);
    if (cache.has(schluessel)) return cache.get(schluessel);
    const r = await fetch("/auswertung/daten", {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf }, body: schluessel,
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.fehler || "Fehler beim Laden");
    cache.set(schluessel, d);
    return d;
  }

  function titel(k) {
    if (k.titel) return k.titel;
    const g = opt.gruppen[k.gruppe] || "";
    return `${opt.messgroessen[k.messgroesse] || "Ausgaben"}${k.gruppe && k.gruppe !== "gesamt" ? " nach " + g : ""}`;
  }
  function untertitel(k, d) {
    const teile = [opt.zeitraeume[k.zeitraum] || "", opt.zeiten[k.zeit] || ""];
    if (k.vergleich === "vorjahr") teile.push("mit Vorjahr");
    if (k.kumuliert) teile.push("kumuliert");
    if (d && d.einheit === "€" && d.summe && !["saldo"].includes(k.messgroesse) && k.gruppe !== "einaus")
      teile.push("Summe " + window.Diagramme.zahl(d.summe, "€"));
    return teile.filter(Boolean).join(" · ");
  }

  function letzterTag(monat) {
    const [j, m] = monat.split("-").map(Number);
    return `${monat}-${String(new Date(j, m, 0).getDate()).padStart(2, "0")}`;
  }
  function buchungsLink(k, d, reihe, zeitIndex) {
    const p = new URLSearchParams();
    if (zeitIndex !== undefined && d.zeit === "monat") {
      p.set("monat", d.schluessel[zeitIndex]);
    } else {
      p.set("monat", "alle");
      let von = d.von, bis = d.bis;
      if (zeitIndex !== undefined && d.zeit === "jahr") { von = `${d.schluessel[zeitIndex]}-01`; bis = `${d.schluessel[zeitIndex]}-12`; }
      if (zeitIndex !== undefined && d.zeit === "quartal") {
        const [j, q] = d.schluessel[zeitIndex].split("-Q");
        von = `${j}-${String((q - 1) * 3 + 1).padStart(2, "0")}`; bis = `${j}-${String(q * 3).padStart(2, "0")}`;
      }
      p.set("von", `${von}-01`); p.set("bis", letzterTag(bis));
    }
    if (k.messgroesse === "ausgaben") p.set("art", "ausgabe");
    if (k.messgroesse === "einnahmen") p.set("art", "einnahme");
    if (reihe) {
      const g = k.gruppe;
      if (g === "einaus") p.set("art", reihe.id === "einnahme" ? "einnahme" : "ausgabe");
      else if (g === "gegenpartei") p.set("partei", reihe.name);
      else if (g === "unterkategorie") p.set("kategorie", reihe.id);
      else if (filterName[g]) p.set(filterName[g], reihe.id === "ohne" && g === "kategorie" ? "ohne" : reihe.id);
    }
    return `/buchungen/?${p.toString()}`;
  }

  function zeichneKarte(karte, k) {
    const flaeche = karte.querySelector(".dg-flaeche");
    const unter = karte.querySelector(".dg-unter");
    flaeche.innerHTML = '<p class="leise klein">lädt …</p>';
    hole(k).then((d) => {
      unter.textContent = untertitel(k, d);
      window.Diagramme.zeichne(flaeche, d, k.typ, {
        link: (r) => { window.location.href = buchungsLink(k, d, r); },
        linkZeit: (i) => { window.location.href = buchungsLink(k, d, null, i); },
      });
    }).catch((e) => { flaeche.innerHTML = ""; flaeche.append(Object.assign(document.createElement("p"), { className: "flash warn", textContent: e.message })); });
  }

  function knopf(text, titelText, aktion) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn klein"; b.textContent = text; b.title = titelText;
    b.setAttribute("aria-label", titelText);
    b.addEventListener("click", aktion);
    return b;
  }

  function alleZeichnen() {
    raster.innerHTML = "";
    leer.hidden = diagramme.length > 0;
    diagramme.forEach((k, i) => {
      const karte = document.createElement("section");
      karte.className = "karte dg-karte" + (k.breite === "voll" ? " voll" : "");
      const kopf = document.createElement("div");
      kopf.className = "dg-kopf";
      const t = document.createElement("div");
      t.innerHTML = "<h2></h2><div class='leise klein dg-unter'></div>";
      t.querySelector("h2").textContent = titel(k);
      const knoepfe = document.createElement("div");
      knoepfe.className = "dg-knoepfe";
      knoepfe.append(
        knopf("✎", "Bearbeiten", () => oeffneEditor(i)),
        knopf("⧉", "Duplizieren", () => { diagramme.splice(i + 1, 0, JSON.parse(JSON.stringify(k))); speichern(); }),
        knopf("↑", "Nach oben", () => { if (i > 0) { [diagramme[i - 1], diagramme[i]] = [diagramme[i], diagramme[i - 1]]; speichern(); } }),
        knopf("↓", "Nach unten", () => { if (i < diagramme.length - 1) { [diagramme[i + 1], diagramme[i]] = [diagramme[i], diagramme[i + 1]]; speichern(); } }),
        knopf("✕", "Entfernen", () => { if (window.confirm(`Diagramm „${titel(k)}“ entfernen?`)) { diagramme.splice(i, 1); speichern(); } }),
      );
      kopf.append(t, knoepfe);
      const f = document.createElement("div");
      f.className = "dg-flaeche";
      karte.append(kopf, f);
      raster.append(karte);
      zeichneKarte(karte, k);
    });
  }

  async function speichern() {
    alleZeichnen();
    await fetch(`/auswertung/ansicht/${daten.aid}`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf },
      body: JSON.stringify({ diagramme }),
    });
  }

  // ---------------------------------------------------------------- Editor
  function fuelleAuswahl(gruppe, gewaehlt) {
    const sel = form.elements.auswahl;
    sel.innerHTML = "";
    (auswahlListe[gruppe] || []).forEach((e) => {
      const o = document.createElement("option");
      o.value = e.id; o.textContent = e.name;
      o.selected = (gewaehlt || []).map(String).includes(String(e.id));
      sel.append(o);
    });
  }
  function sichtbarkeit() {
    const g = form.elements.gruppe.value;
    form.querySelectorAll("[data-nur-gruppe]").forEach((el) => { el.hidden = !el.dataset.nurGruppe.split(" ").includes(g); });
    form.querySelectorAll("[data-nur-zeitraum]").forEach((el) => { el.hidden = form.elements.zeitraum.value !== el.dataset.nurZeitraum; });
  }
  function ausFormular() {
    const e = form.elements;
    const k = {
      titel: e.titel.value.trim(), typ: e.typ.value, breite: e.breite.value, messgroesse: e.messgroesse.value,
      gruppe: e.gruppe.value, zeit: e.zeit.value, zeitraum: e.zeitraum.value,
      vergleich: e.vergleich.checked ? "vorjahr" : "keiner", kumuliert: e.kumuliert.checked,
      top: parseInt(e.top.value, 10) || 0,
    };
    if (k.gruppe === "unterkategorie") k.eltern = e.eltern.value;
    if (auswahlListe[k.gruppe]) k.auswahl = Array.from(e.auswahl.selectedOptions).map((o) => o.value);
    if (k.zeitraum === "eigen") { k.von = e.von.value; k.bis = e.bis.value; }
    return k;
  }
  function insFormular(k) {
    const e = form.elements;
    e.titel.value = k.titel || ""; e.typ.value = k.typ || "balken"; e.breite.value = k.breite || "halb";
    e.messgroesse.value = k.messgroesse || "ausgaben"; e.gruppe.value = k.gruppe || "kategorie";
    e.zeit.value = k.zeit || "monat"; e.zeitraum.value = k.zeitraum || "12";
    e.vergleich.checked = k.vergleich === "vorjahr"; e.kumuliert.checked = !!k.kumuliert;
    e.top.value = k.top || ""; e.von.value = k.von || ""; e.bis.value = k.bis || "";
    if (k.eltern) e.eltern.value = k.eltern;
    fuelleAuswahl(e.gruppe.value, k.auswahl);
    sichtbarkeit();
  }
  let warte;
  function vorschauZeichnen() {
    clearTimeout(warte);
    warte = setTimeout(() => {
      const k = ausFormular();
      vorschau.innerHTML = '<p class="leise klein">lädt …</p>';
      hole(k).then((d) => window.Diagramme.zeichne(vorschau, d, k.typ, {})).catch((err) => { vorschau.textContent = err.message; });
    }, 250);
  }
  function oeffneEditor(i) {
    bearbeitet = i;
    insFormular(i >= 0 ? diagramme[i] : { typ: "balken", messgroesse: "ausgaben", gruppe: "kategorie", zeit: "monat", zeitraum: "12", top: 6, breite: "halb" });
    document.getElementById("dg-editor-titel").textContent = i >= 0 ? "Diagramm bearbeiten" : "Diagramm hinzufügen";
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
    vorschauZeichnen();
  }
  form.elements.gruppe.addEventListener("change", () => { fuelleAuswahl(form.elements.gruppe.value, []); sichtbarkeit(); });
  form.elements.zeitraum.addEventListener("change", sichtbarkeit);
  form.addEventListener("input", vorschauZeichnen);
  form.addEventListener("change", vorschauZeichnen);
  dialog.addEventListener("close", () => {
    if (dialog.returnValue !== "speichern") return;
    const k = ausFormular();
    if (bearbeitet >= 0) diagramme[bearbeitet] = k; else diagramme.push(k);
    speichern();
  });
  document.getElementById("dg-neu").addEventListener("click", () => oeffneEditor(-1));

  let breite = window.innerWidth;
  window.addEventListener("resize", () => {
    if (Math.abs(window.innerWidth - breite) < 40) return;
    breite = window.innerWidth;
    clearTimeout(warte);
    warte = setTimeout(alleZeichnen, 200);
  });
  alleZeichnen();
})();
