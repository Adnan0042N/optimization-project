/**
 * app.js — Main application logic: form handling, quick start, sidebar toggle, tabs, history.
 */

let isLoading = false;

// ── Load chat history on page load ──────────────────────────────────

/** Fetch and render previous chat messages from the server. */
async function loadHistory() {
    try {
        const res = await fetch(`${API}/api/history`);
        const data = await res.json();

        if (data.messages && data.messages.length > 0) {
            clearWelcome();
            for (const msg of data.messages) {
                if (msg.role === 'user') {
                    addUserMessage(msg.content);
                } else {
                    addBotMessage(msg.content, msg.type || 'message');
                }
            }
        }

        // Update header if there's an active topic
        if (data.target_topic) {
            document.getElementById('header-title').textContent = data.target_topic;
        }
    } catch (e) {
        console.error('History load error:', e);
    }
}

// ── Chat form handling ──────────────────────────────────────────────

/** Handle chat form submission. */
async function handleSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message || isLoading) return;

    clearWelcome();
    addUserMessage(message);
    input.value = '';
    autoResize(input);
    setLoading(true);

    showTypingIndicator();

    try {
        const data = await sendMessage(message);
        addBotMessage(data.response, data.type);

        // Refresh sidebar
        refreshTree();
        refreshProgress();
        refreshMemory();
    } catch (err) {
        removeTypingIndicator();
        addBotMessage('⚠️ Something went wrong. Please check if the server is running.', 'error');
        console.error('Chat error:', err);
    } finally {
        setLoading(false);
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
        refreshTree();
        refreshProgress();
        refreshMemory();
    } catch (err) {
        removeTypingIndicator();
        addBotMessage('⚠️ Could not connect to the server.', 'error');
    } finally {
        setLoading(false);
    }
}

/** Reset the learning session. */
async function resetSession() {
    try {
        await fetch(`${API}/api/reset`, { method: 'POST' });
        // Clear chat
        const container = document.getElementById('chat-container');
        container.innerHTML = `
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
        // Reset header
        document.getElementById('header-title').textContent = 'Start Learning';
        document.getElementById('header-subtitle').textContent = 'Ask me to teach you any topic';
        refreshTree();
        refreshProgress();
        refreshMemory();
    } catch (err) {
        console.error('Reset error:', err);
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
        refreshMemory();
    }
}

/** Fetch memory file contents and display them. */
async function refreshMemory() {
    try {
        const res = await fetch(`${API}/api/memory`);
        const data = await res.json();

        const memEl = document.getElementById('memory-content');
        const dailyEl = document.getElementById('daily-content');
        const convEl = document.getElementById('conversation-content');

        if (memEl) memEl.textContent = data.memory || '(empty)';
        if (dailyEl) dailyEl.textContent = data.daily || '(empty)';
        if (convEl) convEl.textContent = data.conversation || '(empty)';
    } catch (e) {
        console.error('Memory fetch error:', e);
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

// ── Initialize ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();   // restore previous chat messages
    refreshTree();
    refreshProgress();
    refreshMemory();
    document.getElementById('chat-input').focus();
});
