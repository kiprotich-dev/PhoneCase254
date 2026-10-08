document.querySelectorAll('.messages').forEach((message) => { setTimeout(() => message.remove(), 4200); });

const showCartMessage = (text, type = 'success') => {
  const messages = document.createElement('div');
  messages.className = `messages ${type}`;
  messages.innerHTML = `<div>${text}</div>`;
  document.body.appendChild(messages);
  setTimeout(() => messages.remove(), 4200);
};

document.querySelectorAll('form[action*="/cart/add/"]').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    const originalText = button?.innerHTML;
    if (button) { button.disabled = true; button.textContent = 'Adding…'; }
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value},
        body: new FormData(form),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'Unable to add this item.');
      const bag = document.querySelector('.bag');
      if (bag) bag.textContent = `Bag (${data.cart_count})`;
      showCartMessage(data.message);
    } catch (error) {
      showCartMessage(error.message, 'error');
    } finally {
      if (button) { button.disabled = false; button.innerHTML = originalText; }
    }
  });
});

document.querySelectorAll('.cart-row input[type="number"]').forEach((input) => {
  input.addEventListener('change', () => input.form.requestSubmit());
});

const checkoutSummary = document.querySelector('.order-aside[data-subtotal]');
if (checkoutSummary) {
  const subtotal = Number(checkoutSummary.dataset.subtotal);
  const itemDiscount = document.querySelector('#checkout-item-discount');
  const deliveryDiscount = document.querySelector('#checkout-delivery-discount');
  const deliveryFee = document.querySelector('#checkout-delivery-fee');
  const pointsDiscount = document.querySelector('#checkout-points-discount');
  const pointsRow = document.querySelector('.points-discount');
  const total = document.querySelector('#checkout-total');
  const pointsInput = document.querySelector('input[name="redeem_points"]');
  const availablePoints = Number(checkoutSummary.dataset.points || 0);
  const updateCheckoutTotal = (paymentMethod) => {
    const grossDelivery = subtotal * 0.10;
    const prepaid = paymentMethod === 'prepaid';
    const itemSaving = prepaid ? subtotal * 0.05 : 0;
    const deliverySaving = subtotal > 2000 ? grossDelivery * 0.50 : (prepaid ? grossDelivery * 0.06 : 0);
    itemDiscount.textContent = itemSaving.toFixed(2);
    deliveryDiscount.textContent = deliverySaving.toFixed(2);
    deliveryFee.textContent = (grossDelivery - deliverySaving).toFixed(2);
    const pointsSaving = pointsInput?.checked ? Math.min(availablePoints, subtotal - itemSaving + grossDelivery - deliverySaving) : 0;
    if (pointsDiscount) pointsDiscount.textContent = pointsSaving.toFixed(2);
    if (pointsRow) pointsRow.hidden = pointsSaving <= 0;
    total.textContent = (subtotal - itemSaving + grossDelivery - deliverySaving - pointsSaving).toFixed(2);
    document.querySelectorAll('.prepaid-discount').forEach((row) => { row.hidden = !prepaid; });
  };
  document.querySelectorAll('input[name="payment_method"]').forEach((radio) => {
    radio.addEventListener('change', () => updateCheckoutTotal(radio.value));
  });
  pointsInput?.addEventListener('change', () => updateCheckoutTotal(document.querySelector('input[name="payment_method"]:checked')?.value || 'prepaid'));
  updateCheckoutTotal(document.querySelector('input[name="payment_method"]:checked')?.value || 'prepaid');
}
