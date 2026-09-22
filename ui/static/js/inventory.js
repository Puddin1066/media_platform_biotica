async function api(path) {
  const res = await fetch(path);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function statusClass(status) {
  if (status.includes('complete') || status === 'usable') return 'ok';
  if (status.includes('half') || status.includes('noisy')) return 'warn-inline';
  return 'hint';
}

function render(data) {
  document.getElementById('pragmatic').textContent = data.pragmatic_answer;
  const intended = data.intended;
  document.getElementById('intended').innerHTML = `
    <h3>${intended.name} · ${intended.status}</h3>
    <p><strong>Should be:</strong> ${intended.should_be}</p>
    <p><strong>Actually is:</strong> ${intended.actually_is}</p>
    <p><strong>Entry:</strong> <code>${intended.entry}</code></p>
  `;
  document.getElementById('counts').innerHTML = Object.entries(data.status_counts).map(([k, v]) => `
    <article class="card"><h3>${v}</h3><p class="${statusClass(k)}">${k}</p></article>
  `).join('');
  document.getElementById('pieces').innerHTML = data.pieces.map((p) => `
    <article class="card">
      <h3>${p.name} <small>(${p.file})</small></h3>
      <p class="${statusClass(p.status)}">${p.status}</p>
      <p>${p.role}</p>
      <p><strong>Baked:</strong> ${p.baked}</p>
      <p><strong>Missing:</strong> ${p.missing}</p>
    </article>
  `).join('');
}

api('/api/inventory').then(render).catch((err) => {
  document.getElementById('pragmatic').textContent = err.message;
});
