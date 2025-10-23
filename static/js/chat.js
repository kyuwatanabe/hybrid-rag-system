// RAG Chatbot JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const queryInput = document.getElementById('queryInput');
    const sendButton = document.getElementById('sendButton');
    const chatMessages = document.getElementById('chatMessages');

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const query = queryInput.value.trim();
        if (!query) return;

        // Disable input while processing
        setInputState(false);

        // Add user message to chat
        addUserMessage(query);

        // Clear input
        queryInput.value = '';

        // Add loading message
        const loadingId = addLoadingMessage();

        try {
            // Send query to backend
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: query })
            });

            const data = await response.json();

            // Remove loading message
            removeLoadingMessage(loadingId);

            if (data.success) {
                // Add bot response based on source (FAQ or RAG)
                if (data.source === 'FAQ') {
                    addFAQMessage(data.answer, data.faq_question, data.similarity);
                } else {
                    addRAGMessage(query, data.answer, data.sources);
                }
            } else {
                // Add error message
                addErrorMessage(data.error || 'エラーが発生しました');
            }

        } catch (error) {
            console.error('Error:', error);
            removeLoadingMessage(loadingId);
            addErrorMessage('通信エラーが発生しました。もう一度お試しください。');
        } finally {
            // Re-enable input
            setInputState(true);
            queryInput.focus();
        }
    });

    // Add user message to chat
    function addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                ${escapeHtml(text)}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // Add FAQ message to chat
    function addFAQMessage(answer, faqQuestion, similarity) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message faq-message';

        const similarityPercent = (similarity * 100).toFixed(1);

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="source-badge faq-badge">FAQ登録済み</div>
                ${formatAnswer(answer)}
                <div class="faq-info">
                    <small>
                        <strong>元の質問:</strong> ${escapeHtml(faqQuestion)}<br>
                        <strong>類似度:</strong> ${similarityPercent}%
                    </small>
                </div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // Add RAG message to chat
    function addRAGMessage(userQuery, answer, sources) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message rag-message';

        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            sourcesHtml = `
                <div class="sources">
                    <h4>参照情報 (${sources.length}件)</h4>
                    ${sources.map(source => `
                        <div class="source-item">
                            <strong>${source.number}.</strong>
                            ${escapeHtml(source.file_name)}
                            (ページ ${source.page_num})
                            - 類似度: ${(source.similarity * 100).toFixed(1)}%
                        </div>
                    `).join('')}
                </div>
            `;
        }

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="source-badge rag-badge">RAG生成</div>
                ${formatAnswer(answer)}
                ${sourcesHtml}
                <div class="rating-buttons">
                    <button class="rating-btn positive-btn" data-query="${escapeHtml(userQuery)}" data-answer="${escapeHtml(answer)}">
                        👍 この回答は役に立ちました
                    </button>
                    <button class="rating-btn negative-btn" data-query="${escapeHtml(userQuery)}" data-answer="${escapeHtml(answer)}">
                        👎 この回答は役に立ちませんでした
                    </button>
                </div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        // Add click event listeners to rating buttons
        const ratingButtons = messageDiv.querySelectorAll('.rating-btn');
        ratingButtons.forEach(btn => {
            btn.addEventListener('click', handleRating);
        });
    }

    // Add loading message
    function addLoadingMessage() {
        const loadingId = 'loading-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message loading-message';
        messageDiv.id = loadingId;
        messageDiv.innerHTML = `
            <div class="message-content">
                回答を生成中
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return loadingId;
    }

    // Remove loading message
    function removeLoadingMessage(loadingId) {
        const loadingElement = document.getElementById(loadingId);
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    // Add error message
    function addErrorMessage(error) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <p style="color: #d32f2f;">エラー: ${escapeHtml(error)}</p>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // Set input state (enabled/disabled)
    function setInputState(enabled) {
        queryInput.disabled = !enabled;
        sendButton.disabled = !enabled;

        const buttonText = sendButton.querySelector('.button-text');
        const buttonLoading = sendButton.querySelector('.button-loading');

        if (enabled) {
            buttonText.style.display = 'inline';
            buttonLoading.style.display = 'none';
        } else {
            buttonText.style.display = 'none';
            buttonLoading.style.display = 'inline';
        }
    }

    // Scroll to bottom of chat
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Format answer text (preserve line breaks)
    function formatAnswer(text) {
        return escapeHtml(text)
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    }

    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Handle rating button click
    async function handleRating(event) {
        const button = event.currentTarget;
        const query = button.dataset.query;
        const answer = button.dataset.answer;
        const rating = button.classList.contains('positive-btn') ? 'positive' : 'negative';

        // Disable both buttons
        const ratingButtons = button.parentElement.querySelectorAll('.rating-btn');
        ratingButtons.forEach(btn => btn.disabled = true);

        try {
            const response = await fetch('/api/rate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    answer: answer,
                    rating: rating
                })
            });

            const data = await response.json();

            if (data.success) {
                // Replace buttons with thank you message
                button.parentElement.innerHTML = `
                    <div class="rating-feedback">
                        ${rating === 'positive' ? '✓' : '×'} ${escapeHtml(data.message)}
                    </div>
                `;
            } else {
                console.error('Rating failed:', data.error);
                // Re-enable buttons on error
                ratingButtons.forEach(btn => btn.disabled = false);
            }

        } catch (error) {
            console.error('Error submitting rating:', error);
            // Re-enable buttons on error
            ratingButtons.forEach(btn => btn.disabled = false);
        }
    }

    // Focus on input on page load
    queryInput.focus();
});
