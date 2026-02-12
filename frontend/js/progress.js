/**
 * progress.js — Fetches and displays learning progress in the sidebar.
 */

/** Fetch progress from API and update the sidebar UI. */
async function refreshProgress() {
    try {
        const res = await fetch(`${API}/api/progress`);
        const data = await res.json();

        // Update progress bar
        const total = data.total_concepts || 0;
        const mastered = data.mastered_count || 0;
        const pct = total > 0 ? Math.round((mastered / total) * 100) : 0;

        document.getElementById('progress-bar').style.width = `${pct}%`;
        document.getElementById('progress-count').textContent = `${mastered} / ${total}`;

        // Update current topic label
        const label = document.getElementById('current-topic-label');
        if (data.current_concept) {
            label.textContent = `Now learning: ${data.current_concept}`;
        } else if (data.target_topic) {
            label.textContent = `Topic: ${data.target_topic}`;
        } else {
            label.textContent = '';
        }

        // Update header
        if (data.target_topic) {
            document.getElementById('header-title').textContent = data.target_topic;
            const status = data.waiting_for_synthesis ? 'Synthesis question' : `Step ${data.current_index + 1} of ${total}`;
            document.getElementById('header-subtitle').textContent = status;
        }
    } catch (e) {
        console.error('Progress fetch error:', e);
    }
}
