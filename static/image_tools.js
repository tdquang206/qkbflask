document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('imageToolsBtn');
  if (!button) return;
  const menu = document.getElementById('imageToolsMenu');
  const close = () => { menu.hidden = true; button.setAttribute('aria-expanded', 'false'); };
  button.addEventListener('click', () => {
    menu.hidden = !menu.hidden;
    button.setAttribute('aria-expanded', String(!menu.hidden));
  });
  button.addEventListener('keydown', event => {
    if (['ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault(); menu.hidden = false; button.setAttribute('aria-expanded', 'true'); menu.querySelector('button').focus();
    }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.image-tools-dropdown') || event.target.closest('#imageToolsMenu button')) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !menu.hidden) { event.preventDefault(); close(); button.focus(); }
  });
  document.getElementById('clearSelectionBtn').addEventListener('click', close);
  document.querySelectorAll('.compare-checkbox').forEach(cb => cb.addEventListener('change', close));
});
