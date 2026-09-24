document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('question-form');
  if (!form) return;

  var MAX_OPTIONS = parseInt(form.dataset.maxOptions, 10);
  var MIN_OPTIONS = parseInt(form.dataset.minOptions, 10);
  var AUDIO_MAX_BYTES = parseInt(form.dataset.audioMaxMb, 10) * 1024 * 1024;

  // --- Question type: show only the sections that belong to it ----------------
  var kindRadios = form.querySelectorAll('input[name="kind"]');
  var stepNum = form.querySelector('.qf-step-num');

  function currentKind() {
    var checked = form.querySelector('input[name="kind"]:checked');
    return checked ? checked.value : 'standard';
  }

  function applyKind() {
    var kind = currentKind();
    form.querySelectorAll('[data-kind]').forEach(function (section) {
      section.hidden = section.dataset.kind !== kind;
    });
    kindRadios.forEach(function (r) { r.closest('.qf-kind').classList.toggle('selected', r.checked); });
    if (stepNum) stepNum.textContent = kind === 'standard' ? '2' : '3';
  }
  kindRadios.forEach(function (r) { r.addEventListener('change', applyKind); });
  applyKind();

  // --- Optional English translation --------------------------------------------
  var toggleEn = document.getElementById('toggle-en');
  var hasEnglish = Array.prototype.some.call(form.querySelectorAll('.qf-en input, .qf-en textarea, input.qf-en'), function (el) {
    return el.value.trim() !== '';
  }) || form.querySelector('.qf-en .errorlist');
  toggleEn.checked = !!hasEnglish;
  function applyEnglish() { form.classList.toggle('show-en', toggleEn.checked); }
  toggleEn.addEventListener('change', applyEnglish);
  applyEnglish();

  // --- Options: add / remove rows, keep the "correct" radio indexes in sync ---
  var optionsBox = document.getElementById('options');
  var addBtn = document.getElementById('add-option');

  function rows() { return optionsBox.querySelectorAll('.qf-option'); }

  function renumber() {
    var list = rows();
    list.forEach(function (row, i) {
      row.querySelector('input[type="radio"]').value = i;
      row.querySelector('input[name="option_ar"]').placeholder = 'الاختيار ' + (i + 1);
      row.querySelector('input[name="option_en"]').placeholder = 'Option ' + (i + 1) + ' (English)';
      row.querySelector('.qf-option-remove').disabled = list.length <= MIN_OPTIONS;
    });
    addBtn.hidden = list.length >= MAX_OPTIONS;
    if (!optionsBox.querySelector('input[type="radio"]:checked') && list.length) {
      list[0].querySelector('input[type="radio"]').checked = true;
    }
    list.forEach(function (row) {
      row.classList.toggle('is-correct', row.querySelector('input[type="radio"]').checked);
    });
  }

  addBtn.addEventListener('click', function () {
    if (rows().length >= MAX_OPTIONS) return;
    var row = rows()[0].cloneNode(true);
    row.querySelectorAll('input[type="text"]').forEach(function (el) { el.value = ''; });
    row.querySelector('input[type="radio"]').checked = false;
    optionsBox.appendChild(row);
    renumber();
    row.querySelector('input[name="option_ar"]').focus();
  });

  optionsBox.addEventListener('click', function (e) {
    var btn = e.target.closest('.qf-option-remove');
    if (!btn || rows().length <= MIN_OPTIONS) return;
    btn.closest('.qf-option').remove();
    renumber();
  });
  optionsBox.addEventListener('change', renumber);

  // Enter in an option jumps to the next one (or adds a row) instead of submitting.
  optionsBox.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' || e.target.name !== 'option_ar') return;
    e.preventDefault();
    var list = Array.prototype.slice.call(rows());
    var idx = list.indexOf(e.target.closest('.qf-option'));
    if (idx < list.length - 1) list[idx + 1].querySelector('input[name="option_ar"]').focus();
    else addBtn.click();
  });
  renumber();

  // --- Audio: upload, drag & drop, microphone recording -----------------------
  var fileInput = form.querySelector('input[type="file"][name="audio_file"]');
  var drop = document.getElementById('audio-drop');
  var preview = document.getElementById('audio-preview');
  var previewName = document.getElementById('audio-preview-name');
  var previewPlayer = document.getElementById('audio-preview-player');
  var clearBtn = document.getElementById('audio-clear');
  var current = document.getElementById('audio-current');
  var removeBtn = document.getElementById('audio-remove');
  var removeInput = document.getElementById('remove-audio');
  var recBtn = document.getElementById('rec-btn');
  var recTimer = document.getElementById('rec-timer');
  var previewUrl = null;

  function showPreview(file) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (!file) {
      preview.hidden = true;
      previewPlayer.removeAttribute('src');
      return;
    }
    previewUrl = URL.createObjectURL(file);
    previewPlayer.src = previewUrl;
    previewName.textContent = file.name + ' · ' + (file.size / 1024 / 1024).toFixed(1) + ' MB';
    preview.hidden = false;
    if (current) current.hidden = true; // the new clip replaces the old one on save
  }

  function setFile(file) {
    if (file.size > AUDIO_MAX_BYTES) {
      alert('حجم الملف أكبر من ' + form.dataset.audioMaxMb + ' ميجابايت.');
      return;
    }
    var dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    showPreview(file);
  }

  fileInput.addEventListener('change', function () {
    var file = fileInput.files[0];
    if (file && file.size > AUDIO_MAX_BYTES) {
      alert('حجم الملف أكبر من ' + form.dataset.audioMaxMb + ' ميجابايت.');
      fileInput.value = '';
      file = null;
    }
    showPreview(file);
    if (!file && current && removeInput.value !== '1') current.hidden = false;
  });

  clearBtn.addEventListener('click', function () {
    fileInput.value = '';
    showPreview(null);
    if (current && removeInput.value !== '1') current.hidden = false;
  });

  if (removeBtn) {
    removeBtn.addEventListener('click', function () {
      removeInput.value = '1';
      current.hidden = true;
    });
  }

  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('dragging'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('dragging'); });
  });
  drop.addEventListener('drop', function (e) {
    var file = e.dataTransfer.files[0];
    if (!file) return;
    if (!/^audio\//.test(file.type)) { alert('الملف يجب أن يكون مقطعًا صوتيًا.'); return; }
    setFile(file);
  });

  // Microphone recording (needs HTTPS or localhost).
  if (!window.MediaRecorder || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    recBtn.hidden = true;
    return;
  }
  var recorder = null;
  var chunks = [];
  var timerId = null;

  function pickMime() {
    var types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
    for (var i = 0; i < types.length; i++) {
      if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    }
    return '';
  }

  function stopTimer() {
    clearInterval(timerId);
    recTimer.hidden = true;
  }

  recBtn.addEventListener('click', function () {
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var mime = pickMime();
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunks = [];
      recorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
      recorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        stopTimer();
        recBtn.textContent = '🎙 تسجيل من الميكروفون';
        recBtn.classList.remove('recording');
        var type = (recorder.mimeType || 'audio/webm').split(';')[0];
        var ext = type === 'audio/mp4' ? 'm4a' : type.split('/')[1];
        var stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
        setFile(new File(chunks, 'recording-' + stamp + '.' + ext, { type: type }));
      };
      recorder.start();
      recBtn.textContent = '■ إيقاف التسجيل';
      recBtn.classList.add('recording');
      var started = Date.now();
      recTimer.hidden = false;
      recTimer.textContent = '00:00';
      timerId = setInterval(function () {
        var s = Math.floor((Date.now() - started) / 1000);
        recTimer.textContent = String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
      }, 250);
    }).catch(function () {
      alert('تعذّر الوصول إلى الميكروفون. تأكد من السماح للمتصفح باستخدامه.');
    });
  });
});
