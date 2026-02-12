/**
 * chat.js — Handles sending messages, rendering bubbles, and markdown formatting.
 */

const API = '';

/** Send a message to the backend and get a response. */
async function sendMessage(message) {
    const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
    });
    return res.json();
}

/** Start learning a specific topic. */
async function startLearning(topic) {
    const res = await fetch(`${API}/api/start-learning`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
    });
    return res.json();
}

/** Add a user message bubble to the chat. */
function addUserMessage(text) {
    const container = document.getElementById('chat-container');
    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-end';
    wrapper.innerHTML = `<div class="msg-user text-sm text-white">${escapeHtml(text)}</div>`;
    container.appendChild(wrapper);
    scrollToBottom();
}

/** Add a bot message bubble with markdown rendering. */
function addBotMessage(text, type = 'message') {
    removeTypingIndicator();
    const container = document.getElementById('chat-container');
    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-start';

    const bubble = document.createElement('div');
    bubble.className = 'msg-bot text-sm text-gray-200';
    bubble.innerHTML = renderMarkdown(text);
    wrapper.appendChild(bubble);

    container.appendChild(wrapper);
    scrollToBottom();
    return bubble;
}

/** Show the typing indicator. */
function showTypingIndicator() {
    const container = document.getElementById('chat-container');
    if (document.getElementById('typing-indicator')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-start';
    wrapper.id = 'typing-indicator';
    wrapper.innerHTML = `
        <div class="msg-bot typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    container.appendChild(wrapper);
    scrollToBottom();
}

/** Remove the typing indicator. */
function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

/** Scroll chat to bottom. */
function scrollToBottom() {
    const container = document.getElementById('chat-container');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

/** Clear the welcome message on first chat. */
function clearWelcome() {
    const container = document.getElementById('chat-container');
    const welcome = container.querySelector('.py-10');
    if (welcome) welcome.remove();
}

// ── Markdown rendering ──────────────────────────────────────────────

function renderMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Code blocks (```...```)
    html = html.replace(/```([^`]*?)```/gs, (_, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-accent-400 mt-3 mb-1">$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-accent-400 mt-4 mb-2">$1</h2>');

    // Horizontal rule
    html = html.replace(/^---$/gm, '<hr>');

    // Numbered lists
    html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');

    // Bullet lists
    html = html.replace(/^[-*•]\s+(.+)$/gm, '<li>$1</li>');

    // Wrap consecutive <li> in <ul>
    html = html.replace(/((?:<li>.*?<\/li>\n?)+)/gs, '<ul class="list-disc pl-5 space-y-1">$1</ul>');

    // Paragraphs (double newlines)
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph if not starting with block element
    if (!html.startsWith('<')) {
        html = `<p>${html}</p>`;
    }

    // Emojis are already unicode — they render fine

    return html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
