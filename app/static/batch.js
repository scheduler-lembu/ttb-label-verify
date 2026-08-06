"use strict";

(function () {
  var demoBtn = document.getElementById("demo-button");
  var uploadForm = document.getElementById("upload-form");
  var errorBox = document.getElementById("batch-error");
  var resultsSec = document.getElementById("batch-results");
  var summaryEl = document.getElementById("triage-summary");
  var foldersEl = document.getElementById("folders");
  var detailPanel = document.getElementById("detail-panel");
  var detailTitle = document.getElementById("detail-title");
  var detailTbody = document.getElementById("detail-tbody");
  var detailBack = document.getElementById("detail-back");

  var state;

  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }

  function reset() {
    clearError();
    foldersEl.innerHTML = "";
    detailPanel.hidden = true;
    foldersEl.hidden = false;
    state = { total: 0, done: 0, cleared: 0, attention: 0, folders: {}, order: [] };
    resultsSec.hidden = false;
    summaryEl.textContent = "Starting…";
  }

  function updateSummary(done) {
    var lead = done ? "Done" : (state.done + " of " + state.total + " checked");
    summaryEl.textContent = lead + "  —  ✓ " + state.cleared
      + " cleared automatically   ▲ " + state.attention + " need your attention";
  }

  // --- Detail panel: full per-field readout for one label (reuses the
  //     single-label result shape: field | extracted | expected | verdict). ---
  function openDetail(item) {
    detailTitle.textContent = item.name;
    detailTbody.innerHTML = "";
    (item.fields || []).forEach(function (row) {
      var tr = document.createElement("tr");
      var f = document.createElement("td"); f.className = "cell-field"; f.textContent = row.label;
      var x = document.createElement("td"); x.className = "cell-val"; x.textContent = row.extracted;
      var e = document.createElement("td"); e.className = "cell-val"; e.textContent = row.expected;
      var r = document.createElement("td"); r.className = "cell-result";
      var badge = document.createElement("span");
      badge.className = "badge badge-" + row.verdict;
      badge.textContent = row.verdict_label;
      r.appendChild(badge);
      if (row.reason) {
        var reason = document.createElement("div");
        reason.className = "reason"; reason.textContent = row.reason;
        r.appendChild(reason);
      }
      tr.appendChild(f); tr.appendChild(x); tr.appendChild(e); tr.appendChild(r);
      detailTbody.appendChild(tr);
    });
    foldersEl.hidden = true;
    detailPanel.hidden = false;
  }

  function closeDetail() {
    detailPanel.hidden = true;
    foldersEl.hidden = false;
  }

  // --- Folders ---
  function ensureFolder(tag) {
    var f = state.folders[tag.folder_id];
    if (f) return f;

    var card = document.createElement("div");
    card.className = "folder-card";

    var head = document.createElement("button");
    head.type = "button";
    head.className = "folder-head";

    var name = document.createElement("span");
    name.className = "folder-name"; name.textContent = tag.folder_label;
    var count = document.createElement("span");
    count.className = "folder-count"; count.textContent = "0";
    head.appendChild(name); head.appendChild(count);

    var list = document.createElement("div");
    list.className = "folder-list"; list.hidden = true;

    head.addEventListener("click", function () {
      list.hidden = !list.hidden;
      card.classList.toggle("open", !list.hidden);
    });

    card.appendChild(head); card.appendChild(list);
    foldersEl.appendChild(card);

    f = { label: tag.folder_label, items: [], countEl: count, listEl: list };
    state.folders[tag.folder_id] = f;
    state.order.push(tag.folder_id);
    return f;
  }

  function addToFolder(tag, item) {
    var f = ensureFolder(tag);
    f.items.push(item);
    f.countEl.textContent = String(f.items.length);

    var row = document.createElement("button");
    row.type = "button";
    row.className = "folder-row";

    var label = document.createElement("span");
    label.className = "folder-row-name"; label.textContent = item.name;

    var flaw = document.createElement("span");
    flaw.className = "folder-row-flaw";
    var bits = [];
    if (tag.note) bits.push(tag.note);
    if (tag.extracted) bits.push("on label: " + tag.extracted);
    flaw.textContent = bits.join("  ·  ");

    row.appendChild(label); row.appendChild(flaw);
    row.addEventListener("click", function () { openDetail(item); });
    f.listEl.appendChild(row);
  }

  function handleItem(item) {
    state.done += 1;
    if (item.clean) {
      state.cleared += 1;           // clean items clear themselves; never a row
      updateSummary(false);
      return;
    }
    state.attention += 1;
    (item.folder_tags || []).forEach(function (tag) { addToFolder(tag, item); });
    updateSummary(false);
  }

  function finalSummary(s) {
    state.cleared = s.pass;
    state.attention = s.fail + s.needs_review;
    state.total = s.total;
    state.done = s.total;
    updateSummary(true);
  }

  function startStream(jobId, itemCount) {
    state.total = itemCount;
    var es = new EventSource("/batch/" + jobId + "/stream");
    es.addEventListener("item", function (ev) { handleItem(JSON.parse(ev.data)); });
    es.addEventListener("summary", function (ev) { finalSummary(JSON.parse(ev.data)); es.close(); });
    es.onerror = function () { es.close(); };
  }

  function submitBatch(formData) {
    reset();
    fetch("/batch", { method: "POST", body: formData })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { resultsSec.hidden = true; showError((res.j && res.j.error) || "Couldn't start the batch."); return; }
        if (res.j.pairing_errors && res.j.pairing_errors.length) {
          showError(res.j.pairing_errors.length + " item(s) couldn't be paired: "
            + res.j.pairing_errors.slice(0, 5).map(function (e) { return e.reference + " (" + e.problem + ")"; }).join(", "));
        }
        startStream(res.j.job_id, res.j.item_count);
      })
      .catch(function () { resultsSec.hidden = true; showError("Couldn't reach the server."); });
  }

  if (detailBack) detailBack.addEventListener("click", closeDetail);

  if (demoBtn) {
    demoBtn.addEventListener("click", function () {
      var fd = new FormData();
      fd.append("mode", "demo");
      submitBatch(fd);
    });
  }

  if (uploadForm) {
    uploadForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData();
      fd.append("mode", "upload");
      var csv = document.getElementById("csv-file");
      var imgs = document.getElementById("images-file");
      if (csv && csv.files[0]) fd.append("csv_file", csv.files[0]);
      if (imgs) { for (var i = 0; i < imgs.files.length; i++) fd.append("images", imgs.files[i]); }
      submitBatch(fd);
    });
  }
})();
