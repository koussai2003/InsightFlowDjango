(() => {
  const root = document.documentElement;
  const themeButton = document.getElementById('theme-toggle');
  let theme = 'dark';
  try { theme = localStorage.getItem('insightflow-theme') || 'dark'; } catch {}
  root.dataset.theme = theme;
  themeButton?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('insightflow-theme', root.dataset.theme); } catch {}
  });

  const search = document.getElementById('project-search');
  search?.addEventListener('input', () => {
    const query = search.value.trim().toLowerCase();
    document.querySelectorAll('.project-link').forEach(link => {
      link.hidden = !link.querySelector('.project-name').textContent.toLowerCase().includes(query);
    });
  });

  const form = document.getElementById('question-form');
  const question = document.getElementById('question');
  const conversation = document.getElementById('conversation');
  const welcome = document.getElementById('welcome');
  const suggestions = document.getElementById('suggestions');
  const fileInput = document.getElementById('csv-file');
  const status = document.getElementById('upload-status');
  const fileHint = document.getElementById('file-hint');
  const preview = document.getElementById('dataset-preview');
  const table = document.getElementById('preview-table');

  document.querySelectorAll('.suggestions button').forEach(button => button.addEventListener('click', () => {
    question.value = button.textContent.replace(' ↗', '').trim(); question.focus();
  }));

  form?.addEventListener('submit', event => {
    event.preventDefault();
    const value = question.value.trim(); if (!value) return;
    welcome?.classList.add('hidden'); suggestions?.classList.add('hidden');
    const bubble = document.createElement('article'); bubble.className = 'chat-message';
    bubble.textContent = value;
    const note = document.createElement('small'); note.textContent = 'Saved in this browser session · AI replies are not connected yet.';
    bubble.append(note); conversation.append(bubble); question.value = '';
    bubble.scrollIntoView({ block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });
  question?.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });

  function parseCSV(text) {
    const rows = []; let row = [], cell = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (ch === '"') { if (quoted && text[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted; }
      else if (ch === ',' && !quoted) { row.push(cell); cell = ''; }
      else if ((ch === '\n' || ch === '\r') && !quoted) { if (ch === '\r' && text[i + 1] === '\n') i++; row.push(cell); if (row.some(v => v.trim())) rows.push(row); row = []; cell = ''; if (rows.length >= 6) break; }
      else cell += ch;
    }
    if (row.length || cell) { row.push(cell); if (row.some(v => v.trim())) rows.push(row); }
    if (quoted) throw new Error('CSV has an unclosed quote.');
    return rows;
  }
  fileInput?.addEventListener('change', async () => {
    const file = fileInput.files?.[0]; if (!file) return;
    status.textContent = '';
    if (!file.name.toLowerCase().endsWith('.csv') || file.size > 10 * 1024 * 1024) { status.textContent = 'Choose a CSV file smaller than 10 MB.'; fileInput.value = ''; return; }
    try {
      const rows = parseCSV((await file.text()).replace(/^\uFEFF/, ''));
      if (!rows.length) throw new Error('This CSV is empty.');
      table.replaceChildren();
      const head = document.createElement('thead'), headRow = document.createElement('tr');
      rows[0].forEach(value => { const th = document.createElement('th'); th.textContent = value || 'Column'; headRow.append(th); }); head.append(headRow); table.append(head);
      const body = document.createElement('tbody');
      rows.slice(1).forEach(values => { const tr = document.createElement('tr'); rows[0].forEach((_, i) => { const td = document.createElement('td'); td.textContent = values[i] || '—'; tr.append(td); }); body.append(tr); }); table.append(body);
      document.getElementById('dataset-name').textContent = file.name;
      document.getElementById('dataset-count').textContent = `First ${Math.max(0, rows.length - 1)} rows`;
      preview.classList.remove('hidden'); fileHint.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
      const config = document.getElementById('upload-config');
      if (config) {
        const data = new FormData(); data.append('csv_file', file);
        const csrf = config.querySelector('[name=csrfmiddlewaretoken]').value;
        const response = await fetch(config.dataset.uploadUrl, { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: data });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'The CSV preview is ready, but upload failed.');
        status.textContent = `${file.name} uploaded to this project.`;
      }
    } catch (error) { status.textContent = error.message; }
  });
})();
