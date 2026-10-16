
const canonical = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const clone = value => JSON.parse(canonical(value));
const digest = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
const decode = value => Uint8Array.from(atob(value), char => char.charCodeAt(0));
const node = (tag, text, attrs = {}) => { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; Object.assign(element, attrs); return element; };

export function createNormalizedStoreWorker() {
  const worker = new Worker(new URL('./app38-normalized-store-worker.js', import.meta.url));
  const pending = new Map(); let sequence = 0, closed = false;
  worker.onmessage = ({data}) => { const item = pending.get(data.id); if (!item) return; pending.delete(data.id); clearTimeout(item.timer); data.error ? item.reject(Error(data.error)) : item.resolve(data.result); };
  worker.onerror = event => { for (const item of pending.values()) { clearTimeout(item.timer); item.reject(Error(event.message || 'Normalized source worker failed.')); } pending.clear(); };
  return {run(command, payload) { if (closed) return Promise.reject(Error('Normalized source worker is closed.')); return new Promise((resolve, reject) => { const id = ++sequence; const timer = setTimeout(() => { pending.delete(id); reject(Error('The normalized source operation timed out.')); }, 180000); pending.set(id, {resolve, reject, timer}); worker.postMessage({id, command, payload}); });}, close() { closed = true; worker.terminate(); for (const item of pending.values()) { clearTimeout(item.timer); item.reject(Error('Normalized source worker closed.')); } pending.clear(); }};
}

export function mountNormalizedStore(container, {execute, getSource, saveReport = null, saveSource = null} = {}) {
  if (!container || typeof execute !== 'function' || typeof getSource !== 'function') throw Error('A local normalized-source adapter is required.');
  if (saveReport !== null && typeof saveReport !== 'function' || saveSource !== null && typeof saveSource !== 'function') throw Error('A valid local save adapter is required.');
  let closed = false, busy = false, result = null, sourceRequest = null, outputRequest = null;
  const root = node('section'); root.className = 'source-normalized-store';
  root.append(
    node('h3', 'Save a normalized copy of this source'),
    node('p', 'This creates a complete local copy of the selected source and checks it again after download. The current return and original source stay unchanged.'),
  );
  const acknowledge = node('input', undefined, {type: 'checkbox'});
  const ackLabel = node('label'); ackLabel.className = 'check-field'; ackLabel.append(acknowledge, node('span', 'I understand this is a separate source copy. It does not recalculate the current return.'));
  const run = node('button', 'Create normalized source copy', {type: 'button', className: 'button primary'});
  const save = node('button', 'Save normalized .taxbin', {type: 'button', className: 'button secondary', disabled: true});
  const saveAudit = node('button', 'Save readback report', {type: 'button', className: 'button secondary', disabled: true});
  const status = node('p', 'Review the scope, then create the copy.', {role: 'status'});
  const error = node('p', '', {role: 'alert', className: 'dialog-error'});
  const output = node('div');
  const details = node('details'); details.append(node('summary', 'Developer validation details'));
  root.append(ackLabel, node('div', undefined, {className: 'inline-actions'}), status, error, output, details);
  const actions = root.querySelector('.inline-actions'); actions.append(run, save, saveAudit); container.append(root);
  const setBusy = value => { busy = value; run.disabled = value || !acknowledge.checked; acknowledge.disabled = value; save.disabled = value || !result; saveAudit.disabled = value || !result; };
  acknowledge.onchange = () => { if (!busy) setBusy(false); };
  const fail = issue => { if (closed) return; result = null; output.replaceChildren(); details.replaceChildren(node('summary', 'Developer validation details')); error.textContent = String(issue?.message || issue); status.textContent = 'No source or current return values were changed.'; setBusy(false); };
  run.onclick = async () => {
    if (closed || busy) return;
    if (!acknowledge.checked) { error.textContent = 'Confirm the separate-copy scope first.'; return; }
    setBusy(true); error.textContent = ''; output.replaceChildren(); details.replaceChildren(node('summary', 'Developer validation details')); status.textContent = 'Reading the complete source and checking its supported document structure…';
    try {
      const request = clone(getSource());
      if (request?.container !== 'binary_entity' || !request.profile || !Array.isArray(request.carriers)) throw Error('Open and inspect one complete binary source first.');
      const sourceBytes = decode(request.base64); request.sha256 = await digest(sourceBytes); sourceRequest = request;
      const normalized = await execute('app38_normalize', {source: request});
      const normalizedBytes = decode(normalized.normalized_source.base64);
      if (normalizedBytes.length !== normalized.normalized_source.bytes || await digest(normalizedBytes) !== normalized.normalized_source.sha256) throw Error('The normalized source identity check failed.');
      outputRequest = {source: {...clone(request), base64: normalized.normalized_source.base64, sha256: normalized.normalized_source.sha256}};
      status.textContent = 'The normalized source was created. Running a fresh independent readback…';
      const fresh = await execute('app38_fresh_read', outputRequest);
      if (!fresh.readback?.whole_document_readback || fresh.readback.document_sha256 !== normalized.normalized_source.sha256 || fresh.native_Load_executed || fresh.native_FixupFields_executed) throw Error('The downloaded source did not pass independent full readback.');
      result = {format: 'tax-reborn-normalized-store-app38-receipt-v1', source: normalized.source, normalized_source: {sha256: normalized.normalized_source.sha256, bytes: normalized.normalized_source.bytes}, normalization: normalized.readback, fresh_readback: fresh.readback, native_Load_executed: false, native_FixupFields_executed: false, original_execution_count: 0};
      output.append(node('p', `Complete normalized source ready · ${normalized.normalized_source.bytes} bytes · ${normalized.normalized_source.sha256}`), node('p', `Fresh readback confirmed ${fresh.readback.form_count} form(s) and the exact downloaded bytes.`));
      details.append(node('pre', JSON.stringify(result, null, 2)));
      status.textContent = 'Readback passed. Save the source copy and report if you need them outside this return.';
    } catch (issue) { fail(issue); }
    finally { if (!closed) setBusy(false); }
  };
  save.onclick = async () => {
    if (!result || !outputRequest) return;
    try {
      const bytes = decode(outputRequest.source.base64), blob = new Blob([bytes], {type: 'application/octet-stream'});
      if (saveSource) await saveSource(blob, 'Tax-Reborn-normalized-source.taxbin'); else { const a = node('a'); a.href = URL.createObjectURL(blob); a.download = 'Tax-Reborn-normalized-source.taxbin'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }
      status.textContent = 'Normalized source save requested. The current return and original source remain unchanged.';
    } catch (issue) { fail(issue); }
  };
  saveAudit.onclick = async () => {
    if (!result) return;
    try {
      const blob = new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'});
      if (saveReport) await saveReport(blob, 'Tax-Reborn-normalized-source-readback.json'); else { const a = node('a'); a.href = URL.createObjectURL(blob); a.download = 'Tax-Reborn-normalized-source-readback.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }
      status.textContent = 'Readback report save requested.';
    } catch (issue) { fail(issue); }
  };
  setBusy(false);
  return {destroy() { if (closed) return; closed = true; container.replaceChildren(); }, getResult() { return result ? clone(result) : null; }};
}
