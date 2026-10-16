import assert from 'node:assert/strict';
const {createWorkspaceBackup, verifyWorkspaceBackup, planWorkspaceRestore} = await import('../web/full-workspace-backup.js');
const id = '00000000-0000-4000-8000-000000000001', doc = '00000000-0000-4000-8000-000000000002';
const backup = await createWorkspaceBackup({returns: [{id, data: {tax_year: 2025}, metadata: {source: 'own'}, states: {ca: {jurisdiction: 'ca'}}, result: {}}], workspace: {returnId: id, dirty: true}, documents: [{id: doc, returnId: id, name: 'camera.jpg', type: 'image/jpeg', file: new Uint8Array([1, 2, 3]), binding_files: {profile: new Uint8Array([4]), carriers: [new Uint8Array([5, 6])]}}]});
assert.equal(backup.format, 'tax-reborn-full-workspace-v1'); assert.equal(backup.entry_count, 10); assert.equal((await verifyWorkspaceBackup(backup)).all_passed, true);
const plan = await planWorkspaceRestore(backup); assert.equal(plan.all_passed, true); assert.notEqual(plan.return_id_map[id], id); assert.notEqual(plan.document_id_map[doc], doc);
const tampered = structuredClone(backup); tampered.files[0].base64 = 'AA=='; await assert.rejects(() => verifyWorkspaceBackup(tampered), /hash or size/);
const duplicate = structuredClone(backup); duplicate.files[1].path = duplicate.files[0].path; await assert.rejects(() => verifyWorkspaceBackup(duplicate), /duplicate/);
console.log(JSON.stringify({all_passed: true, entry_count: backup.entry_count, total_bytes: backup.total_bytes, attachments: 1, source_binding_files: 2}));
