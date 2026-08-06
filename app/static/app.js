"use strict";

/*
 * Single-label page — progressive enhancement only (D-21). The <form> posts to
 * /verify and works with JS disabled; this script only adds conveniences:
 * drag-and-drop onto the upload zone, a client-side thumbnail preview, and a
 * "Checking…" button state on submit. No verification logic lives here — the
 * server does the extraction/adjudication and re-renders the results table.
 */
(function () {
  var fileInput = document.getElementById("label-file");
  var fileName = document.getElementById("file-name");
  var thumb = document.getElementById("thumb");
  var zone = document.getElementById("upload-zone");
  var form = document.getElementById("verify-form");
  var button = document.getElementById("verify-button");

  // Reflect the chosen/dropped file: show its name and, for images, a preview thumb.
  function showFile(file) {
    if (!file) return;
    if (fileName) fileName.textContent = file.name;
    if (thumb && file.type && file.type.indexOf("image/") === 0) {
      thumb.src = URL.createObjectURL(file);
      thumb.hidden = false;
    }
  }

  if (fileInput) {
    fileInput.addEventListener("change", function () {
      if (fileInput.files && fileInput.files[0]) showFile(fileInput.files[0]);
    });
  }

  if (zone) {
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("dragover"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("dragover"); });
    });
    zone.addEventListener("drop", function (e) {
      var files = e.dataTransfer && e.dataTransfer.files;
      if (files && files[0] && fileInput) { fileInput.files = files; showFile(files[0]); }
    });
  }

  // On submit, disable the single primary button and show progress so a slow verify
  // never looks frozen (NFR-06). The plain POST still proceeds and the server re-renders.
  if (form && button) {
    form.addEventListener("submit", function () {
      button.disabled = true;
      button.textContent = "Checking… (about 5 seconds)";
    });
  }
})();
