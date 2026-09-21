document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.querySelector('.dash-sidebar-toggle');
  var sidebar = document.querySelector('.dash-sidebar');
  var overlay = document.querySelector('.dash-overlay');
  if (!toggle || !sidebar || !overlay) return;

  function closeSidebar() {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
  }

  toggle.addEventListener('click', function () {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  });
  overlay.addEventListener('click', closeSidebar);
});
