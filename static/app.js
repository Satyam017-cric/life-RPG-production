document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;
  const completeForms = document.querySelectorAll('[data-complete]');
  const celebration = document.getElementById('celebration');

  completeForms.forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button');
      if (!button || button.disabled) return;
      button.disabled = true;
      button.textContent = 'Clearing…';
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          headers: { 'Accept': 'application/json', 'X-Requested-With': 'fetch' },
          body: new FormData(form),
        });
        if (!response.ok) throw new Error('Quest completion failed');
        const result = await response.json();
        showCelebration(result);
        setTimeout(() => window.location.reload(), 900);
      } catch (error) {
        form.submit();
      }
    });
  });

  function showCelebration(result) {
    if (!celebration) return;
    const title = document.getElementById('celebration-title');
    const copy = document.getElementById('celebration-copy');
    title.textContent = result.level_up ? `LEVEL ${result.new_level} UNLOCKED` : 'QUEST COMPLETE';
    copy.textContent = `+${result.xp_gained} XP  ·  +${result.gold_gained} Gold  ·  ${result.streak} day streak`;
    celebration.setAttribute('aria-hidden', 'false');
    celebration.classList.add('show');
  }

  document.querySelectorAll('.toast').forEach((toast) => {
    setTimeout(() => toast.classList.add('hide'), 4200);
  });

  const nav = document.querySelector('nav');
  if (nav) {
    document.querySelectorAll('nav a').forEach((link) => {
      if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
    });
  }

  if (root.dataset.theme === 'neon') root.style.setProperty('--theme-accent', '#7df9ff');
  if (root.dataset.theme === 'ember') root.style.setProperty('--theme-accent', '#ff9b54');
  if (root.dataset.theme === 'aether') root.style.setProperty('--theme-accent', '#9bbcff');
});
