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
      if (box.checked && summe() !== ziel) { e.preventDefault(); pruefe(); status.scrollIntoView({ block: "center" }); }
    });
    umschalten();
  }

  // Schnellerfassung: Vorzeichen-Umschalter
  document.querySelectorAll("[data-richtung]").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("[data-richtung]").forEach((x) => x.classList.toggle("an", x === b));
    const feld = document.getElementById("richtung");
    if (feld) feld.value = b.dataset.richtung;
  }));

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
