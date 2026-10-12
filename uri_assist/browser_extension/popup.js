// Opening this popup by clicking the extension grants activeTab for the current tab only (Chrome's own consent).
// The snapshot is shown as a summary; it is not sent anywhere in A0.
document.getElementById("share").addEventListener("click", async () => {
  const out = document.getElementById("out");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["snapshot.js"] });
    const s = res.result;
    out.textContent = `Read: "${s.title}"\nFields: ${s.fields.length} (private: ${s.fields.filter(f => f.sensitive).length})\n` +
      `Text: ${s.text.length} characters\nRemoved in page: ${JSON.stringify(s.redactions)}`;
  } catch (e) {
    out.textContent = "This page can't be read (browser pages and the Web Store are off-limits).";
  }
});
