"use strict";

(function () {
  var fileInput = document.getElementById("label-file");
  var fileName = document.getElementById("file-name");
  var thumb = document.getElementById("thumb");
  var zone = document.getElementById("upload-zone");
  var form = document.getElementById("verify-form");
  var button = document.getElementById("verify-button");

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

  if (form && button) {
    form.addEventListener("submit", function () {
      button.disabled = true;
      button.textContent = "Checking… (about 5 seconds)";
    });
  }
})();
