// Level test page: countdowns, locking and saving answers. The server enforces
// every limit; this only shows the time and reacts when it runs out.
document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('quiz-form');
  if (!form) return;
  var submitting = false;

  function autoSubmit(nav) {
    if (submitting) return;
    submitting = true;
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'nav';
    input.value = nav;
    form.appendChild(input);
    form.submit(); // no submitter, so only this "nav" value is sent (with the chosen option)
  }

  function fmt(seconds) {
    seconds = Math.max(0, Math.ceil(seconds));
    var m = Math.floor(seconds / 60), s = seconds % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }

  // Count down from the server's figure using the local clock's elapsed time
  // (not its absolute value), so a wrong device clock doesn't matter.
  function countdown(el, onTick, onDone) {
    if (!el) return;
    var remaining = parseFloat(el.dataset.remaining);
    var startedAt = performance.now();
    function step() {
      var left = remaining - (performance.now() - startedAt) / 1000;
      onTick(left);
      if (left <= 0) { onDone(); return; }
      setTimeout(step, 250);
    }
    step();
  }

  var examTimer = document.getElementById('exam-timer');
  countdown(examTimer, function (left) {
    examTimer.querySelector('.quiz-timer-value').textContent = fmt(left);
    examTimer.classList.toggle('low', left <= 60);
  }, function () { autoSubmit('finish'); });

  var options = form.querySelectorAll('input[name="option"]');
  var csrf = form.querySelector('[name="csrfmiddlewaretoken"]').value;

  // Save the choice straight away, so it counts even if the question's time
  // runs out before the student presses "Next".
  options.forEach(function (radio) {
    radio.addEventListener('change', function () {
      var dot = form.querySelector('.quiz-dot.current');
      if (dot) dot.classList.add('answered');
      var body = new URLSearchParams({
        question: form.querySelector('[name="question"]').value,
        option: radio.value,
        nav: 'save',
      });
      fetch(form.action, {
        method: 'POST', headers: { 'X-CSRFToken': csrf }, body: body, credentials: 'same-origin',
      }).catch(function () { /* the choice is sent again with "Next" */ });
    });
  });

  // When the question's time is up: lock the answers and wait for "Next".
  function lockQuestion() {
    options.forEach(function (radio) {
      radio.disabled = true;
      radio.closest('.quiz-option').classList.add('is-locked');
    });
    document.getElementById('locked-msg').hidden = false;
    var next = form.querySelector('.quiz-next, .quiz-finish');
    if (next) {
      next.classList.add('quiz-attention');
      next.focus();
    }
  }

  var qTimer = document.getElementById('question-timer');
  if (qTimer) {
    var limit = parseFloat(qTimer.dataset.limit) || 1;
    var bar = qTimer.querySelector('.quiz-qtimer-bar');
    countdown(qTimer, function (left) {
      qTimer.querySelector('.quiz-qtimer-value').textContent = fmt(left);
      bar.style.width = Math.max(0, Math.min(100, left / limit * 100)) + '%';
      qTimer.classList.toggle('low', left <= Math.min(10, limit * 0.25));
    }, lockQuestion);
  }

  // Ask before finishing with unanswered questions.
  form.addEventListener('submit', function (e) {
    var submitter = e.submitter;
    if (submitting || !submitter || !submitter.hasAttribute('data-finish')) return;
    var unanswered = parseInt(form.dataset.unanswered, 10) || 0;
    var pickedNow = form.querySelector('input[name="option"]:checked') && form.dataset.hadAnswer === '0';
    if (pickedNow) unanswered -= 1;
    var phrases = JSON.parse(document.getElementById('unanswered-phrases').textContent);
    if (unanswered > 0 && !window.confirm(form.dataset.confirm.replace('{n}', phrases[unanswered] || unanswered))) {
      e.preventDefault();
      return;
    }
    submitting = true;
  });
});
