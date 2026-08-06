"use strict";

/*
 * Batch triage — per-FIELD buckets + a focused, one-label-at-a-time review screen.
 *   - Buckets: one per field that needs a human; a closed card shows only name + count.
 *   - Review screen: banner -> photo -> what the application says -> why flagged ->
 *     Approve / Reject, advancing until the bucket empties.
 *   - Approve is PER-FIELD (clears the label from THIS bucket only).
 *   - Reject is WHOLE-APPLICATION (pulls the label from EVERY bucket + records a rollup).
 * All disposition is client-side, in-memory, session-only (no persistence, no network).
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

  var reviewScreen = document.getElementById("review-screen");
  var reviewBack = document.getElementById("review-back");
  var reviewProgress = document.getElementById("review-progress");
  var reviewBanner = document.getElementById("review-banner");
  var reviewImg = document.getElementById("review-img");
  var reviewAppLabel = document.getElementById("review-app-label");
  var reviewAppValue = document.getElementById("review-app-value");
  var reviewWhy = document.getElementById("review-why");
  var reviewFullTbody = document.getElementById("review-fulltbody");
  var approveBtn = document.getElementById("review-approve");
  var rejectBtn = document.getElementById("review-reject");

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

  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }

  function reset() {
    clearError();
    bucketsEl.innerHTML = "";
    reviewScreen.hidden = true;
    bucketsEl.hidden = false;
    doneEl.hidden = true;
    reviewedEl.hidden = true;
    flashEl.hidden = true;
    state = {
      jobId: null, total: 0, done: 0, clearedAuto: 0,
      attention: 0, flaggedTotal: 0,
      reviewedCleared: 0, rejected: 0, rejectedApps: [],
      buckets: {}, bucketOrder: [], apps: {},
      currentBucket: null, currentApp: null, reviewIndex: 0, reviewTotal: 0,
    };
    resultsSec.hidden = false;
    summaryEl.textContent = "Starting…";
  }

  function bLabel(id) { return BUCKET_LABELS[id] || id; }

  function esc(v) { return (v === null || v === undefined || v === "") ? "—" : String(v); }

  function updateSummary(done) {
    var lead = done ? "Done" : (state.done + " of " + state.total + " checked");
    summaryEl.textContent = lead + "  —  ✓ " + state.clearedAuto
      + " cleared automatically   ▲ " + state.attention + " need your attention";
  }

  function updateReviewed() {
    if (state.reviewedCleared + state.rejected > 0) {
      reviewedEl.hidden = false;
      reviewedEl.textContent = "Reviewed by you: " + state.reviewedCleared
        + " cleared · " + state.rejected + " rejected";
    } else {
      reviewedEl.hidden = true;
    }
  }

  function flash(msg) { flashEl.hidden = false; flashEl.textContent = msg; }
  function clearFlash() { flashEl.hidden = true; flashEl.textContent = ""; }

  function checkCompletion() {
    if (state.flaggedTotal > 0 && state.attention === 0) {
      reviewScreen.hidden = true;
      bucketsEl.hidden = true;
      var txt = "All caught up — reviewed " + state.flaggedTotal + " application(s): "
        + state.reviewedCleared + " cleared by you, " + state.rejected + " rejected.";
      if (state.rejectedApps.length) {
        txt += "  Rejected: " + state.rejectedApps.map(function (r) {
          return r.name + " (please check: " + r.pleaseCheck.map(function (p) { return bLabel(p.field); }).join(", ") + ")";
        }).join("; ") + ".";
      }
      doneEl.hidden = false;
      doneEl.textContent = txt;
    }
  }

  // --- Buckets ---
  function ensureBucket(tag) {
    var b = state.buckets[tag.bucket_id];
    if (b) return b;
    var card = document.createElement("button");
    card.type = "button";
    card.className = "bucket-card";
    var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "icon");
    icon.innerHTML = '<use href="#' + (tag.bucket_id === "unreadable_label" ? "i-warn" : "i-bucket") + '"/>';
    var name = document.createElement("span");
    name.className = "bucket-name"; name.textContent = bLabel(tag.bucket_id);
    var count = document.createElement("span");
    count.className = "bucket-count"; count.textContent = "0";
    card.appendChild(icon); card.appendChild(name); card.appendChild(count);
    card.addEventListener("click", function () { openBucket(tag.bucket_id); });
    bucketsEl.appendChild(card);
    b = { id: tag.bucket_id, appIds: [], card: card, countEl: count };
    state.buckets[tag.bucket_id] = b;
    state.bucketOrder.push(tag.bucket_id);
    return b;
  }

  function setBucketCount(b) {
    b.countEl.textContent = String(b.appIds.length);
    b.card.hidden = b.appIds.length === 0;   // only non-empty buckets show
  }

  function removeAppFromBucket(app, bucketId) {
    var b = state.buckets[bucketId];
    if (!b) return;
    var idx = b.appIds.indexOf(app.filename);
    if (idx !== -1) b.appIds.splice(idx, 1);
    app.active.delete(bucketId);
    setBucketCount(b);
  }

  function tagFor(app, field) {
    for (var i = 0; i < app.tags.length; i++) { if (app.tags[i].bucket_id === field) return app.tags[i]; }
    return null;
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
      var badge = document.createElement("span");
      badge.className = "badge badge-" + row.verdict; badge.textContent = row.verdict_label;
      rr.appendChild(badge);
      if (row.reason) { var d = document.createElement("div"); d.className = "reason"; d.textContent = row.reason; rr.appendChild(d); }
      tr.appendChild(f); tr.appendChild(xx); tr.appendChild(ee); tr.appendChild(rr);
      reviewFullTbody.appendChild(tr);
    });
  }

  function renderReview(appId, bucketId) {
    var app = state.apps[appId];
    var tag = tagFor(app, bucketId);
    state.currentApp = appId;
    reviewProgress.textContent = "Label " + state.reviewIndex + " of " + state.reviewTotal + " in this bucket";
    reviewBanner.textContent = BANNERS[bucketId] || ("Check the " + bLabel(bucketId) + " against the application.");
    reviewImg.src = "/batch/" + state.jobId + "/image/" + encodeURIComponent(app.filename);
    reviewImg.alt = "Submitted label: " + app.name;

    if (bucketId === "warning") {
      reviewAppLabel.textContent = "Official Government Warning (must match exactly)";
    } else if (bucketId === "unreadable_label") {
      reviewAppLabel.textContent = "The tool couldn't read the label";
    } else {
      reviewAppLabel.textContent = "What the application says";
    }
    reviewAppValue.textContent = (tag && tag.expected) ? tag.expected
      : (bucketId === "unreadable_label" ? "Review the image and decide." : "— (blank) —");
    reviewWhy.textContent = tag ? whyText(tag) : "";

    renderFullDetails(app);
    bucketsEl.hidden = true;
    doneEl.hidden = true;
    reviewScreen.hidden = false;
  }

  function openBucket(bucketId) {
    var b = state.buckets[bucketId];
    if (!b || b.appIds.length === 0) return;
    clearFlash();
    state.currentBucket = bucketId;
    state.reviewTotal = b.appIds.length;
    state.reviewIndex = 1;
    renderReview(b.appIds[0], bucketId);
  }

  function backToBuckets() {
    state.currentBucket = null; state.currentApp = null;
    reviewScreen.hidden = true;
    bucketsEl.hidden = false;
  }

  function advance() {
    var b = state.buckets[state.currentBucket];
    if (b && b.appIds.length > 0) {
      state.reviewIndex += 1;
      renderReview(b.appIds[0], state.currentBucket);
    } else {
      flash("This bucket is clear.");
      backToBuckets();
      checkCompletion();
    }
  }

  function approve() {
    var app = state.apps[state.currentApp];
    var F = state.currentBucket;
    if (!app || app.status === "rejected" || app.approved[F]) return;
    app.approved[F] = true;
    removeAppFromBucket(app, F);              // leaves THIS bucket only
    if (app.active.size === 0) {              // every flagged field approved -> fully cleared
      state.reviewedCleared += 1;
      state.attention -= 1;
    }
    updateReviewed(); updateSummary(true);
    advance();
  }

  function reject() {
    var app = state.apps[state.currentApp];
    var F = state.currentBucket;
    if (!app || app.status === "rejected") return;
    app.status = "rejected";
    var pleaseCheck = app.flaggedFields.map(function (f) {
      var t = tagFor(app, f); return { field: f, reason: t ? t.reason : "" };
    });
    app.rejectionInfo = { rejectedField: F, reason: (tagFor(app, F) || {}).reason, pleaseCheck: pleaseCheck };
    Array.from(app.active).forEach(function (b) { removeAppFromBucket(app, b); });  // leaves ALL buckets
    state.attention -= 1;
    state.rejected += 1;
    state.rejectedApps.push({ name: app.name, pleaseCheck: pleaseCheck });
    flash("Rejected for: " + bLabel(F) + ". Please check: "
      + pleaseCheck.map(function (p) { return bLabel(p.field); }).join(", ") + ".");
    updateReviewed(); updateSummary(true);
    advance();
  }

  // --- Streaming ---
  function handleItem(item) {
    state.done += 1;
    if (item.clean) { state.clearedAuto += 1; updateSummary(false); return; }
    var tags = item.bucket_tags || [];
    if (!tags.length) { updateSummary(false); return; }
    var appId = item.image_filename;
    var app = state.apps[appId];
    if (!app) {
      app = {
        filename: appId, name: item.name, item: item, tags: tags,
        flaggedFields: tags.map(function (t) { return t.bucket_id; }),
        active: new Set(), approved: {}, status: "pending", rejectionInfo: null,
      };
      state.apps[appId] = app;
      state.attention += 1;
      state.flaggedTotal += 1;
    }
    tags.forEach(function (tag) {
      var b = ensureBucket(tag);
      if (b.appIds.indexOf(appId) === -1) { b.appIds.push(appId); app.active.add(tag.bucket_id); setBucketCount(b); }
    });
    doneEl.hidden = true;
    updateSummary(false);
  }

  function finalSummary(s) {
    state.clearedAuto = s.pass;
    state.total = s.total; state.done = s.total;
    updateSummary(true);
    checkCompletion();
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

  if (reviewBack) reviewBack.addEventListener("click", function () { clearFlash(); backToBuckets(); });
  if (approveBtn) approveBtn.addEventListener("click", approve);
  if (rejectBtn) rejectBtn.addEventListener("click", reject);

  if (demoBtn) {
    demoBtn.addEventListener("click", function () {
      var fd = new FormData(); fd.append("mode", "demo"); submitBatch(fd);
    });
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
