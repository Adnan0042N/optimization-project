/**
 * sessions.js — Multi-session manager using localStorage.
 * Each chat window = one session with its own tree, teaching order, and conversation log.
 */

const SESSIONS_KEY = 'learnbot_sessions';
const CURRENT_SESSION_KEY = 'learnbot_current_session';

// ── Helpers ──────────────────────────────────────────────────────────

function _generateId() {
    return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
}

function _todayISO() {
    return new Date().toISOString().split('T')[0];
}

function _nowISO() {
    return new Date().toISOString();
}

// ── Core Session CRUD ────────────────────────────────────────────────

/** Get all sessions as an object { id: session } */
function _getAllSessions() {
    try {
        return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '{}');
    } catch {
        return {};
    }
}

/** Save all sessions back to localStorage */
function _saveAllSessions(sessions) {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

/** Create a new empty session and return it. */
function createSession(title = 'New Chat') {
    const id = _generateId();
    const session = {
        id,
        title,
        createdAt: _nowISO(),
        updatedAt: _nowISO(),

        // Learning state (equivalent of old state.json)
        tree: null,              // accumulated knowledge tree (can have multiple root children)
        teachingOrder: [],       // flat ordered list of concepts to teach
        currentIndex: 0,
        waitingForSynthesis: false,
        currentQuestion: '',
        attemptCount: 0,
        targetTopic: '',         // latest topic being learned
        allTopics: [],           // all topics asked in this session
        explainedCurrent: false,

        // Chat messages for UI rendering
        chatHistory: [],         // [{role, content, type, time}]

        // Conversation.md equivalent (structured turns)
        conversationTurns: [],   // [{turnNumber, user, concepts, explanation, examples, checkQuestion, userAnswer, correct}]
        turnCounter: 0,
    };

    const sessions = _getAllSessions();
    sessions[id] = session;
    _saveAllSessions(sessions);
    setCurrentSessionId(id);
    return session;
}

/** Get a session by ID. */
function getSession(id) {
    const sessions = _getAllSessions();
    return sessions[id] || null;
}

/** Get the current active session. Creates one if none exists. */
function getCurrentSession() {
    const id = getCurrentSessionId();
    if (id) {
        const session = getSession(id);
        if (session) return session;
    }
    // No valid current session — create one
    return createSession();
}

/** Get current session ID from localStorage. */
function getCurrentSessionId() {
    return localStorage.getItem(CURRENT_SESSION_KEY);
}

/** Set the current session ID. */
function setCurrentSessionId(id) {
    localStorage.setItem(CURRENT_SESSION_KEY, id);
}

/** List all sessions sorted by updatedAt descending. */
function listSessions() {
    const sessions = _getAllSessions();
    return Object.values(sessions).sort((a, b) =>
        new Date(b.updatedAt) - new Date(a.updatedAt)
    );
}

/** Delete a session. If it's the current one, switch to another or create new. */
function deleteSession(id) {
    const sessions = _getAllSessions();
    delete sessions[id];
    _saveAllSessions(sessions);

    if (getCurrentSessionId() === id) {
        const remaining = Object.keys(sessions);
        if (remaining.length > 0) {
            setCurrentSessionId(remaining[0]);
        } else {
            createSession();
        }
    }
}

/** Update a specific field of the current session and save. */
function updateCurrentSession(updates) {
    const id = getCurrentSessionId();
    if (!id) return;

    const sessions = _getAllSessions();
    const session = sessions[id];
    if (!session) return;

    Object.assign(session, updates, { updatedAt: _nowISO() });
    sessions[id] = session;
    _saveAllSessions(sessions);
    return session;
}

/** Add a chat message to the current session. */
function addMessageToSession(role, content, type = 'message') {
    const session = getCurrentSession();
    session.chatHistory.push({
        role,
        content,
        type,
        time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    });
    // Keep last 200 messages
    if (session.chatHistory.length > 200) {
        session.chatHistory = session.chatHistory.slice(-200);
    }
    updateCurrentSession({ chatHistory: session.chatHistory });
}

/** Add a structured conversation turn to the current session. */
function addConversationTurn(turnData) {
    const session = getCurrentSession();
    session.turnCounter += 1;
    const turn = {
        turnNumber: session.turnCounter,
        timestamp: _nowISO(),
        ...turnData,
    };
    session.conversationTurns.push(turn);
    updateCurrentSession({
        conversationTurns: session.conversationTurns,
        turnCounter: session.turnCounter,
    });
    return turn;
}

/** Update session title based on the first topic. */
function updateSessionTitle(title) {
    updateCurrentSession({ title });
    renderSessionList(); // refresh sidebar
}

/** Merge a new tree into the session's accumulated tree.
 *  If no existing tree, just set it.
 *  If existing tree, add the new tree's root as a sibling child under a common parent.
 */
function mergeTreeIntoSession(newTree, topic) {
    const session = getCurrentSession();

    if (!session.tree) {
        // First tree in this session — use it directly
        updateCurrentSession({
            tree: newTree,
            targetTopic: topic,
            allTopics: [topic],
        });
    } else {
        // Accumulate: wrap both under a common "Session Knowledge" parent
        let existingTree = session.tree;

        if (existingTree.topic === 'Session Knowledge') {
            // Already a wrapper — add new tree as another child
            existingTree.children.push(newTree);
        } else {
            // First accumulation — wrap existing + new under parent
            existingTree = {
                topic: 'Session Knowledge',
                type: 'ROOT',
                children: [existingTree, newTree],
            };
        }

        const allTopics = session.allTopics || [];
        if (!allTopics.includes(topic)) {
            allTopics.push(topic);
        }

        updateCurrentSession({
            tree: existingTree,
            targetTopic: topic,
            allTopics,
        });
    }
}

// ── Sidebar Rendering ────────────────────────────────────────────────

/** Render the session list in the sidebar. */
function renderSessionList() {
    const container = document.getElementById('session-list');
    if (!container) return;

    const sessions = listSessions();
    const currentId = getCurrentSessionId();

    container.innerHTML = sessions.map(s => `
        <div class="session-item ${s.id === currentId ? 'active' : ''}"
             onclick="switchSession('${s.id}')" title="${s.title}">
            <div class="flex items-center gap-2 min-w-0">
                <svg class="w-3.5 h-3.5 shrink-0 text-gray-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"/>
                </svg>
                <span class="truncate text-xs">${escapeHtml(s.title)}</span>
            </div>
            <button onclick="event.stopPropagation(); confirmDeleteSession('${s.id}')"
                    class="opacity-0 group-hover:opacity-100 p-0.5 hover:text-red-400 transition-opacity shrink-0">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        </div>
    `).join('');
}

/** Switch to a different session. */
function switchSession(id) {
    setCurrentSessionId(id);
    loadCurrentSessionUI();
    renderSessionList();
}

/** Start a brand new chat session. */
function startNewChat() {
    createSession();
    loadCurrentSessionUI();
    renderSessionList();
}

/** Confirm and delete a session. */
function confirmDeleteSession(id) {
    if (confirm('Delete this chat?')) {
        deleteSession(id);
        loadCurrentSessionUI();
        renderSessionList();
    }
}

/** Load current session data into the UI (chat messages, tree, progress). */
function loadCurrentSessionUI() {
    const session = getCurrentSession();
    const container = document.getElementById('chat-container');

    // Clear chat area
    container.innerHTML = '';

    if (session.chatHistory.length === 0) {
        // Show welcome screen
        container.innerHTML = getWelcomeHTML();
    } else {
        // Render chat messages
        for (const msg of session.chatHistory) {
            if (msg.role === 'user') {
                addUserMessage(msg.content, false); // false = don't save again
            } else {
                addBotMessage(msg.content, msg.type || 'message', false);
            }
        }
    }

    // Update header
    if (session.targetTopic) {
        document.getElementById('header-title').textContent = session.targetTopic;
        const total = session.teachingOrder.length;
        const idx = session.currentIndex;
        document.getElementById('header-subtitle').textContent =
            session.waitingForSynthesis ? 'Synthesis question' : `Step ${idx + 1} of ${total}`;
    } else {
        document.getElementById('header-title').textContent = 'Start Learning';
        document.getElementById('header-subtitle').textContent = 'Ask me to teach you any topic';
    }

    // Refresh tree and progress from session
    refreshTreeFromSession();
    refreshProgressFromSession();
    refreshMemoryPanel();
}

function getWelcomeHTML() {
    return `
        <div class="flex justify-center py-10">
            <div class="text-center max-w-md">
                <div class="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-accent-500/20 to-purple-500/20 border border-accent-500/20 flex items-center justify-center">
                    <svg class="w-8 h-8 text-accent-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5"/></svg>
                </div>
                <h3 class="text-xl font-bold text-gray-100 mb-2">What do you want to learn?</h3>
                <p class="text-sm text-gray-500 mb-6">I'll break any topic into first principles and teach you step by step with synthesis questions.</p>
                <div class="flex flex-wrap justify-center gap-2">
                    <button onclick="quickStart('Quantum Mechanics')" class="quick-start-btn">Quantum Mechanics</button>
                    <button onclick="quickStart('Machine Learning')" class="quick-start-btn">Machine Learning</button>
                    <button onclick="quickStart('Blockchain')" class="quick-start-btn">Blockchain</button>
                    <button onclick="quickStart('General Relativity')" class="quick-start-btn">General Relativity</button>
                </div>
            </div>
        </div>
    `;
}
