"use strict";

(function () {
  var demoBtn = document.getElementById("demo-button");
  var uploadForm = document.getElementById("upload-form");
  var errorBox = document.getElementById("batch-error");
  var resultsSec = document.getElementById("batch-results");
  var summaryEl = document.getElementById("triage-summary");
  var reviewedEl = document.getElementById("triage-reviewed");
  var doneEl = document.getElementById("triage-done");
  var undoBtn = document.getElementById("undo-last");
  var foldersEl = document.getElementById("folders");
  var detailPanel = document.getElementById("detail-panel");
  var detailTitle = document.getElementById("detail-title");
  var detailTbody = document.getElementById("detail-tbody");
  var detailBack = document.getElementById("detail-back");
  var noteInput = document.getElementById("detail-note");

  // disposition -> human label for the reviewed tally
  var DISPOSITIONS = [
    { key: "approved", label: "Approve", cls: "act-approve" },
    { key: "rejected", label: "Reject", cls: "act-reject" },
    { key: "tool_error", label: "Tool was wrong", cls: "act-toolerr" },
  ];

  var state;

  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }

  function reset() {
    clearError();
    foldersEl.innerHTML = "";
    detailPanel.hidden = true;
    foldersEl.hidden = false;
    doneEl.hidden = true;
    reviewedEl.hidden = true;
    undoBtn.hidden = true;
    if (noteInput) noteInput.value = "";
    state = {
      total: 0, done: 0, cleared: 0, attention: 0, flaggedTotal: 0, seq: 0,
      folders: {}, order: [], items: {},
      reviewed: { approved: 0, rejected: 0, tool_error: 0 },
      lastAction: null, detailContext: null,
    };
    resultsSec.hidden = false;
    summaryEl.textContent = "Starting…";
  }

  function updateSummary(done) {
    var lead = done ? "Done" : (state.done + " of " + state.total + " checked");
    summaryEl.textContent = lead + "  —  ✓ " + state.cleared
      + " cleared automatically   ▲ " + state.attention + " need your attention";
  }

  function updateReviewed() {
    var r = state.reviewed;
    if (r.approved + r.rejected + r.tool_error > 0) {
      reviewedEl.hidden = false;
      reviewedEl.textContent = "Reviewed by you: " + r.approved + " approved · "
        + r.rejected + " rejected · " + r.tool_error + " tool errors";
    } else {
      reviewedEl.hidden = true;
    }
  }

  function checkCompletion() {
    if (state.flaggedTotal > 0 && state.attention === 0) {
      detailPanel.hidden = true;
      foldersEl.hidden = true;
      var r = state.reviewed;
      doneEl.hidden = false;
      doneEl.textContent = "All caught up — you reviewed "
        + (r.approved + r.rejected + r.tool_error) + " label(s): "
        + r.approved + " approved · " + r.rejected + " rejected · " + r.tool_error + " tool errors.";
    }
  }

  // --- Action buttons (shared by folder rows and the detail panel) ---
  function makeActionButtons(handler) {
    var wrap = document.createElement("div");
    wrap.className = "row-actions";
    DISPOSITIONS.forEach(function (d) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "act " + d.cls;
      b.textContent = d.label;
      b.addEventListener("click", function (ev) { ev.stopPropagation(); handler(d.key); });
      wrap.appendChild(b);
    });
    return wrap;
  }

  // --- Detail panel: full per-field readout + the three actions. ---
  function openDetail(id, folderId) {
    var entry = state.items[id];
    if (!entry) return;
    state.detailContext = { id: id, folderId: folderId };
    detailTitle.textContent = entry.item.name;
    detailTbody.innerHTML = "";
    (entry.item.fields || []).forEach(function (row) {
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
    if (noteInput) noteInput.value = "";
    foldersEl.hidden = true;
    doneEl.hidden = true;
    detailPanel.hidden = false;
  }

  function closeDetail() {
    state.detailContext = null;
    detailPanel.hidden = true;
    foldersEl.hidden = false;
  }

  // Acting in the detail panel resolves, then auto-advances to the next
  // unresolved item in the SAME folder (or back to the folder list).
  function detailAct(disposition) {
    var ctx = state.detailContext;
    if (!ctx) return;
    var note = disposition === "tool_error" && noteInput ? (noteInput.value || "").trim() : null;
    var folderId = ctx.folderId;
    resolve(ctx.id, disposition, note);
    var f = state.folders[folderId];
    if (f && f.ids.length > 0) {
      openDetail(f.ids[0], folderId);
    } else {
      closeDetail();
      checkCompletion();
    }
  }

  // --- Folders ---
  function setFolderCount(f) {
    if (f.ids.length === 0) {
      f.card.classList.add("cleared");
      f.countEl.textContent = "✓ All clear";
    } else {
      f.card.classList.remove("cleared");
      f.countEl.textContent = String(f.ids.length);
    }
  }

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

    f = { id: tag.folder_id, label: tag.folder_label, ids: [], countEl: count, listEl: list, card: card };
    state.folders[tag.folder_id] = f;
    state.order.push(tag.folder_id);
    return f;
  }

  function makeRow(id, tag) {
    var entry = state.items[id];
    var row = document.createElement("div");
    row.className = "folder-row";

    var open = document.createElement("button");
    open.type = "button";
    open.className = "folder-row-open";
    var label = document.createElement("span");
    label.className = "folder-row-name"; label.textContent = entry.item.name;
    var flaw = document.createElement("span");
    flaw.className = "folder-row-flaw";
    var bits = [];
    if (tag.note) bits.push(tag.note);
    if (tag.extracted) bits.push("on label: " + tag.extracted);
    flaw.textContent = bits.join("  ·  ");
    open.appendChild(label); open.appendChild(flaw);
    open.addEventListener("click", function () { openDetail(id, tag.folder_id); });

    // Fast rip-through: acting on a folder row resolves + clears (no advance).
    var actions = makeActionButtons(function (disposition) { resolve(id, disposition, null); });

    row.appendChild(open); row.appendChild(actions);
    return row;
  }

  function addToFolder(tag, id) {
    var f = ensureFolder(tag);
    f.ids.push(id);
    var row = makeRow(id, tag);
    state.items[id].rowEls[tag.folder_id] = row;
    f.listEl.appendChild(row);
    setFolderCount(f);
  }

  // --- Resolution (label-level, session-only, in memory) ---
  function resolve(id, disposition, note) {
    var entry = state.items[id];
    if (!entry || entry.disposition) return;   // already resolved
    entry.disposition = disposition;
    entry.note = note || "";
    state.reviewed[disposition] += 1;
    state.attention -= 1;

    // Remove this label from EVERY folder it was tagged in (one label, one disposition).
    Object.keys(entry.rowEls).forEach(function (fid) {
      var f = state.folders[fid];
      var idx = f.ids.indexOf(id);
      if (idx !== -1) f.ids.splice(idx, 1);
      var el = entry.rowEls[fid];
      if (el && el.parentNode) el.parentNode.removeChild(el);
      setFolderCount(f);
    });
    entry.rowEls = {};

    state.lastAction = { id: id, disposition: disposition };
    undoBtn.hidden = false;
    updateSummary(state.total > 0 && state.done >= state.total);
    updateReviewed();
    checkCompletion();
  }

  function undoLast() {
    var la = state.lastAction;
    if (!la) return;
    var entry = state.items[la.id];
    if (!entry || !entry.disposition) return;
    state.reviewed[entry.disposition] -= 1;
    entry.disposition = null;
    entry.note = "";
    state.attention += 1;
    entry.tags.forEach(function (tag) { addToFolder(tag, la.id); });
    state.lastAction = null;
    undoBtn.hidden = true;
    doneEl.hidden = true;
    foldersEl.hidden = false;
    updateSummary(state.total > 0 && state.done >= state.total);
    updateReviewed();
  }

  function handleItem(item) {
    state.done += 1;
    if (item.clean) {
      state.cleared += 1;           // clean items clear themselves; never a row
      updateSummary(false);
      return;
    }
    state.attention += 1;
    state.flaggedTotal += 1;
    var id = "L" + (++state.seq);
    state.items[id] = {
      item: item, disposition: null, note: "",
      tags: item.folder_tags || [], rowEls: {},
    };
    (item.folder_tags || []).forEach(function (tag) { addToFolder(tag, id); });
    doneEl.hidden = true;          // more work arrived; not caught up
    updateSummary(false);
  }

  function finalSummary(s) {
    state.cleared = s.pass;
    state.total = s.total;
    state.done = s.total;
    updateSummary(true);           // attention stays the live unresolved count
    checkCompletion();
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
  if (undoBtn) undoBtn.addEventListener("click", undoLast);
  // Detail-panel action buttons (approve / reject / tool-was-wrong).
  DISPOSITIONS.forEach(function (d) {
    var btn = document.getElementById("detail-" + d.key);
    if (btn) btn.addEventListener("click", function () { detailAct(d.key); });
  });

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
