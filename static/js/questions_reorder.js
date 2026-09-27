document.addEventListener('DOMContentLoaded', function () {
  var table = document.getElementById('questions-table');
  if (!table || !table.dataset.reorderUrl) return;

  var tbody = table.tBodies[0];
  var status = document.getElementById('reorder-status');
  var csrf = document.querySelector('#reorder-csrf [name="csrfmiddlewaretoken"]').value;
  var saveTimer = null;
  var dragged = null;

  function rows() { return Array.prototype.slice.call(tbody.rows); }

  function setStatus(text, cls) {
    if (!status) return;
    status.textContent = text;
    status.className = 'qo-status' + (cls ? ' ' + cls : '');
  }

  function refresh() {
    var list = rows();
    list.forEach(function (row, i) {
      row.querySelector('.qo-num').textContent = i + 1;
      row.querySelector('.qo-arrow[data-dir="-1"]').disabled = i === 0;
      row.querySelector('.qo-arrow[data-dir="1"]').disabled = i === list.length - 1;
    });
  }

  function flash(row) {
    row.classList.remove('moved');
    void row.offsetWidth; // restart the animation
    row.classList.add('moved');
  }

  // Debounced so several quick arrow clicks become one request.
  function scheduleSave() {
    refresh();
    setStatus('جارٍ الحفظ…');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 400);
  }

  function save() {
    var body = new URLSearchParams();
    rows().forEach(function (row) { body.append('ids', row.dataset.id); });
    fetch(table.dataset.reorderUrl, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf },
      body: body,
      credentials: 'same-origin',
    }).then(function (resp) {
      if (resp.ok) return setStatus('✓ تم حفظ الترتيب', 'ok');
      if (resp.status === 409) {
        setStatus('تم تعديل الأسئلة من مكان آخر — أعد تحميل الصفحة ثم حاول مرة أخرى.', 'error');
      } else {
        setStatus('تعذّر حفظ الترتيب، حاول مرة أخرى.', 'error');
      }
    }).catch(function () {
      setStatus('تعذّر الاتصال بالخادم، حاول مرة أخرى.', 'error');
    });
  }

  // Arrow buttons
  tbody.addEventListener('click', function (e) {
    var btn = e.target.closest('.qo-arrow');
    if (!btn || btn.disabled) return;
    var row = btn.closest('tr');
    if (btn.dataset.dir === '-1') tbody.insertBefore(row, row.previousElementSibling);
    else tbody.insertBefore(row.nextElementSibling, row);
    flash(row);
    scheduleSave();
    // Keep keyboard focus on the same arrow so it can be pressed repeatedly.
    var again = row.querySelector('.qo-arrow[data-dir="' + btn.dataset.dir + '"]');
    (again.disabled ? row.querySelector('.qo-arrow:not(:disabled)') : again).focus();
  });

  // Drag & drop — only starts from the handle, so text in the row stays selectable.
  tbody.addEventListener('mousedown', function (e) {
    var handle = e.target.closest('.qo-handle');
    if (handle) handle.closest('tr').draggable = true;
  });
  document.addEventListener('mouseup', function () {
    rows().forEach(function (row) { if (row !== dragged) row.draggable = false; });
  });

  tbody.addEventListener('dragstart', function (e) {
    dragged = e.target.closest('tr');
    if (!dragged) return;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', dragged.dataset.id);
    dragged.classList.add('dragging');
  });

  tbody.addEventListener('dragover', function (e) {
    if (!dragged) return;
    e.preventDefault();
    var target = e.target.closest('tr');
    if (!target || target === dragged) return;
    var rect = target.getBoundingClientRect();
    var after = e.clientY > rect.top + rect.height / 2;
    tbody.insertBefore(dragged, after ? target.nextElementSibling : target);
  });

  tbody.addEventListener('drop', function (e) { e.preventDefault(); });

  tbody.addEventListener('dragend', function () {
    if (!dragged) return;
    var row = dragged;
    dragged = null;
    row.classList.remove('dragging');
    row.draggable = false;
    flash(row);
    scheduleSave();
  });

  refresh();
});
