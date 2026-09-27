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

  // Drag to reorder options. Pointer events (not HTML5 drag & drop) so it also
  // works with touch; the "correct" radio travels with its row.
  optionsBox.addEventListener('pointerdown', function (e) {
    var handle = e.target.closest('.qf-option-handle');
    if (!handle || e.button > 0) return;
    e.preventDefault();
    var row = handle.closest('.qf-option');
    row.classList.add('dragging');
    optionsBox.classList.add('sorting');

    function onMove(ev) {
      var siblings = Array.prototype.filter.call(rows(), function (r) { return r !== row; });
      var before = null;
      for (var i = 0; i < siblings.length; i++) {
        var rect = siblings[i].getBoundingClientRect();
        if (ev.clientY < rect.top + rect.height / 2) { before = siblings[i]; break; }
      }
      if (before !== row.nextElementSibling || (!before && row !== optionsBox.lastElementChild)) {
        optionsBox.insertBefore(row, before);
      }
    }

    function onUp() {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onUp);
      row.classList.remove('dragging');
      optionsBox.classList.remove('sorting');
      renumber();
    }

    // Listen on the document: moving the row in the DOM would drop pointer capture on the handle.
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onUp);
  });

  renumber();

  // --- New category without leaving the form ------------------------------------
  var catSelect = form.querySelector('select[name="category"]');
  var catBtn = document.getElementById('cat-new-btn');
  var catBox = document.getElementById('cat-new');
  var catAr = document.getElementById('cat-new-ar');
  var catEn = document.getElementById('cat-new-en');
  var catSave = document.getElementById('cat-new-save');
  var catError = document.getElementById('cat-new-error');
  var csrf = form.querySelector('[name="csrfmiddlewaretoken"]').value;

  function toggleCatBox(open) {
    catBox.hidden = !open;
    catBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    catError.textContent = '';
    if (open) catAr.focus();
  }

  function saveCategory() {
    var name = catAr.value.trim();
    if (!name) { catError.textContent = 'اكتب اسم التصنيف.'; catAr.focus(); return; }
    catSave.disabled = true;
    var body = new URLSearchParams({ name_ar: name, name_en: catEn.value.trim() });
    fetch(catBox.dataset.url, {
      method: 'POST', headers: { 'X-CSRFToken': csrf }, body: body, credentials: 'same-origin',
    }).then(function (resp) {
      return resp.json().then(function (data) { return { ok: resp.ok, data: data }; });
    }).then(function (res) {
      if (!res.ok || !res.data.ok) {
        catError.textContent = (res.data && res.data.error) || 'تعذّر إضافة التصنيف.';
        return;
      }
      var option = new Option(res.data.name, res.data.id, true, true);
      catSelect.add(option);
      catAr.value = catEn.value = '';
      toggleCatBox(false);
      catSelect.focus();
    }).catch(function () {
      catError.textContent = 'تعذّر الاتصال بالخادم، حاول مرة أخرى.';
    }).then(function () { catSave.disabled = false; });
  }

  catBtn.addEventListener('click', function () { toggleCatBox(catBox.hidden); });
  document.getElementById('cat-new-cancel').addEventListener('click', function () { toggleCatBox(false); });
  catSave.addEventListener('click', saveCategory);
  [catAr, catEn].forEach(function (el) {
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); saveCategory(); }  // don't submit the question form
      if (e.key === 'Escape') toggleCatBox(false);
    });
  });

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
