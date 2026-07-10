#!/usr/bin/env node
// ccstatusline Custom Command widget: show a rate-limit reset time only when
// that window is at/above THRESHOLD% used. Session (5h) and weekly (7d) are
// gated independently; both shown when both qualify.
//
// Primary source: Claude Code's documented statusline stdin
//   (rate_limits.five_hour / rate_limits.seven_day). This is absent until the
//   first API response of a session, so as a fallback we read ccstatusline's
//   own usage cache, which persists across sessions and is kept fresh by the
//   session-usage / weekly-usage widgets.

// todo - maybe make this smarter by incorporating the time remaining.
// like, it doesn't matter if i'm at 90% if the reset is in a few seconds
// maybe maybe i'd still want it just to avoid anxiety
// so maybe always show it above 90%, but below that only show it if likely to get to 90% in time  remaining
// what would be a good way to estimate that?

const fs = require('fs');
const os = require('os');
const path = require('path');

const SESSION_THRESHOLD = 50;
const WEEKLY_THRESHOLD = 75;
const CACHE_FILE = path.join(os.homedir(), '.cache', 'ccstatusline', 'usage.json');

function readStdin() {
    try {
        return fs.readFileSync(0, 'utf8');
    } catch {
        return '';
    }
}

function fmtClock(ms) {
    return new Date(ms)
        .toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
        .replace(' ', '')
        .toLowerCase();
}

function fmtWeekday(ms) {
    return new Date(ms).toLocaleDateString('en-US', { weekday: 'short' });
}

// Normalize a window to { pct, resetMs } or null.
function normalize(pct, resetMs) {
    if (typeof pct !== 'number' || !Number.isFinite(resetMs))
        return null;
    return { pct, resetMs };
}

function fromStdin() {
    let data;
    try {
        data = JSON.parse(readStdin());
    } catch {
        return {};
    }
    const rl = (data && data.rate_limits) || {};
    const sec = w => (w && typeof w.resets_at === 'number' ? w.resets_at * 1000 : NaN);
    return {
        session: rl.five_hour ? normalize(rl.five_hour.used_percentage, sec(rl.five_hour)) : null,
        weekly: rl.seven_day ? normalize(rl.seven_day.used_percentage, sec(rl.seven_day)) : null
    };
}

function fromCache() {
    let c;
    try {
        c = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
    } catch {
        return {};
    }
    return {
        session: normalize(c.sessionUsage, Date.parse(c.sessionResetAt)),
        weekly: normalize(c.weeklyUsage, Date.parse(c.weeklyResetAt))
    };
}

const stdin = fromStdin();
const needsFallback = !stdin.session || !stdin.weekly;
const cache = needsFallback ? fromCache() : {};

const session = stdin.session ?? cache.session ?? null;
const weekly = stdin.weekly ?? cache.weekly ?? null;

// Show only if at/above threshold and the reset is still in the future (guards
// against stale cache whose window has already reset).
function qualifies(w, threshold) {
    return w && w.pct >= threshold && w.resetMs > Date.now();
}

const parts = [];
if (qualifies(session, SESSION_THRESHOLD))
    parts.push(`Session resets ${fmtClock(session.resetMs)}`);
if (qualifies(weekly, WEEKLY_THRESHOLD))
    parts.push(`Weekly resets ${fmtWeekday(weekly.resetMs)} ${fmtClock(weekly.resetMs)}`);

if (parts.length)
    process.stdout.write(parts.join(' · '));
process.exit(0);
