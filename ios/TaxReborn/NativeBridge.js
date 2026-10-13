'use strict';
(() => {
  if (location.origin !== 'http://127.0.0.1:18786' || window !== window.top) return;
  let sequence = 0;
  const pending = new Map();
  function request(action, payload = {}) {
    const id = String(++sequence);
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {pending.delete(id); reject(Error('The native file operation timed out.'));}, 300000);
      pending.set(id, {resolve, reject, timeout});
      window.webkit.messageHandlers.taxReborn.postMessage({id, action, ...payload});
    });
  }
  Object.defineProperty(window, 'TaxRebornIOS', {value: Object.freeze({
    saveFile: (filename, mime, base64) => request('saveFile', {filename, mime, base64}),
    pickFile: (options = {}) => request('pickFile', {accept: options.accept || ''}),
    pickPhoto: () => request('pickPhoto'),
    capturePhoto: () => request('capturePhoto'),
    platform: 'ios', version: 1
  }), writable: false});
  window.__taxRebornNativeReply = message => {
    const item = pending.get(message.id);
    if (!item) return;
    clearTimeout(item.timeout); pending.delete(message.id);
    message.error ? item.reject(Error(message.error)) : item.resolve(message.result);
  };
})();
