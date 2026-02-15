/**
 * memory-store.js — Global memory + spaced repetition logic using localStorage.
 * This is the equivalent of memory.md — tracks all concepts across all sessions.
 * Also manages daily logs (daily-YYYY-MM-DD equivalent).
 */

const MEMORY_KEY = 'learnbot_memory';      // { concepts: { concept_id: {...} } }
const DAILY_PREFIX = 'learnbot_daily_';     // learnbot_daily_2026-02-15 → {entries: [...]}

// ── Memory (Concept Records) ─────────────────────────────────────────

/** Get the full memory object. */
function getMemory() {
    try {
        return JSON.parse(localStorage.getItem(MEMORY_KEY) || '{"concepts":{}}');
    } catch {
        return { concepts: {} };
    }
}

/** Save the full memory object. */
function saveMemory(memory) {
    localStorage.setItem(MEMORY_KEY, JSON.stringify(memory));
}

/** Get a single concept record. Returns null if not found. */
function getConcept(conceptId) {
    const memory = getMemory();
    return memory.concepts[conceptId] || null;
}

/** Create or update a concept record. */
function upsertConcept(conceptId, data) {
    const memory = getMemory();
    const existing = memory.concepts[conceptId];

    if (existing) {
        Object.assign(existing, data);
    } else {
        const today = _todayISO();
        memory.concepts[conceptId] = {
            concept_id: conceptId,
            name: data.name || conceptId,
            first_learned: today,
            last_reviewed: today,
            repetition: 0,
            ease: 1.0,
            next_review: _addDays(today, 7),
            mastered: false,
            correct_streak: 0,
            ...data,
        };
    }

    saveMemory(memory);
    return memory.concepts[conceptId];
}

/** Ensure a concept exists in memory. Create with defaults if it doesn't. */
function ensureConcept(conceptId, name) {
    if (!getConcept(conceptId)) {
        upsertConcept(conceptId, { name });
    }
    return getConcept(conceptId);
}

/**
 * Update a concept after a review / check question.
 * Applies the spaced repetition formula (no response time — only correctness).
 *
 * SUCCESS:
 *   repetition += 1
 *   ease = min(ease + 0.1, 2.0)
 *   interval = 7 * repetition * ease
 *   next_review = today + interval
 *
 * FAIL:
 *   repetition = max(repetition - 1, 0)
 *   ease = max(ease - 0.1, 0.5)
 *   interval = 7 * max(repetition, 1) * ease
 *   next_review = today + interval
 */
function updateConceptAfterReview(conceptId, wasCorrect) {
    const memory = getMemory();
    const concept = memory.concepts[conceptId];
    if (!concept) return null;

    const today = _todayISO();

    if (wasCorrect) {
        concept.repetition += 1;
        concept.ease = Math.min(concept.ease + 0.1, 2.0);
        concept.correct_streak += 1;
    } else {
        concept.repetition = Math.max(concept.repetition - 1, 0);
        concept.ease = Math.max(concept.ease - 0.1, 0.5);
        concept.correct_streak = 0;
    }

    const rep = wasCorrect ? concept.repetition : Math.max(concept.repetition, 1);
    const intervalDays = Math.round(7 * rep * concept.ease);

    concept.last_reviewed = today;
    concept.next_review = _addDays(today, intervalDays);

    // Check mastery: correct 2 times in a row within last 30 days
    if (concept.correct_streak >= 2 && _daysBetween(concept.first_learned, today) <= 30) {
        concept.mastered = true;
    }

    saveMemory(memory);
    return concept;
}

/** Get all concepts due for review today. */
function getReviewDueConcepts() {
    const memory = getMemory();
    const today = _todayISO();
    const due = [];

    for (const [id, concept] of Object.entries(memory.concepts)) {
        if (concept.next_review <= today && !concept.mastered) {
            due.push(concept);
        }
    }

    return due;
}

/** Get all concepts (for display). */
function getAllConcepts() {
    const memory = getMemory();
    return Object.values(memory.concepts);
}

/** Get mastered concept IDs as a Set of lowercase strings. */
function getMasteredConceptIds() {
    const memory = getMemory();
    const mastered = new Set();
    for (const [id, concept] of Object.entries(memory.concepts)) {
        if (concept.mastered) {
            mastered.add(id.toLowerCase());
        }
    }
    return mastered;
}

// ── Daily Log ────────────────────────────────────────────────────────

/** Get today's daily log. */
function getDailyLog(date) {
    const key = DAILY_PREFIX + (date || _todayISO());
    try {
        return JSON.parse(localStorage.getItem(key) || '{"entries":[]}');
    } catch {
        return { entries: [] };
    }
}

/** Save a daily log for a specific date. */
function saveDailyLog(date, data) {
    const key = DAILY_PREFIX + (date || _todayISO());
    localStorage.setItem(key, JSON.stringify(data));
}

/** Log a concept interaction to today's daily log. */
function logDailyEntry(conceptId, sessionId, turnNumber) {
    const today = _todayISO();
    const log = getDailyLog(today);

    log.entries.push({
        concept_id: conceptId,
        session_id: sessionId,
        turn: turnNumber,
        timestamp: _nowISO(),
    });

    saveDailyLog(today, log);
}

// ── Recall Support: Search Past Explanations ─────────────────────────

/**
 * Search past sessions for the best explanation of a concept.
 * Looks through all sessions' conversationTurns for matching concept_id.
 * Scores by: correct (1.0 base), recency bonus (0.3 max).
 * Returns the best past turn or null.
 */
function findBestPastExplanation(targetConceptId) {
    const sessions = _getAllSessions();
    const candidates = [];
    const today = new Date();

    for (const session of Object.values(sessions)) {
        if (!session.conversationTurns) continue;

        for (const turn of session.conversationTurns) {
            if (!turn.concepts || !turn.concepts.includes(targetConceptId)) continue;

            let score = 0;

            // Base score: correct = 1.0, incorrect = 0.0
            if (turn.correct === true) {
                score += 1.0;
            }

            // Recency bonus: up to 0.3 for recent (within 90 days)
            if (turn.timestamp) {
                const turnDate = new Date(turn.timestamp);
                const daysDiff = (today - turnDate) / (1000 * 60 * 60 * 24);
                if (daysDiff <= 90) {
                    score += 0.3 * (1 - daysDiff / 90);
                }
            }

            candidates.push({
                score,
                turn,
                sessionId: session.id,
                sessionTitle: session.title,
            });
        }
    }

    if (candidates.length === 0) return null;

    // Sort by score descending
    candidates.sort((a, b) => b.score - a.score);
    return candidates[0];
}

// ── Memory Panel Rendering ───────────────────────────────────────────

/** Render memory data into the sidebar panels. */
function refreshMemoryPanel() {
    const memEl = document.getElementById('memory-content');
    const dailyEl = document.getElementById('daily-content');
    const convEl = document.getElementById('conversation-content');

    // Memory.md equivalent
    if (memEl) {
        const memory = getMemory();
        const concepts = Object.values(memory.concepts);
        if (concepts.length === 0) {
            memEl.textContent = '(no concepts learned yet)';
        } else {
            let text = '';
            for (const c of concepts) {
                text += `## ${c.concept_id}\n`;
                text += `name: ${c.name}\n`;
                text += `first_learned: ${c.first_learned}\n`;
                text += `last_reviewed: ${c.last_reviewed}\n`;
                text += `repetition: ${c.repetition}\n`;
                text += `ease: ${c.ease.toFixed(1)}\n`;
                text += `next_review: ${c.next_review}\n`;
                text += `mastered: ${c.mastered}\n\n`;
            }
            memEl.textContent = text;
        }
    }

    // Daily.md equivalent
    if (dailyEl) {
        const log = getDailyLog(_todayISO());
        if (log.entries.length === 0) {
            dailyEl.textContent = '(no activity today)';
        } else {
            let text = `# Daily log ${_todayISO()}\n\n## Concepts\n`;
            for (const entry of log.entries) {
                text += `- concept_id: ${entry.concept_id}\n`;
                text += `  session: ${entry.session_id}\n`;
                text += `  turn: ${entry.turn}\n`;
                text += `  time: ${entry.timestamp}\n`;
            }
            dailyEl.textContent = text;
        }
    }

    // Conversation.md equivalent (from current session)
    if (convEl) {
        const session = getCurrentSession();
        if (!session.conversationTurns || session.conversationTurns.length === 0) {
            convEl.textContent = '(no structured turns yet)';
        } else {
            let text = `# Conversation ${session.id}\ndate: ${session.createdAt}\n\n`;
            for (const turn of session.conversationTurns) {
                text += `## Turn ${turn.turnNumber}\n`;
                text += `user: ${turn.user || ''}\n`;
                text += `concepts: ${(turn.concepts || []).join(', ')}\n`;
                if (turn.explanation) text += `explanation: ${turn.explanation.slice(0, 200)}...\n`;
                if (turn.checkQuestion) text += `check_question: ${turn.checkQuestion}\n`;
                if (turn.userAnswer !== undefined) text += `user_answer: ${turn.userAnswer}\n`;
                if (turn.correct !== undefined) text += `correct: ${turn.correct}\n`;
                text += '\n';
            }
            convEl.textContent = text;
        }
    }
}

// ── Date Helpers ─────────────────────────────────────────────────────

function _addDays(dateStr, days) {
    const d = new Date(dateStr);
    d.setDate(d.getDate() + days);
    return d.toISOString().split('T')[0];
}

function _daysBetween(dateStr1, dateStr2) {
    const d1 = new Date(dateStr1);
    const d2 = new Date(dateStr2);
    return Math.abs(Math.floor((d2 - d1) / (1000 * 60 * 60 * 24)));
}

function _todayISO() {
    return new Date().toISOString().split('T')[0];
}

function _nowISO() {
    return new Date().toISOString();
}

/** Get all sessions from localStorage (used by recall support). */
function _getAllSessions() {
    try {
        return JSON.parse(localStorage.getItem('learnbot_sessions') || '{}');
    } catch {
        return {};
    }
}

