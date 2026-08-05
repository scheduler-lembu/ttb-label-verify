/*
 * app.js — client-side upload + result rendering (scaffold only; no logic).
 *
 * Single responsibility: wire the one page. Later phases implement:
 *   - single: POST the image + form values to /verify, render the per-field
 *     results table (extracted vs expected vs verdict).
 *   - batch: POST the CSV + images to /batch and consume an SSE stream,
 *     APPENDING each result row as it arrives (progressive results, NFR-02),
 *     then show the final summary counts.
 *
 * No behavior in this pass — these are placeholder stubs so the page loads.
 */

"use strict";

// Enable the primary button once a file is chosen. (Wired in a later phase.)
function initUpload() {
  // TODO: attach file-input + drag/drop handlers; toggle #verify-button.
}

// Single-label: send to /verify and render results. (Later phase.)
function verifySingle() {
  // TODO: POST multipart to /verify; render FieldResult rows.
}

// Batch: open an SSE connection to /batch and append rows as they stream in.
function runBatchStream() {
  // TODO: EventSource('/batch'); on each message append a row; on end show summary.
}

// Render one field's result row into #results-table. (Later phase.)
function appendResultRow(/* fieldResult */) {
  // TODO: build a <tr> with expected / extracted / state-<STATE> cells.
}

document.addEventListener("DOMContentLoaded", initUpload);
