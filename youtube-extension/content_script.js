// Runs on every youtube.com page. Blocks everything except the video(s) on
// today's pre-approved allowlist, for the duration of that allowlist window.
// This only matters once the OS-level FocusLock break has already unblocked
// the domain -- if the domain itself is blocked (via /etc/hosts), the page
// never loads at all and this script never runs.
const OVERLAY_ID = "focuslock-yt-block-overlay";

function removeOverlay() {
  const el = document.getElementById(OVERLAY_ID);
  if (el) el.remove();
}

function showOverlay(message) {
  if (document.getElementById(OVERLAY_ID)) return;
  const div = document.createElement("div");
  div.id = OVERLAY_ID;
  div.style.cssText = [
    "position:fixed", "inset:0", "z-index:2147483647",
    "background:#0b0b12", "color:#f0f0f5", "display:flex",
    "flex-direction:column", "align-items:center", "justify-content:center",
    "font-family:sans-serif", "text-align:center", "padding:24px",
  ].join(";");
  div.innerHTML =
    '<div style="font-size:40px;margin-bottom:8px;">&#128274;</div>' +
    '<h1 style="font-size:24px;margin:0 0 12px;">FocusLock</h1>' +
    '<p style="max-width:440px;color:#a0a0b0;line-height:1.5;">' + message + "</p>";
  (document.documentElement || document.body).appendChild(div);
  document.querySelectorAll("video").forEach((v) => v.pause());
}

function check() {
  chrome.storage.local.get(["allowedVideoIds", "breakUntil"], (data) => {
    const now = Date.now();
    const active = data.breakUntil && now < data.breakUntil;
    if (!active) {
      showOverlay(
        "Today's YouTube allowlist window isn't active. Open the extension " +
          "popup after your FocusLock daily break to set one."
      );
      return;
    }
    const videoId = getVideoIdFromUrl(location.href);
    const allowed = videoId && (data.allowedVideoIds || []).includes(videoId);
    if (allowed) {
      removeOverlay();
    } else {
      showOverlay(
        "This page isn't on today's allowlist. Only the video(s) you " +
          "pre-approved before this break are watchable this hour."
      );
    }
  });
}

check();
// YouTube is a single-page app; re-check on its own client-side navigations.
document.addEventListener("yt-navigate-finish", check);
// Fallback poll: catches SPA nav events being missed, and catches the
// allowlist window expiring while a video is already playing.
setInterval(check, 3000);
