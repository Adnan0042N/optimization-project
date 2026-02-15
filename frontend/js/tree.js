/**
 * tree.js — Renders the prerequisite tree in the sidebar.
 * Updated: reads tree from localStorage session instead of /api/tree.
 */

/** Refresh tree from the current session in localStorage. */
function refreshTreeFromSession() {
    const session = getCurrentSession();
    const container = document.getElementById('tree-container');

    if (!session.tree) {
        container.innerHTML = '<p class="text-gray-600 text-xs italic">Ask me to learn a topic to see the tree here.</p>';
        return;
    }

    const masteredSet = getMasteredConceptIds();
    const teachingOrder = session.teachingOrder.map(t => typeof t === 'string' ? t : t.topic);
    const currentIndex = session.currentIndex;

    container.innerHTML = '';
    renderTreeNode(session.tree, container, currentIndex, teachingOrder, masteredSet);
}

/** Legacy alias for compatibility. */
function refreshTree() {
    refreshTreeFromSession();
}

/** Recursively render a tree node. */
function renderTreeNode(node, parent, currentIndex, teachingOrder, masteredSet) {
    const div = document.createElement('div');
    const nodeEl = document.createElement('div');

    // Determine status
    const topicLower = node.topic.toLowerCase().trim();
    const orderIndex = teachingOrder.findIndex(t => t.toLowerCase().trim() === topicLower);
    let statusClass = 'pending';
    let icon = '○';

    if (node.type === 'MASTERED' || masteredSet.has(topicLower)) {
        statusClass = 'mastered';
        icon = '✓';
    } else if (orderIndex !== -1 && orderIndex < currentIndex) {
        statusClass = 'mastered';
        icon = '✓';
    } else if (orderIndex === currentIndex) {
        statusClass = 'learning';
        icon = '▶';
    } else if (node.type === 'FACT') {
        statusClass = 'concept';
        icon = '◆';
    }

    nodeEl.className = `tree-node ${statusClass}`;
    nodeEl.innerHTML = `
        <span class="text-[10px] opacity-60">${icon}</span>
        <span class="truncate">${escapeHtml(node.topic)}</span>
    `;
    div.appendChild(nodeEl);

    // Render children
    if (node.children && node.children.length > 0) {
        const childContainer = document.createElement('div');
        childContainer.className = 'tree-children';
        for (const child of node.children) {
            renderTreeNode(child, childContainer, currentIndex, teachingOrder, masteredSet);
        }
        div.appendChild(childContainer);
    }

    parent.appendChild(div);
}
