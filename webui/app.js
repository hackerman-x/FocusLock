// FocusLock web UI (pywebview). Talks to Python only through
// window.pywebview.api.* -- every privileged action (starting a block,
// the YouTube break) goes through that bridge into the same shell scripts
// the Tkinter version used, so the enforcement lives in Python/bash, not
// in this JS.

const APP_ROOT = document.getElementById('app');

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

// ---------- theme ----------

// localStorage can be missing entirely (WebKitGTK in private mode), and a
// throw here would stop the whole UI from loading -- the theme is optional.
function loadTheme() {
  try { return localStorage.getItem('focuslock-theme'); } catch (e) { return null; }
}

function storeTheme(theme) {
  try { localStorage.setItem('focuslock-theme', theme); } catch (e) { /* not persisted */ }
}

function initTheme() {
  const saved = loadTheme() || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeButton();
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  storeTheme(next);
  updateThemeButton();
}

function updateThemeButton() {
  const cur = document.documentElement.getAttribute('data-theme');
  document.getElementById('themeToggle').textContent = cur === 'dark' ? 'Light mode' : 'Dark mode';
}

document.getElementById('themeToggle').addEventListener('click', toggleTheme);

// ---------- generic modal dialogs (return Promises) ----------

function openTemplate(id) {
  const tpl = document.getElementById(id);
  const node = tpl.content.cloneNode(true);
  const backdrop = node.querySelector('.modal-backdrop');
  document.body.appendChild(node);
  return document.querySelector('.modal-backdrop:last-of-type') || backdrop;
}

function closeModal(modalBackdrop) {
  modalBackdrop.remove();
}

function openNameDialog() {
  return new Promise((resolve) => {
    const modal = openTemplate('tpl-name-dialog');
    const input = modal.querySelector('.name-input');
    input.focus();
    const finish = (val) => { closeModal(modal); resolve(val); };
    modal.querySelector('[data-action="cancel"]').addEventListener('click', () => finish(null));
    modal.querySelector('[data-action="submit"]').addEventListener('click', () => {
      const name = input.value.trim();
      finish(name || null);
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') modal.querySelector('[data-action="submit"]').click();
      if (e.key === 'Escape') finish(null);
    });
  });
}

function openPasswordDialog(title, summaryLines, confirmWord) {
  return new Promise((resolve) => {
    const modal = openTemplate('tpl-password-dialog');
    modal.querySelector('.modal-title-yellow').textContent = title;
    const summaryEl = modal.querySelector('.summary-lines');
    summaryLines.forEach((line) => summaryEl.appendChild(el('div', null, line)));
    modal.querySelector('.confirm-label').textContent = `TYPE "${confirmWord}" TO CONFIRM`;
    modal.querySelector('[data-action="submit"]').textContent = title;

    const pwInput = modal.querySelector('.pw-input');
    const confirmInput = modal.querySelector('.confirm-input');
    const errorEl = modal.querySelector('.pw-error');
    pwInput.focus();

    const finish = (val) => { closeModal(modal); resolve(val); };
    modal.querySelector('[data-action="cancel"]').addEventListener('click', () => finish(null));
    const submit = () => {
      if (confirmInput.value !== confirmWord) {
        errorEl.textContent = `Confirmation must be exactly "${confirmWord}".`;
        return;
      }
      if (!pwInput.value) {
        errorEl.textContent = 'Password is required.';
        return;
      }
      finish(pwInput.value);
    };
    modal.querySelector('[data-action="submit"]').addEventListener('click', submit);
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submit();
      if (e.key === 'Escape') finish(null);
    });
  });
}

function openSelectionDialog(apps, domains, presets, initialApps, initialDomains) {
  return new Promise((resolve) => {
    const modal = openTemplate('tpl-selection-dialog');
    const appsBox = modal.querySelector('.apps-checks');
    const domainsBox = modal.querySelector('.domains-checks');
    const errorEl = modal.querySelector('#selectionError');

    const appVars = {};
    const domainVars = {};

    apps.forEach(([key, label]) => {
      const wrap = el('label', 'check-item');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = initialApps.includes(key);
      appVars[key] = cb;
      wrap.appendChild(cb);
      wrap.appendChild(el('span', null, label));
      appsBox.appendChild(wrap);
    });
    domains.forEach(([key, label]) => {
      const wrap = el('label', 'check-item');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = initialDomains.includes(key);
      domainVars[key] = cb;
      wrap.appendChild(cb);
      wrap.appendChild(el('span', null, label));
      domainsBox.appendChild(wrap);
    });

    function renderPresets() {
      const row = modal.querySelector('.presets-row');
      row.innerHTML = '';
      const names = Object.keys(presets);
      if (names.length === 0) {
        row.appendChild(el('span', 'presets-empty', '(none saved yet -- customize below, then save one)'));
        return;
      }
      names.forEach((name) => {
        const pill = el('span', 'preset-pill', name);
        pill.addEventListener('click', () => {
          const preset = presets[name];
          Object.entries(appVars).forEach(([k, cb]) => { cb.checked = preset.apps.includes(k); });
          Object.entries(domainVars).forEach(([k, cb]) => { cb.checked = preset.domains.includes(k); });
        });
        row.appendChild(pill);
      });
    }
    renderPresets();

    modal.querySelector('#savePresetBtn').addEventListener('click', async () => {
      const name = await openNameDialog();
      if (!name) return;
      const selApps = Object.entries(appVars).filter(([, cb]) => cb.checked).map(([k]) => k);
      const selDomains = Object.entries(domainVars).filter(([, cb]) => cb.checked).map(([k]) => k);
      presets[name] = { apps: selApps, domains: selDomains };
      await window.pywebview.api.save_preset(name, selApps, selDomains);
      renderPresets();
    });

    modal.querySelector('#selectAllBtn').addEventListener('click', () => {
      Object.values(appVars).forEach((cb) => (cb.checked = true));
      Object.values(domainVars).forEach((cb) => (cb.checked = true));
    });
    modal.querySelector('#selectNoneBtn').addEventListener('click', () => {
      Object.values(appVars).forEach((cb) => (cb.checked = false));
      Object.values(domainVars).forEach((cb) => (cb.checked = false));
    });

    const finish = (val) => { closeModal(modal); resolve(val); };
    modal.querySelector('#selectionCancelBtn').addEventListener('click', () => finish(null));
    modal.querySelector('#selectionContinueBtn').addEventListener('click', () => {
      const selApps = Object.entries(appVars).filter(([, cb]) => cb.checked).map(([k]) => k);
      const selDomains = Object.entries(domainVars).filter(([, cb]) => cb.checked).map(([k]) => k);
      if (selApps.length === 0 && selDomains.length === 0) {
        errorEl.textContent = 'Choose at least one app or website to block.';
        return;
      }
      finish({ apps: selApps, domains: selDomains });
    });
    modal.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') finish(null);
    });
  });
}

// ---------- setup view ----------

function renderHeatmap(container, activityDays) {
  container.innerHTML = '';
  // activityDays: chronological (oldest first), starting on a Monday. The
  // CSS grid uses grid-auto-flow: column with 7 fixed rows, so inserting in
  // this order naturally fills top-to-bottom then wraps to the next column
  // -- i.e. each column is one week, matching a GitHub-style heatmap.
  activityDays.forEach((day) => {
    const cell = el('div', 'cell' + (day.locked ? ' on' : ''));
    container.appendChild(cell);
  });
}

function renderSetup(state) {
  const tpl = document.getElementById('tpl-setup');
  const node = tpl.content.cloneNode(true);

  const stats = state.stats;
  node.querySelector('.streak-line').textContent =
    `\u{1F525} ${stats.streak || 0} in a row   ·   Longest: ${stats.longest_streak || 0}   ·   Total sessions: ${stats.total_sessions || 0}`;

  const weeks = state.activity.weeks;
  const cells = state.activity.cells; // chronological, Monday-first, from python
  renderHeatmap(node.querySelector('.heatmap'), cells);
  node.querySelector('.activity-caption').textContent =
    `${state.activity.locked_count} of the last ${weeks * 7} days locked`;

  APP_ROOT.innerHTML = '';
  APP_ROOT.appendChild(node);

  const daysInput = document.getElementById('daysInput');
  const hoursInput = document.getElementById('hoursInput');
  const minutesInput = document.getElementById('minutesInput');
  const intentInput = document.getElementById('intentInput');

  let selectedApps = state.apps.map(([k]) => k);
  let selectedDomains = state.domains.map(([k]) => k);
  let presets = state.presets;

  document.getElementById('startBlockBtn').addEventListener('click', async () => {
    const result = await openSelectionDialog(state.apps, state.domains, presets, selectedApps, selectedDomains);
    if (!result) return;
    selectedApps = result.apps;
    selectedDomains = result.domains;

    const days = parseInt(daysInput.value, 10) || 0;
    const hours = parseInt(hoursInput.value, 10) || 0;
    const minutes = parseInt(minutesInput.value, 10) || 0;
    if (days === 0 && hours === 0 && minutes === 0) {
      alert('Set a duration greater than zero (days, hours, or minutes).');
      return;
    }

    const preview = await window.pywebview.api.preview_duration(days, hours, minutes);
    const appNames = state.apps.filter(([k]) => selectedApps.includes(k)).map(([, l]) => l);
    const domainNames = state.domains.filter(([k]) => selectedDomains.includes(k)).map(([, l]) => l);
    const durationLabel = [days ? `${days}d` : '', hours ? `${hours}h` : '', minutes ? `${minutes}m` : '']
      .filter(Boolean).join(' ');
    const summary = [
      `Duration: ${durationLabel}, until ${preview.human}`,
      `Apps: ${appNames.join(', ') || '(none)'}`,
      `Websites: ${domainNames.join(', ') || '(none)'}`,
      'This cannot be undone early once engaged.',
    ];

    const password = await openPasswordDialog('Engage Lock', summary, 'LOCK');
    if (!password) return;

    const res = await window.pywebview.api.start_block(
      days, hours, minutes, selectedApps, selectedDomains, intentInput.value.trim(), password
    );
    if (!res.ok) {
      alert('Failed to engage lock: ' + (res.error || 'Unknown error (check sudo password).'));
      return;
    }
    alert(`FocusLock active. Locked until ${res.unlock_human}.`);
    loadState();
  });
}

// ---------- locked view ----------

let countdownTimer = null;

function renderLocked(state) {
  if (countdownTimer) clearInterval(countdownTimer);

  const tpl = document.getElementById('tpl-locked');
  const node = tpl.content.cloneNode(true);

  node.querySelector('.unlock-at').textContent = `Unlocks at: ${state.unlock_at}`;

  if (state.intent) {
    const box = node.querySelector('.intent-card');
    box.style.display = '';
    box.querySelector('.intent-text').textContent = state.intent;
  }

  const listEl = node.querySelector('.blocked-list');
  if (state.blocked_apps.length === 0 && state.blocked_domains.length === 0) {
    listEl.appendChild(el('div', 'row-item', '(none)'));
  } else {
    state.blocked_apps.forEach(([, label]) => {
      const row = el('div', 'row-item');
      row.appendChild(el('span', 'kind', 'App'));
      row.appendChild(el('span', null, label));
      listEl.appendChild(row);
    });
    state.blocked_domains.forEach(([, label]) => {
      const row = el('div', 'row-item');
      row.appendChild(el('span', 'kind', 'Website'));
      row.appendChild(el('span', null, label));
      listEl.appendChild(row);
    });
  }

  const ytArea = node.querySelector('.youtube-area');
  if (state.youtube_available) {
    if (state.youtube_used_today) {
      let msg = "TODAY'S YOUTUBE BREAK ALREADY USED";
      if (state.youtube_reblock_at) msg += ` (RE-BLOCKED AT ${state.youtube_reblock_at.toUpperCase()})`;
      msg += '. RESETS AT MIDNIGHT.';
      ytArea.appendChild(el('div', 'footnote', msg));
    } else {
      const btn = el('button', 'pill pill-cyan', "Use today's YouTube break (1 hour)");
      btn.type = 'button';
      btn.addEventListener('click', async () => {
        const password = await openPasswordDialog(
          'Use YouTube Break',
          [
            'Unblocks YouTube for exactly 1 hour, then re-blocks itself',
            'automatically. Usable once per day. No extensions.',
          ],
          'YOUTUBE1H'
        );
        if (!password) return;
        const res = await window.pywebview.api.youtube_break(password);
        if (!res.ok) {
          alert('Failed: ' + (res.error || 'Unknown error.'));
          return;
        }
        alert(`Re-blocks automatically at ${res.reblock_human}. You can use it again tomorrow.`);
        loadState();
      });
      ytArea.appendChild(btn);
    }
  }

  APP_ROOT.innerHTML = '';
  APP_ROOT.appendChild(node);

  const countdownEl = document.querySelector('.countdown');
  async function tick() {
    const secs = await window.pywebview.api.seconds_until(state.unlock_at);
    if (secs === null) return;
    if (secs <= 0) {
      countdownEl.textContent = 'UNLOCKING...';
      loadState();
      return;
    }
    const d = Math.floor(secs / 86400);
    const h = Math.floor((secs % 86400) / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    countdownEl.textContent = `${d}d ${h}h ${m}m ${s}s`;
  }
  tick();
  countdownTimer = setInterval(tick, 1000);
}

// ---------- boot ----------

async function loadState() {
  const state = await window.pywebview.api.get_state();
  if (state.locked) {
    renderLocked(state);
  } else {
    renderSetup(state);
  }
}

window.addEventListener('pywebviewready', () => {
  initTheme();
  loadState();
  setInterval(async () => {
    // Cheap poll so an externally-fired unlock (systemd timer) flips the
    // view even if you're just sitting on the setup screen.
    const stillLocked = await window.pywebview.api.is_locked();
    if (document.querySelector('.title-pink') && !stillLocked) loadState();
  }, 3000);
});
