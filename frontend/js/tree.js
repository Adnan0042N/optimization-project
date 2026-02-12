/**
 * tree.js — Renders the prerequisite tree in the sidebar.
 */

/** Fetch and render the prerequisite tree. */
async function refreshTree() {
    try {
        const res = await fetch(`${API}/api/tree`);
        const data = await res.json();

        const container = document.getElementById('tree-container');
        if (!data.tree) {
            container.innerHTML = '<p class="text-gray-600 text-xs italic">Ask me to learn a topic to see the tree here.</p>';
            return;
        }

        container.innerHTML = '';
        renderTreeNode(data.tree, container, data.current_index, data.teaching_order || []);
    } catch (e) {
        console.error('Tree fetch error:', e);
    }
}

/** Recursively render a tree node. */
function renderTreeNode(node, parent, currentIndex, teachingOrder) {
    const div = document.createElement('div');
    const nodeEl = document.createElement('div');

    // Determine status
    const topicLower = node.topic.toLowerCase().trim();
    const orderIndex = teachingOrder.findIndex(t => t.toLowerCase().trim() === topicLower);
    let statusClass = 'pending';
    let icon = '○';

    if (node.type === 'MASTERED') {
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
            renderTreeNode(child, childContainer, currentIndex, teachingOrder);
        }
        div.appendChild(childContainer);
    }

    parent.appendChild(div);
}
