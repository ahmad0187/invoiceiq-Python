// InvoiceIQ dashboard (vanilla JS, no build step).
const $ = (id) => document.getElementById(id);
const state = { status: '', q: '', invoices: [], current: null };
const FIELDS = [
  ['vendor', 'Vendor', 'text', true], ['invoice_number', 'Invoice number', 'text'], ['currency', 'Currency', 'text'],
  ['invoice_date', 'Invoice date', 'date'], ['due_date', 'Due date', 'date'], ['bill_to', 'Bill to', 'text', true],
  ['subtotal', 'Subtotal', 'number'], ['tax', 'Tax', 'number'], ['total', 'Total', 'number'],
];

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (v, cur) => (v == null ? '—' : `${cur ? cur + ' ' : ''}${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
const label = { ready: 'Ready', needs_review: 'Needs review', approved: 'Approved' };

function toast(msg, err = false) {
  const t = $('toast'); t.textContent = msg; t.className = 'toast' + (err ? ' err' : ''); t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 4500);
}

async function load() {
  const all = await api('/api/invoices');
  renderKpis(all);
  const params = new URLSearchParams();
  if (state.status) params.set('status', state.status);
  if (state.q) params.set('q', state.q);
  state.invoices = params.toString() ? await api('/api/invoices?' + params) : all;
  renderRows();
}

function renderKpis(all) {
  const byCur = {};
  all.forEach((i) => { if (i.total != null) byCur[i.currency || '?'] = (byCur[i.currency || '?'] || 0) + i.total; });
  const count = (s) => all.filter((i) => i.status === s).length;
  const issues = all.reduce((n, i) => n + i.issues.filter((x) => x.severity === 'error').length, 0);
  $('kpis').innerHTML = [
    ['Invoices processed', all.length, `${count('approved')} approved`],
    (() => {
      const e = Object.entries(byCur);
      if (e.length <= 1) return ['Total value', e.length ? money(e[0][1], e[0][0]) : '—', 'Across all invoices'];
      return ['Total value', `${e.length} currencies`, e.map(([c, v]) => money(v, c)).join(' · ')];
    })(),
    ['Needs review', count('needs_review'), `${issues} error${issues === 1 ? '' : 's'} found`],
    ['Ready to approve', count('ready'), 'All checks passed'],
  ].map(([l, v, s, unit]) => `<div class="kpi"><div class="l">${l}</div><div class="v">${v}${unit ? ` <span class="muted">${unit}</span>` : ''}</div><div class="s" title="${esc(s)}">${esc(s)}</div></div>`).join('');
}

function renderRows() {
  const rows = state.invoices;
  $('empty').hidden = rows.length > 0;
  $('rows').innerHTML = rows.map((i) => `
    <tr data-id="${i.id}">
      <td><div class="vendor">${esc(i.vendor || 'Unknown vendor')}</div><div class="muted">${esc(i.filename)}</div></td>
      <td class="mono">${esc(i.invoice_number || '—')}</td>
      <td>${esc(i.invoice_date || '—')}</td>
      <td>${esc(i.due_date || '—')}</td>
      <td class="num"><strong>${money(i.total, i.currency)}</strong></td>
      <td><span class="badge b-${i.status}">${label[i.status]}</span>${i.issues.length ? ` <span class="muted">${i.issues.length} issue${i.issues.length > 1 ? 's' : ''}</span>` : ''}</td>
    </tr>`).join('');
}

// ---------------------------------------------------------------- drawer
function openDrawer(inv) {
  state.current = inv;
  $('d-file').textContent = `${inv.filename} · extracted by ${inv.extractor}`;
  $('d-title').textContent = `${inv.vendor || 'Unknown vendor'} ${inv.invoice_number ? '· ' + inv.invoice_number : ''}`;
  $('d-issues').innerHTML = inv.issues.length
    ? inv.issues.map((x) => `<div class="issue ${x.severity}"><b>${x.severity}</b><span>${esc(x.message)}</span></div>`).join('')
    : `<div class="ok-note">${inv.status === 'approved' ? 'Approved.' : 'All checks passed: amounts add up and required fields are present.'}</div>`;
  $('d-form').innerHTML = FIELDS.map(([k, l, t, wide]) =>
    `<label class="${wide ? 'wide' : ''}">${l}<input name="${k}" type="${t}" ${t === 'number' ? 'step="0.01"' : ''} value="${esc(inv[k] ?? '')}"></label>`).join('');
  $('d-items').innerHTML = inv.line_items.length
    ? inv.line_items.map((li) => `<tr><td>${esc(li.description)}</td><td class="num">${li.quantity ?? '—'}</td><td class="num">${money(li.unit_price)}</td><td class="num">${money(li.amount)}</td></tr>`).join('')
    : '<tr><td colspan="4" class="muted">No line items found.</td></tr>';
  $('d-pdf').href = `/api/invoices/${inv.id}/file`;
  $('d-approve').disabled = inv.status === 'approved' || inv.issues.some((x) => x.severity === 'error');
  $('drawer').classList.add('open'); $('drawer').setAttribute('aria-hidden', 'false'); $('scrim').hidden = false;
}
function closeDrawer() { $('drawer').classList.remove('open'); $('drawer').setAttribute('aria-hidden', 'true'); $('scrim').hidden = true; state.current = null; }

$('rows').addEventListener('click', async (e) => {
  const id = e.target.closest('tr')?.dataset.id;
  if (id) openDrawer(await api(`/api/invoices/${id}`));
});
$('d-close').onclick = closeDrawer; $('scrim').onclick = closeDrawer;
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });

$('d-save').onclick = async () => {
  const body = {};
  new FormData($('d-form')).forEach((v, k) => {
    const t = FIELDS.find((f) => f[0] === k)[2];
    body[k] = v === '' ? null : t === 'number' ? Number(v) : v;
  });
  try {
    const inv = await api(`/api/invoices/${state.current.id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    openDrawer(inv); toast('Saved and re-checked.'); load();
  } catch (err) { toast(err.message, true); }
};
$('d-approve').onclick = async () => {
  try { openDrawer(await api(`/api/invoices/${state.current.id}/approve`, { method: 'POST' })); toast('Invoice approved.'); load(); }
  catch (err) { toast(err.message, true); }
};
$('d-delete').onclick = async () => {
  if (!confirm('Delete this invoice and its PDF?')) return;
  await api(`/api/invoices/${state.current.id}`, { method: 'DELETE' }); closeDrawer(); toast('Deleted.'); load();
};

// ---------------------------------------------------------------- upload + filters
async function upload(files) {
  const pdfs = [...files].filter((f) => /\.pdf$/i.test(f.name));
  if (!pdfs.length) return toast('Choose PDF files.', true);
  const fd = new FormData(); pdfs.forEach((f) => fd.append('files', f));
  toast(`Extracting ${pdfs.length} invoice${pdfs.length > 1 ? 's' : ''}…`);
  try {
    const out = await api('/api/invoices', { method: 'POST', body: fd });
    const flagged = out.filter((i) => i.issues.length).length;
    toast(`${out.length} processed${flagged ? `, ${flagged} need review` : ', all checks passed'}.`);
    load();
  } catch (err) { toast(err.message, true); }
}
$('file').onchange = (e) => { upload(e.target.files); e.target.value = ''; };
const drop = $('drop');
['dragenter', 'dragover'].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', (e) => upload(e.dataTransfer.files));

$('tabs').addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  [...$('tabs').children].forEach((x) => x.classList.toggle('on', x === b));
  state.status = b.dataset.status; load();
});
let t; $('search').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); load(); }, 250); });

load().catch((e) => toast(e.message, true));
