(function () {
  const panel = document.querySelector('.chat-panel');
  if (!panel) return;

  const body = panel.querySelector('.chat-body');
  const form = panel.querySelector('.chat-form');
  const input = form.querySelector('input');
  const history = [];

  const fallback = [
    ['what is phonecase254', 'phoneCase254 is a Kenyan lifestyle brand creating stylish, reliable phone cases that protect the device you use every day while expressing your personal style.'],
    ['why phonecase254', 'Choose phoneCase254 for thoughtfully designed cases, dependable everyday protection, local delivery, secure payment options, rewards for loyal customers, and support when you need it.'],
    ['founder', 'Vincent Kiprotich is the Founder and CEO of phoneCase254. Learn more on LinkedIn: www.linkedin.com/in/vincent-kiprotich-84257b221'],
    ['ceo', 'Vincent Kiprotich is the Founder and CEO of phoneCase254. Learn more on LinkedIn: www.linkedin.com/in/vincent-kiprotich-84257b221'],
    ['career', 'Open the Careers page to see current vacancies. Select a job, read the requirements, attach your CV, and submit the application online.'],
    ['job', 'Open the Careers page to see current vacancies. Select a job, read the requirements, attach your CV, and submit the application online.'],
    ['delivery', 'Delivery timing depends on your location. Sign in and use Track delivery to follow your order.'],
    ['mpesa', 'Enter the M-Pesa number at checkout. Your order is confirmed after successful payment.'],
    ['payment', 'Choose Pay before delivery or Pay on delivery at checkout.'],
    ['track', 'Sign in, open Your orders, and choose Track delivery.'],
    ['cancel', 'Eligible orders can be cancelled within three minutes while still on queue.'],
    ['return', 'Contact support with your order reference for return or refund help.'],
    ['point', 'Rewards points appear in Your orders and can be used as KSh credit.'],
    ['password', 'Use Forgot password on the login page to receive a reset link.']
  ];

  function localAnswer(question) {
    const text = question.toLowerCase();
    const match = fallback.find(item => text.includes(item[0]));
    return match ? match[1] : 'I can help with products, delivery, M-Pesa, payments, tracking, cancellations, returns, rewards, careers, and passwords. What would you like to know?';
  }

  function csrfToken() {
    return document.cookie.split('; ').find(item => item.startsWith('csrftoken='))?.split('=')[1] || '';
  }

  function add(text, role) {
    const message = document.createElement('div');
    message.className = 'chat-message ' + (role || '');
    message.textContent = text;
    body.append(message);
    body.scrollTop = body.scrollHeight;
    if (role === 'user' || role === 'assistant') history.push({ role, content: text });
  }

  async function ask(question) {
    const thinking = document.createElement('div');
    thinking.className = 'chat-message';
    thinking.textContent = 'Let me think about that…';
    body.append(thinking);
    body.scrollTop = body.scrollHeight;

    try {
      // The newest question is already in history; send only the preceding turns.
      const previousTurns = history.slice(0, -1).slice(-8);
      const response = await fetch('/api/nova/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({ message: question, history: previousTurns })
      });
      const data = await response.json();
      thinking.remove();
      const answer = data.ok ? data.message : localAnswer(question);
      add(answer, 'assistant');
    } catch (error) {
      thinking.remove();
      add(localAnswer(question), 'assistant');
    }
  }

  form.addEventListener('submit', function (event) {
    event.stopImmediatePropagation();
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    add(question, 'user');
    input.value = '';
    ask(question);
  }, true);

  panel.querySelectorAll('.chat-suggestion').forEach(button => {
    button.addEventListener('click', function (event) {
      event.stopImmediatePropagation();
      add(button.textContent, 'user');
      ask(button.textContent);
    }, true);
  });
})();
