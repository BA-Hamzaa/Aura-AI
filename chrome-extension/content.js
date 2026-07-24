/**
 * content.js — Meeting Detection Script
 * Injected into Zoom, Google Meet, Teams, Discord pages.
 * Detects when a meeting starts/ends and notifies the AI backend.
 */

const BACKEND = "http://localhost:8000";

// ─── Platform Detection ────────────────────────────────────────────────────────

function detectPlatform() {
  const host = window.location.hostname;
  if (host.includes("meet.google.com")) return "Google Meet";
  if (host.includes("zoom.us"))         return "Zoom";
  if (host.includes("teams.microsoft")) return "Microsoft Teams";
  if (host.includes("discord.com"))     return "Discord";
  return "Unknown";
}

function getMeetingTitle() {
  const platform = detectPlatform();
  // Try to extract a meaningful title
  const titleSelectors = [
    "title",                                    // page title
    "[data-meeting-title]",                     // Teams
    ".r6xAKc",                                  // Google Meet code
    ".gWSNeD",                                  // Google Meet title
    "#meeting-name-container",                  // Zoom
    ".chat-header__title",                      // Discord
  ];

  for (const sel of titleSelectors) {
    const el = sel === "title" ? document : document.querySelector(sel);
    if (el && el.textContent && el.textContent.trim()) {
      const text = (sel === "title" ? document.title : el.textContent).trim();
      if (text && text.length > 2) return text;
    }
  }
  return `${platform} Meeting`;
}

// ─── Notify Backend ────────────────────────────────────────────────────────────

async function notifyMeetingStarted() {
  const platform = detectPlatform();
  const title = getMeetingTitle();

  try {
    await fetch(`${BACKEND}/api/meeting/context`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, platform }),
    });
    console.log(`[AI Assistant] Meeting detected: ${platform} — ${title}`);
  } catch (e) {
    console.log("[AI Assistant] Backend not reachable:", e.message);
  }
}

// ─── Meeting Detection Logic ───────────────────────────────────────────────────

let meetingActive = false;
let notifyTimeout = null;

function checkMeetingActive() {
  const platform = detectPlatform();
  let isInMeeting = false;

  if (platform === "Google Meet") {
    // Google Meet: check for mute/camera buttons presence
    isInMeeting = !!(
      document.querySelector('[data-is-muted]') ||
      document.querySelector('[aria-label*="microphone"]') ||
      document.querySelector('[jsname="BOHaEe"]')
    );
  } else if (platform === "Zoom") {
    isInMeeting = window.location.pathname.includes("/wc/") ||
                  !!document.querySelector("#wc-container-right");
  } else if (platform === "Microsoft Teams") {
    isInMeeting = !!document.querySelector("[data-tid='calling-screen']") ||
                  window.location.href.includes("callId");
  } else if (platform === "Discord") {
    isInMeeting = !!document.querySelector("[class*='rtc-connection']") ||
                  !!document.querySelector("[aria-label*='voice connected']");
  } else {
    // Generic: URL has meeting/call indicators
    isInMeeting = /\/(meet|call|room|conf|join|video)/.test(window.location.pathname);
  }

  if (isInMeeting && !meetingActive) {
    meetingActive = true;
    clearTimeout(notifyTimeout);
    notifyTimeout = setTimeout(notifyMeetingStarted, 2000); // wait 2s for page to settle
  } else if (!isInMeeting && meetingActive) {
    meetingActive = false;
    console.log("[AI Assistant] Meeting ended");
  }
}

// Poll every 3 seconds for meeting state changes
setInterval(checkMeetingActive, 3000);
checkMeetingActive(); // initial check

// Also fire on URL changes (SPA navigation)
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    setTimeout(checkMeetingActive, 1000);
  }
}).observe(document, { subtree: true, childList: true });
