// Voice answers: record in the browser (or fall back to the file input) and confirm before submitting.
(function () {
  var form = document.querySelector(".ex-form");
  if (!form) return;
  form.addEventListener("submit", function (e) {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  });

  var canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  document.querySelectorAll(".ex-voice").forEach(function (box) {
    var btn = box.querySelector(".ex-rec-btn"), preview = box.querySelector(".ex-preview");
    var input = box.querySelector("input[type=file]");
    if (!canRecord) { btn.hidden = true; box.querySelector(".ex-nomic").hidden = false; return; }
    var recorder = null, chunks = [];
    btn.addEventListener("click", function () {
      if (recorder && recorder.state === "recording") { recorder.stop(); return; }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        chunks = [];
        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = function (ev) { if (ev.data.size) chunks.push(ev.data); };
        recorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          var type = recorder.mimeType || "audio/webm";
          var ext = type.indexOf("mp4") > -1 ? "m4a" : type.indexOf("ogg") > -1 ? "ogg" : "webm";
          var file = new File(chunks, "answer." + ext, { type: type });
          var transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files;
          preview.src = URL.createObjectURL(file); preview.hidden = false;
          btn.textContent = form.dataset.rerecord;
        };
        recorder.start();
        btn.textContent = form.dataset.stop;
      }).catch(function () { btn.hidden = true; box.querySelector(".ex-nomic").hidden = false; });
    });
  });
})();
