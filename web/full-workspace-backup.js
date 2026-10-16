// Local-only full workspace backup contract. It includes return sections and
// every IndexedDB document/binding blob; it never sends data to a service.
const MAX_ENTRY_BYTES = 50 * 1024 * 1024, MAX_TOTAL_BYTES = 250 * 1024 * 1024;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const bytes = value => value instanceof Uint8Array ? value : value instanceof ArrayBuffer ? new Uint8Array(value) : null;
const safePart = value => { const text = String(value ?? ''); if (!text || text === '.' || text === '..' || /[\\/\0]/.test(text) || text.length > 200) throw Error('Backup path component is unsafe.'); return text; };
const encode = value => { let out = ''; for (let i = 0; i < value.length; i += 16384) out += String.fromCharCode(...value.subarray(i, i + 16384)); return btoa(out); };
const decode = value => Uint8Array.from(atob(value), c => c.charCodeAt(0));
const jsonBytes = value => new TextEncoder().encode(JSON.stringify(value));
const digest = async value => [...new Uint8Array(await crypto.subtle.digest('SHA-256', value))].map(x => x.toString(16).padStart(2, '0')).join('');
async function payload(value) { if (value instanceof Blob) return new Uint8Array(await value.arrayBuffer()); const result = bytes(value); if (result) return result; throw Error('Backup blob is not readable.'); }

export async function createWorkspaceBackup({returns = [], workspace = null, documents = []} = {}) {
  if (!Array.isArray(returns) || !Array.isArray(documents)) throw Error('Backup inputs must be arrays.');
  const files = [], seen = new Set(), add = async (path, kind, value, ids = {}) => {
    if (seen.has(path)) throw Error('Duplicate backup path: ' + path); seen.add(path); const raw = await payload(value);
    if (raw.length > MAX_ENTRY_BYTES) throw Error('Backup entry exceeds the local size limit.');
    files.push({path, kind, ...ids, bytes: raw.length, sha256: await digest(raw), base64: encode(raw)});
  };
  for (const record of returns) {
    if (!record || !UUID.test(record.id)) throw Error('Every saved return needs a UUIDv4.');
    const root = 'returns/' + safePart(record.id), sections = {record, metadata: record.metadata ?? {}, states: record.states ?? {}, data: record.data ?? {}, result: record.result ?? {}};
    for (const [section, value] of Object.entries(sections)) await add(`${root}/${section}.json`, section, jsonBytes(value), {return_id: record.id});
  }
  if (workspace !== null) await add('workspace/active.json', 'unsaved_workspace', jsonBytes(workspace), {workspace_id: 'active'});
  for (const row of documents) {
    if (!row || !UUID.test(row.id) || !UUID.test(row.returnId)) throw Error('Every document needs UUID return and document IDs.');
    const root = `returns/${safePart(row.returnId)}/documents/${safePart(row.id)}`, name = safePart(row.name || 'document.bin');
    await add(`${root}/blob/${name}`, 'document_blob', row.file, {return_id: row.returnId, document_id: row.id, mime: row.type || 'application/octet-stream'});
    await add(`${root}/metadata.json`, 'document_metadata', jsonBytes({...row, file: undefined, binding_files: undefined}), {return_id: row.returnId, document_id: row.id});
    const bindings = row.binding_files || {}, profile = bindings.profile, carriers = Array.isArray(bindings.carriers) ? bindings.carriers : [];
    if (profile) await add(`${root}/binding/profile`, 'source_profile', profile, {return_id: row.returnId, document_id: row.id});
    for (let index = 0; index < carriers.length; index++) await add(`${root}/binding/carrier-${index}`, 'source_carrier', carriers[index], {return_id: row.returnId, document_id: row.id, carrier_index: index});
  }
  const total = files.reduce((sum, file) => sum + file.bytes, 0); if (total > MAX_TOTAL_BYTES) throw Error('Full workspace backup exceeds the local size limit.');
  const manifest = files.map(({path, kind, return_id, document_id, workspace_id, carrier_index, mime, bytes, sha256}) => ({path, kind, ...(return_id ? {return_id} : {}), ...(document_id ? {document_id} : {}), ...(workspace_id ? {workspace_id} : {}), ...(carrier_index !== undefined ? {carrier_index} : {}), ...(mime ? {mime} : {}), bytes, sha256}));
  return {format: 'tax-reborn-full-workspace-v1', created_at_utc: new Date().toISOString(), entry_count: files.length, total_bytes: total, manifest, files};
}

export async function verifyWorkspaceBackup(backup) {
  if (!backup || backup.format !== 'tax-reborn-full-workspace-v1' || !Array.isArray(backup.manifest) || !Array.isArray(backup.files) || backup.entry_count !== backup.files.length || backup.manifest.length !== backup.files.length) throw Error('Unsupported or incomplete full workspace backup.');
  const paths = new Set(), checked = []; let total = 0;
  for (const [index, file] of backup.files.entries()) {
    if (!file || typeof file.path !== 'string' || paths.has(file.path)) throw Error('Backup contains a duplicate or missing path.'); paths.add(file.path);
    const raw = decode(file.base64); if (raw.length !== file.bytes || raw.length > MAX_ENTRY_BYTES || await digest(raw) !== file.sha256) throw Error('Backup entry hash or size check failed: ' + file.path);
    const expected = backup.manifest[index]; if (!expected || JSON.stringify({...expected}) !== JSON.stringify(Object.fromEntries(Object.entries(file).filter(([key]) => !['base64'].includes(key))))) throw Error('Backup manifest does not match its payload.');
    total += raw.length; checked.push({path: file.path, bytes: raw.length, sha256: file.sha256});
  }
  if (total !== backup.total_bytes || total > MAX_TOTAL_BYTES) throw Error('Backup total size is invalid.');
  return {all_passed: true, entry_count: checked.length, total_bytes: total, entries: checked};
}

export async function planWorkspaceRestore(backup, {newReturnId = crypto.randomUUID(), newWorkspaceId = crypto.randomUUID()} = {}) {
  await verifyWorkspaceBackup(backup); if (!UUID.test(newReturnId) || !UUID.test(newWorkspaceId)) throw Error('Restore target IDs must be UUIDv4.');
  const returnIds = [...new Set(backup.files.filter(file => file.return_id).map(file => file.return_id))], documentIds = [...new Set(backup.files.filter(file => file.document_id).map(file => file.document_id))];
  return {all_passed: true, mode: 'restore as new local workspace', return_id_map: Object.fromEntries(returnIds.map(id => [id, crypto.randomUUID()])), document_id_map: Object.fromEntries(documentIds.map(id => [id, crypto.randomUUID()])), workspace_id: newWorkspaceId, source_and_attachment_bytes_verified: true};
}

export const workspaceBackupLimits = {MAX_ENTRY_BYTES, MAX_TOTAL_BYTES};
