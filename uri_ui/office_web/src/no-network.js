// AC15: the page must never reach the network. Univer's sheets-core preset always registers @univerjs/network
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

export const NETWORK_DISABLED = true;
