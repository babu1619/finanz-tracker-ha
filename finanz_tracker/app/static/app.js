// Kleine Helfer ohne externe Bibliotheken.
document.addEventListener("DOMContentLoaded", () => {
  // Rückfrage vor gefährlichen Aktionen
  document.querySelectorAll("form[data-frage]").forEach((f) => {
    f.addEventListener("submit", (e) => { if (!window.confirm(f.dataset.frage)) e.preventDefault(); });
  });

  // Alle auswählen in Tabellen
  const alle = document.getElementById("alle");
  if (alle) {
    alle.addEventListener("change", () => {
      document.querySelectorAll("input[name=ids]").forEach((c) => { c.checked = alle.checked; });
      zaehle();
    });
  }
  const zaehler = document.getElementById("auswahl-zahl");
  function zaehle() {
    if (!zaehler) return;
    const n = document.querySelectorAll("input[name=ids]:checked").length;
    zaehler.textContent = n ? n + " ausgewählt" : "keine ausgewählt";
  }
  document.querySelectorAll("input[name=ids]").forEach((c) => c.addEventListener("change", zaehle));
  zaehle();

  // Sammelaktion: passende Eingabe zeigen
  const aktion = document.getElementById("sammel-aktion");
  if (aktion) {
    const zeige = () => document.querySelectorAll("[data-fuer]").forEach((el) => {
      el.hidden = el.dataset.fuer !== aktion.value;
    });
    aktion.addEventListener("change", zeige);
    zeige();
  }

  // Regel-Formular: Wert-Eingabe passend zum Feld
  document.querySelectorAll(".bedingung").forEach((zeile) => {
    const feld = zeile.querySelector(".b-feld");
    const zeige = () => zeile.querySelectorAll("[data-feldart]").forEach((el) => {
      const arten = el.dataset.feldart.split(" ");
      const art = feld.value === "richtung" ? "richtung" : feld.value === "konto" ? "konto" :
        (feld.value === "betrag" ? "betrag" : (feld.value === "tag" ? "tag" : "text"));
      el.hidden = !arten.includes(art);
      el.querySelectorAll("input,select").forEach((i) => { i.disabled = el.hidden; });
      if (!el.querySelector("input,select") && (el.tagName === "INPUT" || el.tagName === "SELECT")) el.disabled = el.hidden;
    });
    feld.addEventListener("change", zeige);
    zeige();
  });

  // Kategorie-Suche: Datalist-Eingabe in verstecktes Feld übertragen
  document.querySelectorAll("[data-katsuche]").forEach((eingabe) => {
    const ziel = document.getElementById(eingabe.dataset.katsuche);
    const liste = document.getElementById(eingabe.getAttribute("list"));
    eingabe.addEventListener("input", () => {
      const opt = Array.from(liste.options).find((o) => o.value === eingabe.value);
      ziel.value = opt ? opt.dataset.id : "";
      eingabe.setCustomValidity(opt || !eingabe.value ? "" : "Bitte eine Kategorie aus der Liste wählen");
    });
  });

  // Profil-Editor: Spaltenfarben und Live-Vorschau
  const profil = document.getElementById("spaltenzuordnung");
  if (profil) {
    const farben = { datum: "#E6E9F5", valuta: "#EEF0F8", partei: "#DCEDE8", zweck: "#EEF4F1", iban: "#F4F5F2",
      betrag: "#FBEBD0", soll: "#FBEBD0", haben: "#FBEBD0", kennzeichen: "#FDF3E1", saldo: "#FDF3E1", ignore: "#FFFFFF" };
    const daten = JSON.parse(document.getElementById("beispiel-daten").textContent || "[]");
    const selects = Array.from(profil.querySelectorAll("select.spalte"));
    const ausgabe = document.getElementById("live-vorschau");
    const modusFeld = () => (document.querySelector("input[name=betrag_modus]:checked") || {}).value || "vorzeichen";
    const dezimal = () => (document.querySelector("select[name=decimal]") || {}).value || ",";
    const zahl = (t) => {
      if (!t) return null;
      let s = t.replace(/\s|EUR|€/g, ""); let neg = false;
      if (s.endsWith("-")) { neg = true; s = s.slice(0, -1); }
      if (s.startsWith("-")) { neg = true; s = s.slice(1); }
      if (s.startsWith("+")) s = s.slice(1);
      s = dezimal() === "," ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
      const v = parseFloat(s); if (isNaN(v)) return NaN; return neg ? -v : v;
    };
    const fmt = (v) => (v === null ? "–" : isNaN(v) ? "nicht lesbar" :
      (v < 0 ? "−" : "+") + Math.abs(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €");
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    function aktualisiere() {
      const map = selects.map((s) => s.value);
      selects.forEach((s, i) => {
        const farbe = farben[s.value] || "#fff";
        document.querySelectorAll(`[data-spalte="${i}"]`).forEach((el) => {
          el.style.background = farbe;
          el.classList.toggle("ign", s.value === "ignore");
        });
      });
      const nimm = (row, f) => map.map((m, i) => (m === f ? (row[i] || "").trim() : null)).filter((x) => x);
      const zeilen = daten.map((row) => {
        let betrag;
        const modus = modusFeld();
        if (modus === "soll_haben") {
          const s = zahl(nimm(row, "soll")[0] || ""), h = zahl(nimm(row, "haben")[0] || "");
          betrag = (s === null && h === null) ? null : Math.abs(h || 0) - Math.abs(s || 0);
        } else {
          betrag = zahl(nimm(row, "betrag")[0] || "");
          if (modus === "kennzeichen" && betrag !== null && !isNaN(betrag)) {
            const k = (nimm(row, "kennzeichen")[0] || "").toLowerCase();
            betrag = ["s", "soll", "-"].includes(k) ? -Math.abs(betrag) : Math.abs(betrag);
          }
        }
        return `<tr><td class="mono">${esc(nimm(row, "datum")[0] || "– fehlt –")}</td>
          <td><b>${esc(nimm(row, "partei").join(" ") || "–")}</b></td>
          <td class="leise">${esc(nimm(row, "zweck").join(" · ") || "–")}</td>
          <td class="betrag ${betrag > 0 ? "pos" : ""}">${fmt(betrag)}</td>
          <td class="betrag leise">${esc(nimm(row, "saldo")[0] || "–")}</td></tr>`;
      });
      ausgabe.innerHTML = zeilen.join("");
    }
    selects.forEach((s) => s.addEventListener("change", aktualisiere));
    document.querySelectorAll("input[name=betrag_modus], select[name=decimal]").forEach((el) => el.addEventListener("change", aktualisiere));
    aktualisiere();
  }

  // Monatsverlauf auf dem Handy: neueste Monate sichtbar
  document.querySelectorAll(".scroll").forEach((s) => { if (s.querySelector(".verlauf")) s.scrollLeft = s.scrollWidth; });

  // Einklappbare Bereiche: Zustand je Bereich im Browser merken
  document.querySelectorAll("details[data-merken]").forEach((d) => {
    const key = "klappe:" + location.pathname + ":" + d.dataset.merken;
    try {
      const gemerkt = localStorage.getItem(key);
      if (gemerkt !== null && !d.hasAttribute("data-erzwingen")) d.open = gemerkt === "1";
    } catch (e) { /* ohne Speicher: Standard */ }
    d.addEventListener("toggle", () => { try { localStorage.setItem(key, d.open ? "1" : "0"); } catch (e) { /* egal */ } });
  });
  // Häkchen in der Tabelle: Änderungsbereich automatisch öffnen
  const aenderung = document.getElementById("aenderung");
  if (aenderung) {
    document.querySelectorAll("input[name=ids], #alle").forEach((c) => c.addEventListener("change", () => {
      if (document.querySelectorAll("input[name=ids]:checked").length) aenderung.open = true;
    }));
  }

  // Aufteilung einer Buchung
  const splitEditor = document.getElementById("split-editor");
  if (splitEditor) {
    const box = document.getElementById("aufteilen");
    const einzel = document.getElementById("einzelkategorie");
    const zeilen = document.getElementById("split-zeilen");
    const status = document.getElementById("split-status");
    const ziel = Math.abs(parseInt(document.getElementById("buchungsbetrag").dataset.cent, 10));
    const cent = (t) => {
      const s = (t || "").replace(/\s|€/g, "").replace(/\./g, "").replace(",", ".");
      const v = Math.round(parseFloat(s) * 100);
      return isNaN(v) ? 0 : Math.abs(v);
    };
    const fmt = (c) => (c / 100).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
    const summe = () => Array.from(zeilen.querySelectorAll("input[name=split_betrag]")).reduce((a, i) => a + cent(i.value), 0);
    function pruefe() {
      const diff = ziel - summe();
      status.textContent = diff === 0 ? "Summe stimmt" : (diff > 0 ? "noch " + fmt(diff) + " offen" : fmt(-diff) + " zu viel");
      status.style.color = diff === 0 ? "var(--accent-dark)" : "var(--bad)";
      zeilen.querySelectorAll(".split-weg").forEach((b) => { b.disabled = zeilen.children.length <= 2; });
    }
    function umschalten() {
      splitEditor.hidden = !box.checked;
      einzel.hidden = box.checked;
      zeilen.querySelectorAll("input,select").forEach((el) => { el.disabled = !box.checked; });
      pruefe();
    }
    box.addEventListener("change", umschalten);
    zeilen.addEventListener("input", pruefe);
    zeilen.addEventListener("click", (e) => {
      if (e.target.classList.contains("split-weg") && zeilen.children.length > 2) { e.target.closest(".split-zeile").remove(); pruefe(); }
    });
    document.getElementById("split-neu").addEventListener("click", () => {
      const neu = zeilen.lastElementChild.cloneNode(true);
      neu.querySelectorAll("input").forEach((i) => { i.value = ""; });
      neu.querySelectorAll("select").forEach((s) => { s.selectedIndex = 0; });
      zeilen.appendChild(neu);
      const rest = ziel - summe();
      if (rest > 0) neu.querySelector("input[name=split_betrag]").value = (rest / 100).toFixed(2).replace(".", ",");
      pruefe();
    });
    document.getElementById("split-rest").addEventListener("click", () => {
      const felder = zeilen.querySelectorAll("input[name=split_betrag]");
      const letztes = felder[felder.length - 1];
      const ohne = summe() - cent(letztes.value);
      letztes.value = (Math.max(0, ziel - ohne) / 100).toFixed(2).replace(".", ",");
      pruefe();
    });
    document.getElementById("buchung-form").addEventListener("submit", (e) => {
      const sichtbar = !splitEditor.closest("[hidden]");
      if (box.checked && sichtbar && summe() !== ziel) { e.preventDefault(); pruefe(); status.scrollIntoView({ block: "center" }); }
    });
    umschalten();
  }

  // Schnellerfassung: Vorzeichen-Umschalter
  document.querySelectorAll("[data-richtung]").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("[data-richtung]").forEach((x) => x.classList.toggle("an", x === b));
    const feld = document.getElementById("richtung");
    if (feld) feld.value = b.dataset.richtung;
  }));

  // ---- Kategorie-Eingabe mit gemeinsamer Liste (Tabellen): Text -> verstecktes Feld .kat-id
  const katListe = document.getElementById("kat-liste");
  const katId = (text) => {
    if (!katListe || !text) return "";
    const opt = Array.from(katListe.options).find((o) => o.value === text);
    return opt ? opt.dataset.id : null;  // null = ungültig
  };
  document.querySelectorAll(".kat-eingabe").forEach((eingabe) => {
    const ziel = eingabe.parentElement.querySelector(".kat-id");
    eingabe.addEventListener("input", () => {
      const id = katId(eingabe.value);
      if (ziel) ziel.value = id || "";
      eingabe.setCustomValidity(id === null ? "Bitte eine Kategorie aus der Liste wählen" : "");
    });
  });

  // ---- Direkte Bearbeitung in der Buchungstabelle
  const csrf = (document.querySelector("input[name=csrf]") || {}).value || "";
  async function speichereInline(feldBox, wert) {
    const eingabe = feldBox.querySelector(".inline-eingabe");
    feldBox.classList.remove("ok", "fehler");
    feldBox.classList.add("laedt");
    try {
      const r = await fetch(`/buchungen/${feldBox.dataset.bid}/inline`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf },
        body: JSON.stringify({ feld: feldBox.dataset.feld, wert: wert }),
      });
      const d = await r.json().catch(() => ({}));
      if (d.frage_gegenkonto) { feldBox.classList.remove("laedt"); frageGegenkonto(feldBox); return; }
      if (!r.ok || !d.ok) throw new Error(d.meldung || "Speichern fehlgeschlagen");
      if (feldBox.dataset.feld !== "person") eingabe.value = d.anzeige || "";
      eingabe.dataset.alt = eingabe.value;
      eingabe.classList.toggle("leer", !eingabe.value);
      const quelle = feldBox.parentElement.querySelector(".quelle, .tag.offen");
      if (feldBox.dataset.feld === "kategorie" && quelle) quelle.remove();
      feldBox.classList.add("ok");
      setTimeout(() => feldBox.classList.remove("ok"), 1200);
    } catch (e) {
      feldBox.classList.add("fehler");
      eingabe.title = e.message;
      if (eingabe.dataset.alt !== undefined && feldBox.dataset.feld !== "person") eingabe.value = eingabe.dataset.alt;
    } finally {
      feldBox.classList.remove("laedt");
    }
  }
  // Umbuchung direkt in der Tabelle: Gegenkonto auswählen, dann speichern (Barkonto: Gegenbuchung entsteht automatisch)
  function frageGegenkonto(box) {
    const vorlage = document.getElementById("gegenkonto-vorlage");
    if (!vorlage || box.querySelector(".gegenkonto-wahl")) return;
    const wahl = vorlage.content.firstElementChild.cloneNode(true);
    box.appendChild(wahl);
    wahl.focus();
    const eingabe = box.querySelector(".inline-eingabe");
    const abbrechen = () => { wahl.remove(); eingabe.value = eingabe.dataset.alt; };
    wahl.addEventListener("keydown", (e) => { if (e.key === "Escape") abbrechen(); });
    wahl.addEventListener("change", async () => {
      if (!wahl.value) return;
      box.classList.add("laedt");
      try {
        const r = await fetch(`/buchungen/${box.dataset.bid}/inline`, {
          method: "POST", headers: { "Content-Type": "application/json", "X-CSRF": csrf },
          body: JSON.stringify({ feld: "umbuchung", wert: wahl.value }),
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || !d.ok) throw new Error(d.meldung || "Speichern fehlgeschlagen");
        const zelle = box.closest("td");
        zelle.innerHTML = "";
        const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = "Umbuchung";
        const info = document.createElement("span"); info.className = "quelle"; info.textContent = d.anzeige.replace("Umbuchung ", "");
        zelle.append(tag, info);
        const zeile = zelle.closest("tr");
        zeile.querySelectorAll(".betrag").forEach((x) => { x.style.color = "#56625D"; });
        zeile.classList.add("gespeichert");
      } catch (e) {
        box.classList.add("fehler"); eingabe.title = e.message; abbrechen();
      } finally { box.classList.remove("laedt"); }
    });
  }
  document.querySelectorAll(".inline-feld").forEach((box) => {
    const eingabe = box.querySelector(".inline-eingabe");
    eingabe.dataset.alt = eingabe.value;
    if (box.dataset.feld === "person") {
      eingabe.addEventListener("change", () => speichereInline(box, eingabe.value));
    } else if (box.dataset.feld === "kategorie") {
      const fertig = () => {
        if (eingabe.value === eingabe.dataset.alt) return;
        const id = katId(eingabe.value);
        if (id === null) { box.classList.add("fehler"); eingabe.title = "Bitte eine Kategorie aus der Liste wählen"; return; }
        const opt = Array.from(katListe.options).find((o) => o.value === eingabe.value);
        if (opt && opt.dataset.art === "umbuchung") { frageGegenkonto(box); return; }
        speichereInline(box, id || "");
      };
      eingabe.addEventListener("change", fertig);
      eingabe.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); eingabe.blur(); } if (e.key === "Escape") { eingabe.value = eingabe.dataset.alt; eingabe.blur(); } });
    } else {
      eingabe.addEventListener("change", () => { if (eingabe.value !== eingabe.dataset.alt) speichereInline(box, eingabe.value); });
      eingabe.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); eingabe.blur(); } if (e.key === "Escape") { eingabe.value = eingabe.dataset.alt; eingabe.blur(); } });
    }
  });

  // ---- Spaltenfilter: Popup über allem anzeigen (nicht von der scrollenden Tabelle abgeschnitten)
  const filterDetails = Array.from(document.querySelectorAll("details.spaltenfilter"));
  function platziere(d) {
    const pop = d.querySelector(".filter-pop");
    const r = d.querySelector("summary").getBoundingClientRect();
    const breite = Math.min(300, window.innerWidth - 24);
    pop.style.width = breite + "px";
    pop.style.left = Math.max(12, Math.min(r.left, window.innerWidth - breite - 12)) + "px";
    pop.style.top = (r.bottom + 6) + "px";
  }
  filterDetails.forEach((d) => d.addEventListener("toggle", () => {
    if (!d.open) return;
    filterDetails.forEach((x) => { if (x !== d) x.open = false; });
    platziere(d);
    const erstes = d.querySelector(".filter-pop input:not([type=hidden]), .filter-pop select");
    if (erstes) erstes.focus();
  }));
  const schliesseFilter = () => filterDetails.forEach((d) => { d.open = false; });
  document.addEventListener("click", (e) => { if (!e.target.closest("details.spaltenfilter")) schliesseFilter(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") schliesseFilter(); });
  window.addEventListener("scroll", () => filterDetails.filter((d) => d.open).forEach(platziere), { passive: true });
  document.querySelectorAll(".scroll").forEach((s) => s.addEventListener("scroll", schliesseFilter, { passive: true }));

  // ---- Wird in einem Formular die Kategorie „Umbuchung“ gewählt, auf Art „Umbuchung“ umschalten
  document.querySelectorAll("[data-katsuche]").forEach((eingabe) => {
    const liste = document.getElementById(eingabe.getAttribute("list"));
    eingabe.addEventListener("change", () => {
      const opt = liste && Array.from(liste.options).find((o) => o.value === eingabe.value);
      const umb = document.querySelector("input[data-art][value=umbuchung]");
      if (opt && opt.dataset.art === "umbuchung" && umb) { umb.checked = true; umb.dispatchEvent(new Event("change")); }
    });
  });

  // ---- Prüf-Modus einzeln: Art (Kategorie/Umbuchung) und Tag-Vorschläge
  const artFelder = document.querySelectorAll("input[data-art]");
  if (artFelder.length) {
    const zeigeArt = () => {
      const art = (document.querySelector("input[data-art]:checked") || {}).value || "kategorie";
      document.querySelectorAll("[data-art-fuer]").forEach((el) => { el.hidden = el.dataset.artFuer !== art; });
      document.querySelectorAll(".umschalter.gross label").forEach((l) => l.classList.toggle("an", l.querySelector("input").checked));
    };
    artFelder.forEach((r) => r.addEventListener("change", zeigeArt));
    zeigeArt();
  }
  document.querySelectorAll("[data-tag-plus]").forEach((k) => k.addEventListener("click", () => {
    const feld = document.getElementById("pruef-tags");
    const liste = feld.value.split(",").map((t) => t.trim()).filter(Boolean);
    if (!liste.includes(k.dataset.tagPlus)) liste.push(k.dataset.tagPlus);
    feld.value = liste.join(", ");
    k.remove();
  }));

  // ---- Prüf-Modus Tabelle: Werte auf ausgewählte Zeilen übertragen
  const pruefTab = document.getElementById("pruef-tabelle");
  if (pruefTab) {
    const zeilen = () => Array.from(pruefTab.querySelectorAll("tbody tr"));
    const gewaehlt = () => zeilen().filter((z) => z.querySelector("input[name=ids]").checked);
    pruefTab.querySelectorAll("tbody tr").forEach((z) => {
      z.querySelectorAll("input:not([name=ids]), select").forEach((el) => el.addEventListener("change", () => {
        z.querySelector("input[name=ids]").checked = true;
        z.classList.add("sel");
        zaehle();
      }));
      z.querySelector("input[name=ids]").addEventListener("change", (e) => z.classList.toggle("sel", e.target.checked));
    });
    document.getElementById("alle-mit-vorschlag").addEventListener("click", () => {
      zeilen().forEach((z) => { if (z.dataset.vorschlag === "1") { z.querySelector("input[name=ids]").checked = true; z.classList.add("sel"); } });
      zaehle();
    });
    document.getElementById("massen-anwenden").addEventListener("click", () => {
      const m = (n) => pruefTab.querySelector(`[data-massen="${n}"]`);
      const katText = m("kat").value, katWert = katId(katText);
      if (katText && katWert === null) { m("kat").reportValidity(); return; }
      const auswahl = gewaehlt();
      if (!auswahl.length) { alert("Bitte zuerst Zeilen ankreuzen."); return; }
      auswahl.forEach((z) => {
        if (katText) { z.querySelector(".kat-eingabe").value = katText; z.querySelector(".kat-id").value = katWert; }
        const p = m("person").value;
        if (p) z.querySelector("[data-feld=person]").value = p === "0" ? "" : p;
        const t = m("tags").value.trim();
        if (t) {
          const feld = z.querySelector("[data-feld=tags]");
          const liste = feld.value.split(",").map((x) => x.trim()).filter(Boolean);
          t.split(",").map((x) => x.trim()).filter(Boolean).forEach((x) => { if (!liste.includes(x)) liste.push(x); });
          feld.value = liste.join(", ");
        }
        const g = m("gegen").value;
        if (g) {
          const sel = z.querySelector("[data-feld=gegen]");
          const ziel = g === "kein" ? "" : g;
          if (Array.from(sel.options).some((o) => o.value === ziel)) sel.value = ziel;
        }
      });
    });
  }

  // Tastatur im Prüf-Modus: Enter = speichern (Standard), "s" = überspringen
  const skip = document.getElementById("ueberspringen");
  if (skip) {
    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, select, textarea")) return;
      if (e.key === "s") skip.click();
    });
  }
});

// Installierbare App: Service Worker nur in sicherem Kontext (HTTPS mit vertrautem Zertifikat)
if ("serviceWorker" in navigator && window.isSecureContext) {
  window.addEventListener("load", () => { navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {}); });
}
