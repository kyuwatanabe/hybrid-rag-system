// Admin Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadPendingFAQs();
});

// Load system stats
async function loadStats() {
    try {
        const response = await fetch('/api/admin/stats');
        const data = await response.json();

        if (data.success) {
            document.getElementById('totalFAQs').textContent = data.stats.total_faqs;
            document.getElementById('pendingFAQs').textContent = data.stats.pending_faqs;
            document.getElementById('approvedToday').textContent = data.stats.approved_today;
            document.getElementById('rejectedToday').textContent = data.stats.rejected_today;
        } else {
            console.error('Failed to load stats:', data.error);
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load pending FAQs
async function loadPendingFAQs() {
    const pendingList = document.getElementById('pendingList');
    pendingList.innerHTML = '<div class="loading">読み込み中...</div>';

    try {
        const response = await fetch('/api/admin/pending');
        const data = await response.json();

        if (data.success) {
            if (data.pending_faqs.length === 0) {
                pendingList.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">✓</div>
                        <p>承認待ちのFAQはありません</p>
                    </div>
                `;
            } else {
                pendingList.innerHTML = '';
                data.pending_faqs.forEach(faq => {
                    const faqElement = createFAQElement(faq);
                    pendingList.appendChild(faqElement);
                });
            }

            // Update stats
            loadStats();
        } else {
            pendingList.innerHTML = `
                <div class="message message-error">
                    エラー: ${escapeHtml(data.error)}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading pending FAQs:', error);
        pendingList.innerHTML = `
            <div class="message message-error">
                通信エラーが発生しました
            </div>
        `;
    }
}

// Create FAQ element
function createFAQElement(faq) {
    const div = document.createElement('div');
    div.className = 'faq-item';
    div.id = `faq-${faq.id}`;

    const sourceBadgeClass = faq.source === 'RAG' ? 'source-badge-rag' : 'source-badge';
    const ratingClass = faq.user_rating === 'positive' ? 'rating-positive' : 'rating-negative';

    div.innerHTML = `
        <div class="faq-header">
            <span class="faq-id">ID: ${escapeHtml(faq.id)}</span>
            <span class="faq-timestamp">${escapeHtml(faq.timestamp)}</span>
        </div>

        <div class="faq-question">
            ${escapeHtml(faq.question)}
        </div>

        <div class="faq-answer">
            ${formatAnswer(faq.answer)}
        </div>

        <div class="faq-meta">
            <div class="faq-meta-item">
                <span class="source-badge ${sourceBadgeClass}">${escapeHtml(faq.source)}</span>
            </div>
            <div class="faq-meta-item">
                ユーザー評価: <span class="${ratingClass}">${faq.user_rating === 'positive' ? '👍 良い' : '👎 悪い'}</span>
            </div>
        </div>

        <div class="faq-actions">
            <button class="btn btn-edit" onclick="editFAQ(${faq.id})">
                ✎ 編集
            </button>
            <button class="btn btn-approve" onclick="approveFAQ(${faq.id})">
                ✓ 承認してFAQに追加
            </button>
            <button class="btn btn-reject" onclick="rejectFAQ(${faq.id})">
                × 拒否
            </button>
        </div>
    `;

    return div;
}

// Approve FAQ
async function approveFAQ(faqId) {
    const faqElement = document.getElementById(`faq-${faqId}`);
    const buttons = faqElement.querySelectorAll('button');

    // Disable buttons
    buttons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch(`/api/admin/approve/${faqId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            // Show success message
            showMessage('success', `FAQ ${faqId} を承認しました。FAQデータベースに追加されました。`);

            // Remove FAQ item with animation
            faqElement.style.opacity = '0';
            faqElement.style.transform = 'translateX(50px)';
            setTimeout(() => {
                faqElement.remove();
                // Reload if no more items
                if (document.querySelectorAll('.faq-item').length === 0) {
                    loadPendingFAQs();
                }
            }, 300);

            // Update stats
            loadStats();
        } else {
            showMessage('error', `承認に失敗しました: ${data.error}`);
            // Re-enable buttons
            buttons.forEach(btn => btn.disabled = false);
        }
    } catch (error) {
        console.error('Error approving FAQ:', error);
        showMessage('error', '通信エラーが発生しました');
        // Re-enable buttons
        buttons.forEach(btn => btn.disabled = false);
    }
}

// Reject FAQ
async function rejectFAQ(faqId) {
    if (!confirm(`FAQ ${faqId} を拒否してもよろしいですか？`)) {
        return;
    }

    const faqElement = document.getElementById(`faq-${faqId}`);
    const buttons = faqElement.querySelectorAll('button');

    // Disable buttons
    buttons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch(`/api/admin/reject/${faqId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            // Show success message
            showMessage('success', `FAQ ${faqId} を拒否しました。`);

            // Remove FAQ item with animation
            faqElement.style.opacity = '0';
            faqElement.style.transform = 'translateX(-50px)';
            setTimeout(() => {
                faqElement.remove();
                // Reload if no more items
                if (document.querySelectorAll('.faq-item').length === 0) {
                    loadPendingFAQs();
                }
            }, 300);

            // Update stats
            loadStats();
        } else {
            showMessage('error', `拒否に失敗しました: ${data.error}`);
            // Re-enable buttons
            buttons.forEach(btn => btn.disabled = false);
        }
    } catch (error) {
        console.error('Error rejecting FAQ:', error);
        showMessage('error', '通信エラーが発生しました');
        // Re-enable buttons
        buttons.forEach(btn => btn.disabled = false);
    }
}

// Show message
function showMessage(type, text) {
    const messageClass = type === 'success' ? 'message-success' : 'message-error';
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${messageClass}`;
    messageDiv.textContent = text;

    const pendingList = document.getElementById('pendingList');
    pendingList.insertBefore(messageDiv, pendingList.firstChild);

    // Auto remove after 5 seconds
    setTimeout(() => {
        messageDiv.style.opacity = '0';
        setTimeout(() => messageDiv.remove(), 300);
    }, 5000);
}

// Format answer text
function formatAnswer(text) {
    return escapeHtml(text)
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

// Edit FAQ
function editFAQ(faqId) {
    const faqElement = document.getElementById(`faq-${faqId}`);
    const questionElement = faqElement.querySelector('.faq-question');
    const answerElement = faqElement.querySelector('.faq-answer');
    const actionsElement = faqElement.querySelector('.faq-actions');

    // Get current values
    const currentQuestion = questionElement.textContent.trim();
    const currentAnswer = answerElement.textContent.trim();

    // Replace with textareas
    questionElement.innerHTML = `
        <textarea class="edit-textarea" id="edit-question-${faqId}" rows="2">${escapeHtml(currentQuestion)}</textarea>
    `;

    answerElement.innerHTML = `
        <textarea class="edit-textarea" id="edit-answer-${faqId}" rows="8">${escapeHtml(currentAnswer)}</textarea>
    `;

    // Replace actions with save/cancel buttons
    actionsElement.innerHTML = `
        <button class="btn btn-save" onclick="saveFAQ(${faqId})">
            💾 保存
        </button>
        <button class="btn btn-cancel" onclick="cancelEditFAQ(${faqId})">
            ✕ キャンセル
        </button>
    `;

    // Store original values for cancel
    faqElement.dataset.originalQuestion = currentQuestion;
    faqElement.dataset.originalAnswer = currentAnswer;
}

// Save edited FAQ
async function saveFAQ(faqId) {
    const faqElement = document.getElementById(`faq-${faqId}`);
    const questionTextarea = document.getElementById(`edit-question-${faqId}`);
    const answerTextarea = document.getElementById(`edit-answer-${faqId}`);

    const newQuestion = questionTextarea.value.trim();
    const newAnswer = answerTextarea.value.trim();

    if (!newQuestion || !newAnswer) {
        alert('質問と回答を入力してください');
        return;
    }

    // Disable textareas
    questionTextarea.disabled = true;
    answerTextarea.disabled = true;

    try {
        const response = await fetch(`/api/admin/update/${faqId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: newQuestion,
                answer: newAnswer
            })
        });

        const data = await response.json();

        if (data.success) {
            showMessage('success', `FAQ ${faqId} を更新しました`);

            // Reload pending FAQs to show updated version
            loadPendingFAQs();
        } else {
            showMessage('error', `更新に失敗しました: ${data.error}`);
            // Re-enable textareas
            questionTextarea.disabled = false;
            answerTextarea.disabled = false;
        }
    } catch (error) {
        console.error('Error saving FAQ:', error);
        showMessage('error', '通信エラーが発生しました');
        // Re-enable textareas
        questionTextarea.disabled = false;
        answerTextarea.disabled = false;
    }
}

// Cancel FAQ editing
function cancelEditFAQ(faqId) {
    // Reload pending FAQs to restore original view
    loadPendingFAQs();
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
