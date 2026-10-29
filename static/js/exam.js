// Confirm before handing the exam in (answers can't be changed afterwards).
(function () {
  var form = document.querySelector(".ex-form");
  if (!form) return;
  form.addEventListener("submit", function (e) {
    if (!window.confirm(form.dataset.confirm)) e.preventDefault();
  });
})();
