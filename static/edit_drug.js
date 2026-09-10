document.querySelectorAll('.use-purchase-cost').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById('buy_price');
    input.value = button.dataset.cost;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('costSelectionStatus').textContent =
      `Cost selected from purchase ${button.dataset.date || '(no date)'}. Click Update to save.`;
    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    input.focus({ preventScroll: true });
  });
});
