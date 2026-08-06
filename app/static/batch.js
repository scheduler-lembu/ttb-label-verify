"use strict";

/*
 * Batch triage — field-error buckets (#12 one-at-a-time review), record buckets
 * (#13a Approved/Cleared + Rejected, searchable) and (#13b) Re-ingest + a
 * navigable notification bell:
 *   - Re-ingest re-runs ONE label through the accurate single-label engine; the
 *     fresh result clears the app's prior disposition and re-buckets it.
 *   - Each re-ingest posts a notification to the header bell; its Navigate button
 *     walks the agent through the app's CURRENT buckets until it settles in a
 *     record bucket.
 * Session-only, in memory; a reload clears everything.
 */
(function () {
  var demoBtn = document.getElementById("demo-button");
  var uploadForm = document.getElementById("upload-form");
  var errorBox = document.getElementById("batch-error");
  var resultsSec = document.getElementById("batch-results");
  var summaryEl = document.getElementById("triage-summary");
  var reviewedEl = document.getElementById("triage-reviewed");
  var flashEl = document.getElementById("triage-flash");
  var doneEl = document.getElementById("triage-done");
  var bucketsEl = document.getElementById("buckets");
  var recordsSection = document.getElementById("records-section");
  var recordBucketsEl = document.getElementById("record-buckets");

  var reviewScreen = document.getElementById("review-screen");
  var reviewProgress = document.getElementById("review-progress");
  var reviewBanner = document.getElementById("review-banner");
  var reviewImg = document.getElementById("review-img");
  var reviewAppLabel = document.getElementById("review-app-label");
  var reviewAppValue = document.getElementById("review-app-value");
  var reviewWhy = document.getElementById("review-why");
  var reviewFullTbody = document.getElementById("review-fulltbody");
  var approveBtn = document.getElementById("review-approve");
  var rejectBtn = document.getElementById("review-reject");

  var listScreen = document.getElementById("list-screen");
  var listBack = document.getElementById("list-back");
  var listTitle = document.getElementById("list-title");
  var listSearch = document.getElementById("list-search");
  var recordListEl = document.getElementById("record-list");

  var notifBell = document.getElementById("notif-bell");
  var notifCount = document.getElementById("notif-count");
  var notifPanel = document.getElementById("notif-panel");
  var notifListEl = document.getElementById("notif-list");

  var BUCKET_LABELS = {
    brand: "Brand name", alcohol_content: "Alcohol content", warning: "Government warning",
    class_type: "Class / type", net_contents: "Net contents",
    producer: "Producer name & address", country_of_origin: "Country of origin",
    unreadable_label: "Couldn't read the label",
  };
  var BANNERS = {
    brand: "Check the brand name — does the label match the application?",
    alcohol_content: "Check the alcohol content (ABV / proof) against the application.",
    warning: "Check the Government Warning — it must match the official statement exactly, all-caps prefix included.",
    class_type: "Check the class / type against the application.",
    net_contents: "Check the net contents against the application.",
    producer: "Check the producer name & address against the application.",
    country_of_origin: "Check the country of origin against the application.",
    unreadable_label: "The tool couldn't read this label — review the image and decide.",
  };

  var state;
  var recordCards = { cleared: null, rejected: null };

  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }
  function bLabel(id) { return BUCKET_LABELS[id] || id; }
  function esc(v) { return (v === null || v === undefined || v === "") ? "—" : String(v); }

  function buildSearch(name, filename, fields) {
    var parts = [name || "", filename || ""];
    (fields || []).forEach(function (row) {
      parts.push(row.label || ""); parts.push(row.extracted || ""); parts.push(row.expected || "");
    });
    return parts.join("  ").toLowerCase();
  }

  function reset() {
    clearError();
    bucketsEl.innerHTML = "";
    recordBucketsEl.innerHTML = "";
    recordListEl.innerHTML = "";
    notifListEl.innerHTML = "";
    reviewScreen.hidden = true; listScreen.hidden = true;
    bucketsEl.hidden = false; recordsSection.hidden = false;
    doneEl.hidden = true; reviewedEl.hidden = true; flashEl.hidden = true;
    notifPanel.hidden = true;
    state = {
      jobId: null, total: 0, done: 0, clearedAuto: 0,
      attention: 0, flaggedTotal: 0,
      reviewedCleared: 0, rejected: 0, rejectedApps: [],
      buckets: {}, bucketOrder: [], apps: {},
      records: { cleared: [], rejected: [] },
      currentBucket: null, currentApp: null, reviewIndex: 0, reviewTotal: 0,
      currentList: null,
      notifications: [], notifUnread: 0,
    };
    recordCards.cleared = makeRecordCard("cleared", "Approved / Cleared", "i-check");
    recordCards.rejected = makeRecordCard("rejected", "Rejected", "i-x");
    updateBell();
    resultsSec.hidden = false;
    summaryEl.textContent = "Starting…";
  }

  function updateSummary(done) {
    var lead = done ? "Done" : (state.done + " of " + state.total + " checked");
    summaryEl.textContent = lead + "  —  ✓ " + state.clearedAuto
      + " cleared automatically   ▲ " + state.attention + " need your attention";
  }
  function updateReviewed() {
    if (state.reviewedCleared + state.rejected > 0) {
      reviewedEl.hidden = false;
      reviewedEl.textContent = "Reviewed by you: " + state.reviewedCleared + " cleared · " + state.rejected + " rejected";
    } else { reviewedEl.hidden = true; }
  }
  function flash(msg) { flashEl.hidden = false; flashEl.textContent = msg; }
  function clearFlash() { flashEl.hidden = true; flashEl.textContent = ""; }

  function showOverview() {
    clearFlash();
    reviewScreen.hidden = true; listScreen.hidden = true;
    bucketsEl.hidden = false; recordsSection.hidden = false;
    checkCompletion();
  }
  function checkCompletion() {
    if (state.flaggedTotal > 0 && state.attention === 0) {
      reviewScreen.hidden = true; listScreen.hidden = true;
      bucketsEl.hidden = true; recordsSection.hidden = false;
      doneEl.hidden = false;
      doneEl.textContent = "All caught up — reviewed " + state.flaggedTotal + " application(s): "
        + state.reviewedCleared + " cleared by you, " + state.rejected + " rejected.";
    }
  }

  // --- Field-error buckets ---
  function ensureBucket(tag) {
    var b = state.buckets[tag.bucket_id];
    if (b) return b;
    var card = document.createElement("button");
    card.type = "button"; card.className = "bucket-card";
    var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "icon");
    icon.innerHTML = '<use href="#' + (tag.bucket_id === "unreadable_label" ? "i-warn" : "i-bucket") + '"/>';
    var name = document.createElement("span"); name.className = "bucket-name"; name.textContent = bLabel(tag.bucket_id);
    var count = document.createElement("span"); count.className = "bucket-count"; count.textContent = "0";
    card.appendChild(icon); card.appendChild(name); card.appendChild(count);
    card.addEventListener("click", function () { openBucket(tag.bucket_id); });
    bucketsEl.appendChild(card);
    b = { id: tag.bucket_id, appIds: [], card: card, countEl: count };
    state.buckets[tag.bucket_id] = b; state.bucketOrder.push(tag.bucket_id);
    return b;
  }
  function setBucketCount(b) { b.countEl.textContent = String(b.appIds.length); b.card.hidden = b.appIds.length === 0; }
  function removeAppFromBucket(app, bucketId) {
    var b = state.buckets[bucketId]; if (!b) return;
    var idx = b.appIds.indexOf(app.filename); if (idx !== -1) b.appIds.splice(idx, 1);
    app.active.delete(bucketId); setBucketCount(b);
  }
  function tagFor(app, field) {
    for (var i = 0; i < app.tags.length; i++) { if (app.tags[i].bucket_id === field) return app.tags[i]; }
    return null;
  }
  function addToFieldBuckets(app) {
    app.tags.forEach(function (tag) {
      var b = ensureBucket(tag);
      if (b.appIds.indexOf(app.filename) === -1) { b.appIds.push(app.filename); app.active.add(tag.bucket_id); setBucketCount(b); }
    });
  }

  // --- Record buckets ---
  function makeRecordCard(type, label, iconId) {
    var card = document.createElement("button");
    card.type = "button"; card.className = "bucket-card record-card record-" + type;
    var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "icon"); icon.innerHTML = '<use href="#' + iconId + '"/>';
    var name = document.createElement("span"); name.className = "bucket-name"; name.textContent = label;
    var count = document.createElement("span"); count.className = "bucket-count"; count.textContent = "0";
    card.appendChild(icon); card.appendChild(name); card.appendChild(count);
    card.addEventListener("click", function () { openList(type); });
    recordBucketsEl.appendChild(card);
    return { countEl: count };
  }
  function updateRecordCounts() {
    recordCards.cleared.countEl.textContent = String(state.records.cleared.length);
    recordCards.rejected.countEl.textContent = String(state.records.rejected.length);
  }
  function routeToRecord(app, type, badge) {
    app.record = type; if (badge) app.recordBadge = badge;
    state.records[type].unshift(app.filename);   // most-recently-touched first
    updateRecordCounts();
  }
  function removeFromRecord(app) {
    if (!app.record) return;
    var arr = state.records[app.record]; var i = arr.indexOf(app.filename);
    if (i !== -1) arr.splice(i, 1);
    app.record = null; app.recordBadge = null; updateRecordCounts();
  }

  function makeApp(item) {
    var tags = item.bucket_tags || [];
    return {
      filename: item.image_filename, name: item.name, item: item, tags: tags,
      flaggedFields: tags.map(function (t) { return t.bucket_id; }),
      active: new Set(), approved: {}, status: "pending", rejectionInfo: null,
      record: null, recordBadge: null,
      searchText: buildSearch(item.name, item.image_filename, item.fields),
    };
  }

  // --- Review screen ---
  function whyText(tag) {
    var x = esc(tag.extracted), e = esc(tag.expected);
    switch (tag.reason) {
      case "mismatch": return "The tool read '" + x + "', but the application says '" + e + "'.";
      case "borderline": return "The tool read '" + x + "' — close to '" + e + "', not a confident match.";
      case "blank_expected": return "No alcohol content was entered and none was read — confirm it's legitimately absent.";
      case "special_character": return "'" + x + "' has special characters — needs a human check against '" + e + "'.";
      case "warning_wording": return "The warning wording differs from the official statement.";
      case "warning_prefix_not_allcaps": return "The 'GOVERNMENT WARNING' prefix isn't in all caps.";
      case "warning_prefix_missing": return "The 'GOVERNMENT WARNING' prefix is missing.";
      case "unreadable": return "The tool couldn't read this field.";
      case "unexpected_value": return "The label shows a value here, but the application expected none.";
      default: return tag.note || "This field needs a review.";
    }
  }
  function renderFullDetails(app) {
    reviewFullTbody.innerHTML = "";
    (app.item.fields || []).forEach(function (row) {
      var tr = document.createElement("tr");
      var f = document.createElement("td"); f.className = "cell-field"; f.textContent = row.label;
      var xx = document.createElement("td"); xx.className = "cell-val"; xx.textContent = row.extracted;
      var ee = document.createElement("td"); ee.className = "cell-val"; ee.textContent = row.expected;
      var rr = document.createElement("td"); rr.className = "cell-result";
      var badge = document.createElement("span"); badge.className = "badge badge-" + row.verdict; badge.textContent = row.verdict_label;
      rr.appendChild(badge);
      if (row.reason) { var d = document.createElement("div"); d.className = "reason"; d.textContent = row.reason; rr.appendChild(d); }
      tr.appendChild(f); tr.appendChild(xx); tr.appendChild(ee); tr.appendChild(rr);
      reviewFullTbody.appendChild(tr);
    });
  }
  function renderReview(appId, bucketId) {
    var app = state.apps[appId]; var tag = tagFor(app, bucketId);
    state.currentApp = appId;
    reviewProgress.textContent = "Label " + state.reviewIndex + " of " + state.reviewTotal + " in this bucket";
    reviewBanner.textContent = BANNERS[bucketId] || ("Check the " + bLabel(bucketId) + " against the application.");
    reviewImg.src = "/batch/" + state.jobId + "/image/" + encodeURIComponent(app.filename);
    reviewImg.alt = "Submitted label: " + app.name;
    if (bucketId === "warning") reviewAppLabel.textContent = "Official Government Warning (must match exactly)";
    else if (bucketId === "unreadable_label") reviewAppLabel.textContent = "The tool couldn't read the label";
    else reviewAppLabel.textContent = "What the application says";
    reviewAppValue.textContent = (tag && tag.expected) ? tag.expected
      : (bucketId === "unreadable_label" ? "Review the image and decide." : "— (blank) —");
    reviewWhy.textContent = tag ? whyText(tag) : "";
    renderFullDetails(app);
    bucketsEl.hidden = true; recordsSection.hidden = true; listScreen.hidden = true; doneEl.hidden = true;
    reviewScreen.hidden = false;
  }
  // openBucket can start on a specific app (Navigate) or at the first (normal).
  function openBucket(bucketId, startFilename) {
    var b = state.buckets[bucketId];
    if (!b || b.appIds.length === 0) return;
    clearFlash();
    state.currentBucket = bucketId; state.reviewTotal = b.appIds.length;
    var idx = startFilename ? b.appIds.indexOf(startFilename) : 0;
    if (idx < 0) idx = 0;
    state.reviewIndex = idx + 1;
    renderReview(b.appIds[idx], bucketId);
  }
  function advance() {
    var b = state.buckets[state.currentBucket];
    if (b && b.appIds.length > 0) { state.reviewIndex += 1; renderReview(b.appIds[0], state.currentBucket); }
    else { showOverview(); flash("This bucket is clear."); }
  }
  function approve() {
    var app = state.apps[state.currentApp]; var F = state.currentBucket;
    if (!app || app.status === "rejected" || app.approved[F]) return;
    app.approved[F] = true; removeAppFromBucket(app, F);
    if (app.active.size === 0) {
      state.reviewedCleared += 1; state.attention -= 1; app.status = "approved";
      routeToRecord(app, "cleared", "Approved by you");
    }
    updateReviewed(); updateSummary(true); advance();
  }
  function reject() {
    var app = state.apps[state.currentApp]; var F = state.currentBucket;
    if (!app || app.status === "rejected") return;
    app.status = "rejected";
    var pleaseCheck = app.flaggedFields.map(function (f) { var t = tagFor(app, f); return { field: f, reason: t ? t.reason : "" }; });
    app.rejectionInfo = { rejectedField: F, reason: (tagFor(app, F) || {}).reason, pleaseCheck: pleaseCheck };
    Array.from(app.active).forEach(function (b) { removeAppFromBucket(app, b); });
    state.attention -= 1; state.rejected += 1;
    state.rejectedApps.push({ name: app.name, pleaseCheck: pleaseCheck });
    routeToRecord(app, "rejected", "Rejected");
    flash("Rejected for: " + bLabel(F) + ". Please check: " + pleaseCheck.map(function (p) { return bLabel(p.field); }).join(", ") + ".");
    updateReviewed(); updateSummary(true); advance();
  }

  // --- Record list view (searchable; Re-ingest per row) ---
  function makeListRow(app, highlight) {
    var row = document.createElement("div");
    row.className = "record-row" + (app.filename === highlight ? " highlight" : "");
    var top = document.createElement("div"); top.className = "record-row-top";
    var name = document.createElement("span"); name.className = "record-row-name"; name.textContent = app.name || app.filename;
    top.appendChild(name);
    if (app.record === "rejected") {
      var rj = app.rejectionInfo || { rejectedField: "", pleaseCheck: [] };
      var badge = document.createElement("span"); badge.className = "badge badge-FAIL"; badge.textContent = "Rejected for: " + bLabel(rj.rejectedField);
      top.appendChild(badge);
    } else {
      var b2 = document.createElement("span"); b2.className = "badge badge-PASS"; b2.textContent = app.recordBadge || "Cleared";
      top.appendChild(b2);
    }
    var reingest = document.createElement("button");
    reingest.type = "button"; reingest.className = "btn btn--secondary btn-sm reingest-btn";
    reingest.textContent = "Re-ingest";
    reingest.addEventListener("click", function () { reverify(app, reingest); });
    top.appendChild(reingest);
    row.appendChild(top);
    if (app.record === "rejected") {
      var note = document.createElement("div"); note.className = "record-row-note";
      note.textContent = "Please check: " + (app.rejectionInfo.pleaseCheck || []).map(function (p) { return bLabel(p.field); }).join(", ");
      row.appendChild(note);
    }
    return row;
  }
  function renderList(type, query, highlight) {
    recordListEl.innerHTML = "";
    var q = (query || "").trim().toLowerCase();
    var ids = state.records[type]; var shown = 0;
    ids.forEach(function (id) {
      var app = state.apps[id]; if (!app) return;
      if (q && app.searchText.indexOf(q) === -1) return;
      recordListEl.appendChild(makeListRow(app, highlight)); shown += 1;
    });
    if (shown === 0) {
      var empty = document.createElement("p"); empty.className = "record-empty";
      empty.textContent = ids.length === 0 ? "Nothing here yet." : "No matches for “" + query + "”.";
      recordListEl.appendChild(empty);
    }
  }
  function openList(type, highlight) {
    clearFlash();
    state.currentList = type;
    listTitle.textContent = type === "cleared" ? "Approved / Cleared" : "Rejected";
    listSearch.value = "";
    renderList(type, "", highlight);
    bucketsEl.hidden = true; recordsSection.hidden = true; reviewScreen.hidden = true; doneEl.hidden = true;
    listScreen.hidden = false;
  }

  // --- Re-ingest (fresh single-label read) ---
  function reverify(app, btn) {
    var original = btn.textContent;
    btn.disabled = true; btn.textContent = "Re-checking…";
    fetch("/batch/" + state.jobId + "/reverify/" + encodeURIComponent(app.filename), { method: "POST" })
      .then(function (r) { if (!r.ok) throw new Error("bad"); return r.json(); })
      .then(function (resp) { applyReingest(app, resp); })
      .catch(function () {
        btn.disabled = false; btn.textContent = original;
        var msg = btn.parentNode.querySelector(".reingest-error");
        if (!msg) { msg = document.createElement("span"); msg.className = "reingest-error"; btn.parentNode.appendChild(msg); }
        msg.textContent = "couldn't re-check — try again";
      });
  }
  function applyReingest(app, resp) {
    removeFromRecord(app);                                  // clear its record-bucket membership
    Array.from(app.active).forEach(function (b) { removeAppFromBucket(app, b); });
    app.active = new Set(); app.approved = {}; app.rejectionInfo = null; app.status = "pending";
    app.item.fields = resp.fields || [];
    app.tags = resp.bucket_tags || [];
    app.flaggedFields = app.tags.map(function (t) { return t.bucket_id; });
    app.searchText = buildSearch(app.name, app.filename, app.item.fields);

    if (resp.clean || !app.tags.length) {
      app.status = "clean";
      routeToRecord(app, "cleared", "Auto-cleared");
    } else {
      addToFieldBuckets(app);
      state.attention += 1; state.flaggedTotal += 1;
      doneEl.hidden = true;
    }
    updateRecordCounts(); updateSummary(true); updateReviewed();
    postNotification(app, resp);
    if (!listScreen.hidden && state.currentList) renderList(state.currentList, listSearch.value);
    checkCompletion();
  }

  // --- Notifications + bell ---
  function updateBell() {
    if (state.notifUnread > 0) { notifCount.hidden = false; notifCount.textContent = String(state.notifUnread); }
    else { notifCount.hidden = true; }
  }
  function postNotification(app, resp) {
    var brand = app.name || app.filename; var text;
    if (resp.clean || !app.tags.length) text = brand + " — re-checked: cleared.";
    else if (app.tags.length === 1) text = brand + " — re-checked: needs review on " + bLabel(app.tags[0].bucket_id) + ".";
    else text = brand + " — re-checked: needs review on " + app.tags.length + " fields.";
    state.notifications.unshift({ filename: app.filename, text: text, cycleVisited: new Set() });
    state.notifUnread += 1; updateBell();
    if (!notifPanel.hidden) renderNotifPanel();
  }
  function renderNotifPanel() {
    notifListEl.innerHTML = "";
    if (!state.notifications.length) {
      var empty = document.createElement("p"); empty.className = "record-empty"; empty.textContent = "No re-ingest results yet.";
      notifListEl.appendChild(empty); return;
    }
    state.notifications.forEach(function (n) {
      var row = document.createElement("div"); row.className = "notif-row";
      var txt = document.createElement("span"); txt.className = "notif-text"; txt.textContent = n.text;
      var nav = document.createElement("button"); nav.type = "button"; nav.className = "btn btn--primary btn-sm";
      nav.textContent = "Navigate";
      nav.addEventListener("click", function () { navigate(n); });
      row.appendChild(txt); row.appendChild(nav);
      notifListEl.appendChild(row);
    });
  }
  function toggleNotifPanel() {
    if (notifPanel.hidden) {
      state.notifUnread = 0; updateBell();
      renderNotifPanel(); notifPanel.hidden = false;
    } else { notifPanel.hidden = true; }
  }
  function closeNotifPanel() { notifPanel.hidden = true; }

  // Navigate cycling: recompute the app's CURRENT buckets on each click.
  function navigate(notif) {
    var app = state.apps[notif.filename]; if (!app) return;
    var current = Array.from(app.active);
    if (current.length) {
      var next = current.filter(function (b) { return !notif.cycleVisited.has(b); });
      if (!next.length) { notif.cycleVisited.clear(); next = current; }
      var target = next[0]; notif.cycleVisited.add(target);
      closeNotifPanel();
      openBucket(target, app.filename);   // open that bucket ON this app
    } else if (app.record) {
      closeNotifPanel();
      openList(app.record, app.filename);  // settled -> terminal record bucket, highlighted
    }
  }

  // --- Streaming ---
  function handleItem(item) {
    state.done += 1;
    var app = state.apps[item.image_filename] || makeApp(item);
    var isNew = !state.apps[item.image_filename];
    if (isNew) state.apps[item.image_filename] = app;
    if (item.clean || !(item.bucket_tags || []).length) {
      if (isNew && item.clean) { state.clearedAuto += 1; app.status = "clean"; routeToRecord(app, "cleared", "Auto-cleared"); }
      updateSummary(false); return;
    }
    if (isNew) { state.attention += 1; state.flaggedTotal += 1; }
    addToFieldBuckets(app);
    doneEl.hidden = true; updateSummary(false);
  }
  function finalSummary(s) {
    state.clearedAuto = s.pass; state.total = s.total; state.done = s.total;
    updateSummary(true); checkCompletion();
  }
  function startStream(jobId, itemCount) {
    state.jobId = jobId; state.total = itemCount;
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

  document.getElementById("review-back").addEventListener("click", showOverview);
  if (approveBtn) approveBtn.addEventListener("click", approve);
  if (rejectBtn) rejectBtn.addEventListener("click", reject);
  if (listBack) listBack.addEventListener("click", showOverview);
  if (listSearch) listSearch.addEventListener("input", function () { renderList(state.currentList, this.value); });
  if (notifBell) notifBell.addEventListener("click", toggleNotifPanel);

  if (demoBtn) {
    demoBtn.addEventListener("click", function () { var fd = new FormData(); fd.append("mode", "demo"); submitBatch(fd); });
  }
  if (uploadForm) {
    uploadForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData(); fd.append("mode", "upload");
      var csv = document.getElementById("csv-file");
      var imgs = document.getElementById("images-file");
      if (csv && csv.files[0]) fd.append("csv_file", csv.files[0]);
      if (imgs) { for (var i = 0; i < imgs.files.length; i++) fd.append("images", imgs.files[i]); }
      submitBatch(fd);
    });
  }
})();
