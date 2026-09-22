const state = {
  bootstrap: null,
  run: null,
  nextEstimate: null,
};

const RATE_FIELDS = [
  ['openai_input_usd_per_million', 'OpenAI input / 1M tokens'],
  ['openai_output_usd_per_million', 'OpenAI output / 1M tokens'],
  ['openai_web_search_usd_per_call', 'OpenAI web_search / call'],
  ['runway_narration_speech_usd', 'Runway narration speech / job'],
  ['runway_short_video_usd', 'Runway short video / job'],
  ['runway_host_ride_plate_usd', 'Runway host ride plate / job'],
  ['runway_avatar_presenter_usd', 'Runway preset avatar / job'],
  ['runway_sound_bed_usd', 'Runway sound bed / job'],
  ['runway_routed_audio_usd', 'Runway routed audio / job'],
  ['runway_routed_video_usd', 'Runway routed video / job'],
];

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function checkedValues(selector) {
  return [...document.querySelectorAll(selector + ':checked')].map((el) => el.value);
}

function money(value) {
  if (value === null || value === undefined) return 'n/a';
  return `$${Number(value).toFixed(4)}`;
}

function tokens(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString();
}

function collectPricing() {
  const pricing = {};
  for (const [key] of RATE_FIELDS) {
    const el = document.getElementById(`rate-${key}`);
    if (el && el.value !== '') pricing[key] = Number(el.value);
  }
  return pricing;
}

function renderRates(defaults) {
  const box = document.getElementById('pricing-rates');
  box.innerHTML = RATE_FIELDS.map(([key, label]) => `
    <label class="rate-row">
      <span>${label}</span>
      <input id="rate-${key}" type="number" min="0" step="0.001"
        value="${defaults[key] ?? 0}" />
    </label>`).join('');
}

function renderStages(run) {
  const nav = document.getElementById('stage-nav');
  const stages = (state.bootstrap && state.bootstrap.stages) || [];
  nav.innerHTML = stages.map((name) => {
    const info = (run && run.stages && run.stages[name]) || { status: 'blocked' };
    const current = run && run.stage === name ? 'current' : '';
    const cost = info.cost;
    const est = cost && cost.estimate ? money(cost.estimate.usd) : '';
    return `<div class="stage-pill ${info.status} ${current}" title="${info.status}">
      ${name}<br><small>${info.status}${est ? ' · est ' + est : ''}</small>
    </div>`;
  }).join('');
}

function renderBootstrap(data) {
  document.getElementById('theme-text').textContent = data.theme;
  document.getElementById('hypotheses').innerHTML = data.hypotheses.map((h) => `
    <label><input type="checkbox" name="hypothesis" value="${h.id}" checked />
      <span><strong>${h.id}</strong> — ${h.statement}</span></label>`).join('');
  document.getElementById('formats').innerHTML = data.writing_formats.map((f, i) => `
    <label><input type="checkbox" name="format" value="${f}" ${i === 0 ? 'checked' : ''} />
      <span>${f}</span></label>`).join('');
  const defaults = new Set(['narration_speech', 'short_video', 'host_ride_plate']);
  document.getElementById('media-targets').innerHTML = data.media_capabilities.map((m) => `
    <label><input type="checkbox" name="media" value="${m.id}" ${defaults.has(m.id) ? 'checked' : ''} />
      <span>${m.label}</span></label>`).join('');
  const plate = data.host_plate || {};
  const plateEl = document.getElementById('host-plate-status');
  if (plateEl) {
    plateEl.textContent = plate.exists
      ? `Host plate found: ${plate.path}`
      : `Host plate missing — copy your Peloton ride MP4 to ${plate.path || 'media/plates/ride.mp4'}`;
    plateEl.className = plate.exists ? 'hint ok' : 'hint warn-inline';
  }
  renderRates(data.pricing_defaults || {});
  renderStages(null);
}

function renderCostSummary(run) {
  const el = document.getElementById('cost-summary');
  const roll = run.cost_rollup || {};
  const planned = run.planned_cost || {};
  el.hidden = false;
  el.innerHTML = `
    <h3>Cost rollup</h3>
    <p><strong>Planned pipeline:</strong> ${money(planned.estimate_usd_total)}</p>
    <p><strong>Estimate so far:</strong> ${money(roll.estimate_usd_total)}
      · in ${tokens(roll.estimate_input_tokens)} / out ${tokens(roll.estimate_output_tokens)} tokens</p>
    <p><strong>Actual so far:</strong> ${money(roll.actual_usd_total)}
      · in ${tokens(roll.actual_input_tokens)} / out ${tokens(roll.actual_output_tokens)} tokens</p>
    <p class="hint">Actual USD uses provider usage when present; Runway often requires checking the dashboard.</p>
  `;
}

async function refreshNextEstimate(run) {
  const box = document.getElementById('next-estimate');
  try {
    const preview = await api(`/api/runs/${run.run_id}/estimate`);
    state.nextEstimate = preview;
    box.hidden = false;
    if (!preview.stage || !preview.estimate) {
      box.innerHTML = `<h3>Next step</h3><p>No billable stage pending.</p>`;
      return;
    }
    const e = preview.estimate;
    box.innerHTML = `
      <h3>Next step cost preview · ${preview.stage}</h3>
      <p><strong>Est. USD:</strong> ${money(e.usd)}</p>
      <p><strong>Est. tokens:</strong> in ${tokens(e.input_tokens)} / out ${tokens(e.output_tokens)}
        ${e.tool_calls ? ` · tool calls ${e.tool_calls}` : ''}</p>
      <p class="hint">${e.note || ''}</p>
    `;
  } catch (err) {
    box.hidden = false;
    box.innerHTML = `<p class="warn">${err.message}</p>`;
  }
}

function renderRun(run) {
  state.run = run;
  const meta = document.getElementById('run-meta');
  const json = document.getElementById('run-json');
  const actions = document.getElementById('run-actions');
  meta.textContent = `Run ${run.run_id} · stage ${run.stage} · formats ${run.formats.join(', ')}`;
  json.hidden = false;
  json.textContent = JSON.stringify(run, null, 2);
  actions.hidden = false;
  renderStages(run);
  renderDetail(run);
  renderCostSummary(run);
  refreshNextEstimate(run);
}

function renderDetail(run) {
  const el = document.getElementById('stage-detail');
  const cards = Object.entries(run.stages).map(([name, info]) => {
    const cost = info.cost;
    const est = cost && cost.estimate;
    const act = cost && cost.actual;
    const costHtml = est ? `
      <div class="cost-grid">
        <div><span>Estimate</span><strong>${money(est.usd)}</strong>
          <small>in ${tokens(est.input_tokens)} / out ${tokens(est.output_tokens)}</small></div>
        <div><span>Actual</span><strong>${money(act && act.usd)}</strong>
          <small>in ${tokens(act && act.input_tokens)} / out ${tokens(act && act.output_tokens)}
          · ${act && act.source ? act.source : ''}</small></div>
      </div>` : '';
    return `
    <article class="card">
      <h3>${name} · ${info.status}</h3>
      <p>${info.summary || info.reason || '—'}</p>
      ${costHtml}
    </article>`;
  }).join('');
  el.innerHTML = cards;
}

function showError(err) {
  const box = document.getElementById('error');
  box.hidden = !err;
  box.textContent = err || '';
}

async function startRun() {
  showError('');
  try {
    const run = await api('/api/runs', {
      method: 'POST',
      body: JSON.stringify({
        hypothesis_ids: checkedValues('input[name="hypothesis"]'),
        formats: checkedValues('input[name="format"]'),
        media_targets: checkedValues('input[name="media"]'),
        pricing: collectPricing(),
      }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function advance() {
  if (!state.run) return;
  showError('');
  try {
    const run = await api(`/api/runs/${state.run.run_id}/advance`, {
      method: 'POST',
      body: JSON.stringify({ live: false, pricing: collectPricing() }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function skip(stage) {
  if (!state.run) return;
  showError('');
  try {
    const run = await api(`/api/runs/${state.run.run_id}/skip`, {
      method: 'POST',
      body: JSON.stringify({ stage, reason: 'Skipped from UI' }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function runStage(stage) {
  if (!state.run) return;
  showError('');
  try {
    const run = await api(`/api/runs/${state.run.run_id}/stage/${stage}`, {
      method: 'POST',
      body: JSON.stringify({ live: false, pricing: collectPricing() }),
    });
    renderRun(run);
  } catch (err) {
    showError(err.message);
  }
}

async function init() {
  showError('');
  state.bootstrap = await api('/api/bootstrap');
  renderBootstrap(state.bootstrap);
  document.getElementById('btn-start').addEventListener('click', startRun);
  document.getElementById('btn-advance').addEventListener('click', advance);
  document.getElementById('btn-skip-research').addEventListener('click', () => skip('research'));
  document.getElementById('btn-skip-writing').addEventListener('click', () => skip('writing'));
  document.getElementById('btn-research').addEventListener('click', () => runStage('research'));
  document.getElementById('btn-writing').addEventListener('click', () => runStage('writing'));
  document.getElementById('btn-media').addEventListener('click', () => runStage('media'));
  document.getElementById('btn-review').addEventListener('click', () => runStage('review'));
}

init().catch((err) => showError(err.message));
