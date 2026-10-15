'use strict';
(function () {
  function decodeFile(result) {
    if (!result || result.cancelled) return null;
    const file = result.file;
    if (!file || typeof file.base64 !== 'string' || file.base64.length > 20000000 || typeof file.name !== 'string') {
      throw Error('The device did not return a usable local document.');
    }
    let text;
    try { text = atob(file.base64); } catch { throw Error('The selected local document could not be decoded.'); }
    if (text.length > 15000000 || Number(file.bytes) !== text.length) throw Error('The selected local document is incomplete or too large.');
    const bytes = Uint8Array.from(text, character => character.charCodeAt(0));
    return new File([bytes], file.name.replace(/[\\/\u0000-\u001f]/g, '_'), {type:file.mime || 'application/octet-stream'});
  }
  window.taxDecodeNativeFile = decodeFile;
  window.taxNativeSaveFile = async function (blob, name) {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    if (bytes.length > 15000000) throw Error('This export is too large for the device save window.');
    let binary = '';
    for (let start = 0; start < bytes.length; start += 16384) binary += String.fromCharCode(...bytes.subarray(start, start + 16384));
    const encoded = btoa(binary), mime = blob.type || 'application/octet-stream';
    if (window.pywebview?.api?.save_file) return await window.pywebview.api.save_file(name, mime, encoded);
    if (window.TaxRebornIOS?.saveFile) return await window.TaxRebornIOS.saveFile(name, mime, encoded);
    if (window.TaxRebornAndroid?.saveFile) {
      window.TaxRebornAndroid.saveFile(name, mime, encoded);
      return {chooserOpened:true};
    }
    throw Error('A native file save window is unavailable.');
  };
  document.addEventListener('click', async event => {
    const input = event.target.closest?.('input[type="file"]');
    if (!input || !window.TaxRebornIOS?.pickFile) return;
    event.preventDefault(); event.stopImmediatePropagation();
    input.disabled = true;
    try {
      const selected = input.hasAttribute('capture')
        ? await window.TaxRebornIOS.capturePhoto()
        : await window.TaxRebornIOS.pickFile({accept:input.accept || ''});
      const file = decodeFile(selected);
      if (file) {
        const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files;
        input.dispatchEvent(new Event('change', {bubbles:true}));
      }
    } catch (error) {
      if (typeof window.notify === 'function') window.notify(error.message, true);
    } finally { input.disabled = false; }
  }, true);
})();
