function render() {
  chrome.storage.local.get(["allowedVideoIds", "breakUntil"], (data) => {
    const now = Date.now();
    const statusEl = document.getElementById("status");
    const setupEl = document.getElementById("setup");
    const active = data.breakUntil && now < data.breakUntil;
    if (active) {
      const mins = Math.ceil((data.breakUntil - now) / 60000);
      const n = (data.allowedVideoIds || []).length;
      statusEl.textContent = `Active: ${n} video(s) allowed, ${mins} min left.`;
      statusEl.className = "active";
      setupEl.style.display = "none";
    } else {
      statusEl.textContent = "No active allowlist.";
      statusEl.className = "";
      setupEl.style.display = "block";
    }
  });
}

document.getElementById("startBtn").addEventListener("click", () => {
  const text = document.getElementById("urls").value;
  const ids = text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map(getVideoIdFromUrl)
    .filter(Boolean);
  if (ids.length === 0) {
    alert("Paste at least one valid YouTube video URL.");
    return;
  }
  const breakUntil = Date.now() + 60 * 60 * 1000;
  chrome.storage.local.set({ allowedVideoIds: ids, breakUntil }, render);
});

render();
setInterval(render, 5000);
