/**
 * app.js — Main application logic: form handling, quick start, sidebar toggle, tabs, session init.
 * Updated: uses localStorage sessions, passes session context to backend.
 */

let isLoading = false;

// ── Initialize ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Ensure a session exists and load UI
    getCurrentSession();
    loadCurrentSessionUI();
    renderSessionList();
    refreshReviewBanner();
    document.getElementById('chat-input').focus();
});

// ── Chat form handling ──────────────────────────────────────────────

/** Handle chat form submission. */
async function handleSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message || isLoading) return;

    clearWelcome();
    addUserMessage(message); // persists to session
    input.value = '';
    autoResize(input);
    setLoading(true);
    showTypingIndicator();

    try {
        const data = await sendMessage(message);

        // Save the bot response to session
        addBotMessage(data.response, data.type); // persists to session

        // Update session state from backend response
        if (data.session_update) {
            _applySessionUpdate(data.session_update);
        }

        // Handle structured turn data for conversation.md
        if (data.turn_data) {
            addConversationTurn(data.turn_data);

            // Update memory concepts
            if (data.turn_data.concepts) {
                for (const cid of data.turn_data.concepts) {
                    ensureConcept(cid, cid);
                    logDailyEntry(cid, getCurrentSessionId(), getCurrentSession().turnCounter);
                }
            }

            // Update spaced repetition if there was a check/synthesis result
            if (data.turn_data.correct !== undefined) {
                for (const cid of (data.turn_data.concepts || [])) {
                    updateConceptAfterReview(cid, data.turn_data.correct);
                }
            }
        }

        // Update auto-title on first learning request
        const session = getCurrentSession();
        if (session.targetTopic && session.title === 'New Chat') {
            updateSessionTitle(session.targetTopic);
        }

        // Refresh sidebar panels
        refreshTreeFromSession();
        refreshProgressFromSession();
        refreshMemoryPanel();
        refreshReviewBanner();
    } catch (err) {
        removeTypingIndicator();
        addBotMessage('⚠️ Something went wrong. Please check if the server is running.', 'error');
        console.error('Chat error:', err);
    } finally {
        setLoading(false);
    }
}

/** Apply session updates from the backend response. */
function _applySessionUpdate(update) {
    const changes = {};

    if (update.tree !== undefined) {
        // If backend returns a new tree, merge it into the session
        if (update.is_new_tree && update.topic) {
            mergeTreeIntoSession(update.tree, update.topic);
        } else {
            changes.tree = update.tree;
        }
    }
    if (update.teaching_order !== undefined) {
        changes.teachingOrder = update.teaching_order;
    }
    if (update.current_index !== undefined) {
        changes.currentIndex = update.current_index;
    }
    if (update.waiting_for_synthesis !== undefined) {
        changes.waitingForSynthesis = update.waiting_for_synthesis;
    }
    if (update.current_question !== undefined) {
        changes.currentQuestion = update.current_question;
    }
    if (update.attempt_count !== undefined) {
        changes.attemptCount = update.attempt_count;
    }
    if (update.target_topic !== undefined) {
        changes.targetTopic = update.target_topic;
    }
    if (update.explained_current !== undefined) {
        changes.explainedCurrent = update.explained_current;
    }

    if (Object.keys(changes).length > 0) {
        updateCurrentSession(changes);
    }
}

/** Quick-start button handler. */
async function quickStart(topic) {
    clearWelcome();
    addUserMessage(`Learn: ${topic}`);
    setLoading(true);
    showTypingIndicator();

    try {
        const data = await sendMessage(`Learn: ${topic}`);
        addBotMessage(data.response, data.type);

        if (data.session_update) {
            _applySessionUpdate(data.session_update);
        }
        if (data.turn_data) {
            addConversationTurn(data.turn_data);
        }

        // Auto-title
        const session = getCurrentSession();
        if (session.targetTopic && session.title === 'New Chat') {
            updateSessionTitle(session.targetTopic);
        }

        refreshTreeFromSession();
        refreshProgressFromSession();
        refreshMemoryPanel();
        renderSessionList();
    } catch (err) {
        removeTypingIndicator();
        addBotMessage('⚠️ Could not connect to the server.', 'error');
    } finally {
        setLoading(false);
    }
}

/** Start a review session for concepts due today. */
async function startReviewSession() {
    const due = getReviewDueConcepts();
    if (due.length === 0) return;

    // Use current session for reviews
    clearWelcome();

    const conceptNames = due.map(c => c.name).join(', ');
    const systemMsg = `📚 **Time for review!** You have ${due.length} concept${due.length > 1 ? 's' : ''} to review: ${conceptNames}.\n\nI'll ask you about each one. Let's start!`;
    addBotMessage(systemMsg, 'message');

    // Ask the backend to start a review flow
    try {
        setLoading(true);
        showTypingIndicator();
        const data = await sendMessage(`[REVIEW] ${due.map(c => c.concept_id).join(',')}`);
        addBotMessage(data.response, data.type);

        if (data.session_update) {
            _applySessionUpdate(data.session_update);
        }

        refreshTreeFromSession();
        refreshProgressFromSession();
        refreshReviewBanner();
    } catch (err) {
        removeTypingIndicator();
        addBotMessage('⚠️ Could not start review session.', 'error');
    } finally {
        setLoading(false);
    }
}

// ── Sidebar Tabs ────────────────────────────────────────────────────

/** Switch between Tree and Memory tabs. */
function switchTab(tab) {
    const treeTab = document.getElementById('tab-tree');
    const memTab = document.getElementById('tab-memory');
    const treePanel = document.getElementById('panel-tree');
    const memPanel = document.getElementById('panel-memory');

    if (tab === 'tree') {
        treeTab.classList.add('text-accent-400', 'border-accent-500');
        treeTab.classList.remove('text-gray-500', 'border-transparent');
        memTab.classList.remove('text-accent-400', 'border-accent-500');
        memTab.classList.add('text-gray-500', 'border-transparent');
        treePanel.classList.remove('hidden');
        memPanel.classList.add('hidden');
    } else {
        memTab.classList.add('text-accent-400', 'border-accent-500');
        memTab.classList.remove('text-gray-500', 'border-transparent');
        treeTab.classList.remove('text-accent-400', 'border-accent-500');
        treeTab.classList.add('text-gray-500', 'border-transparent');
        memPanel.classList.remove('hidden');
        treePanel.classList.add('hidden');
        refreshMemoryPanel();
    }
}

// ── Keyboard & Input ────────────────────────────────────────────────

/** Handle Enter key (submit) and Shift+Enter (newline). */
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('chat-form').requestSubmit();
    }
}

/** Auto-resize textarea to fit content. */
function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 128) + 'px';
}

/** Toggle loading state. */
function setLoading(loading) {
    isLoading = loading;
    const btn = document.getElementById('send-btn');
    const input = document.getElementById('chat-input');
    btn.disabled = loading;
    input.disabled = loading;
    if (!loading) input.focus();
}

/** Toggle sidebar on mobile. */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}
