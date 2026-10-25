// Shared by popup.js and content_script.js (loaded as a plain script before
// each, not a module, so classic browser-extension script loading works
// without a bundler).
function getVideoIdFromUrl(url) {
  try {
    const u = new URL(url);
    if (u.hostname.endsWith("youtube.com")) {
      if (u.pathname === "/watch") return u.searchParams.get("v");
      const shortsMatch = u.pathname.match(/^\/shorts\/([^/?]+)/);
      if (shortsMatch) return shortsMatch[1];
    }
    if (u.hostname === "youtu.be") {
      return u.pathname.slice(1).split("/")[0] || null;
    }
  } catch (e) {
    // not a valid URL; ignore
  }
  return null;
}
