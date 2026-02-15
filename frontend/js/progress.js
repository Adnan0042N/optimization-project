/**
 * progress.js — Fetches and displays learning progress in the sidebar.
 * Updated: reads from localStorage session instead of /api/progress.
 */

/** Refresh progress from the current session in localStorage. */
function refreshProgressFromSession() {
    const session = getCurrentSession();

    const total = session.teachingOrder ? session.teachingOrder.length : 0;
    const currentIndex = session.currentIndex || 0;
    const mastered = Math.min(currentIndex, total);
    const pct = total > 0 ? Math.round((mastered / total) * 100) : 0;

    document.getElementById('progress-bar').style.width = `${pct}%`;
    document.getElementById('progress-count').textContent = `${mastered} / ${total}`;

    // Update current topic label
    const label = document.getElementById('current-topic-label');
    if (session.teachingOrder && currentIndex < total) {
        const current = session.teachingOrder[currentIndex];
        const name = typeof current === 'string' ? current : current.topic;
        label.textContent = `Now learning: ${name}`;
    } else if (session.targetTopic) {
        label.textContent = `Topic: ${session.targetTopic}`;
    } else {
        label.textContent = '';
    }

    // Update header
    if (session.targetTopic) {
        document.getElementById('header-title').textContent = session.targetTopic;
        const status = session.waitingForSynthesis ? 'Synthesis question' : `Step ${currentIndex + 1} of ${total}`;
        document.getElementById('header-subtitle').textContent = status;
    }
}

/** Legacy alias for compatibility. */
function refreshProgress() {
    refreshProgressFromSession();
}

/** Check and show review due banner. */
function refreshReviewBanner() {
    const due = getReviewDueConcepts();
    const banner = document.getElementById('review-banner');
    const countEl = document.getElementById('review-count');

    if (due.length > 0) {
        banner.classList.remove('hidden');
        countEl.textContent = `${due.length} concept${due.length > 1 ? 's' : ''} due for review`;
    } else {
        banner.classList.add('hidden');
    }
}
