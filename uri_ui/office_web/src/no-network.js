// AC15: the page must never reach the network. Layers: the WebView2 host (primary: request filter, navigation and
// new-window refusal), the CSP in index.html, and this module.
// Univer's sheets-core preset always registers @univerjs/network
// (fetch/XHR HTTP implementations and a WebSocket service) and its drawing code downloads images by URL with fetch().
// URI Office uses none of that. This module is imported first by main.js, so it runs before any Univer code, and
// replaces the browser network APIs with versions that allow only in-page data: and blob: URLs. The CSP
// (connect-src 'self') and the host's navigation lockdown are further layers.

const LOCAL = /^(data|blob):/i;

function refuse(what, url) {
  const err = new Error(`URI Office: network access is disabled (${what} ${String(url).slice(0, 60)})`);
  err.name = 'NetworkDisabledError';
  return err;
}

const realFetch = window.fetch.bind(window);
window.fetch = (input, init) => {
  const url = typeof input === 'string' ? input : (input && input.url) || '';
  if (LOCAL.test(url)) return realFetch(input, init);
  return Promise.reject(refuse('fetch', url));
};

window.XMLHttpRequest = class {
  open(method, url) { throw refuse('XMLHttpRequest', url); }
  send() { throw refuse('XMLHttpRequest', ''); }
  abort() {}
  setRequestHeader() {}
  addEventListener() {}
};

window.WebSocket = class {
  constructor(url) { throw refuse('WebSocket', url); }
};

window.EventSource = class {
  constructor(url) { throw refuse('EventSource', url); }
};

if (navigator.sendBeacon) navigator.sendBeacon = () => false;

// The page starts no workers (see index.html); refuse them so a worker can never run outside this module's patches.
window.Worker = class { constructor(url) { throw refuse('Worker', url); } };
window.SharedWorker = class { constructor(url) { throw refuse('SharedWorker', url); } };

// No new windows (the host also refuses them).
window.open = () => null;

// WebRTC can reach the network over UDP, which neither the CSP nor the host request filter sees (the host also
// starts WebView2 with direct UDP disabled). The page has no use for it.
for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'RTCIceTransport']) {
  try { Object.defineProperty(window, name, { value: undefined, configurable: false, writable: false }); } catch (e) {}
}

export const NETWORK_DISABLED = true;
