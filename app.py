"""
Hybrid RAG System Web Application
Flask-based web interface for Hybrid FAQ + RAG chatbot
"""

import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from hybrid_rag_system import HybridRAGSystem
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize Hybrid RAG system (global)
hybrid_rag = None


def init_hybrid_rag_system():
    """Initialize Hybrid RAG system on startup"""
    global hybrid_rag
    print("Initializing Hybrid RAG system...")

    # Claude APIキーを取得
    claude_api_key = os.getenv('CLAUDE_API_KEY')

    # ハイブリッドシステム初期化（デフォルトでfaq_database.csvを使用）
    hybrid_rag = HybridRAGSystem(
        faq_csv_path="faq_database.csv",
        faq_threshold=0.85,
        claude_api_key=claude_api_key
    )
    print("Hybrid RAG system ready!")


@app.route('/')
def index():
    """Render main chat page"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handle chat requests

    Request JSON:
        {
            "query": "user question"
        }

    Response JSON (FAQ):
        {
            "success": true,
            "query": "user question",
            "answer": "FAQ answer",
            "source": "FAQ",
            "similarity": 0.95,
            "faq_question": "original FAQ question"
        }

    Response JSON (RAG):
        {
            "success": true,
            "query": "user question",
            "answer": "generated answer",
            "source": "RAG",
            "sources": [...],
            "num_sources": 3
        }
    """
    try:
        data = request.get_json()

        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query is required'
            }), 400

        query = data['query'].strip()

        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400

        # Get answer from Hybrid RAG system
        result = hybrid_rag.answer_question(query)

        # Build response based on source
        response = {
            'success': True,
            'query': result['query'],
            'answer': result['answer'],
            'source': result['source']
        }

        if result['source'] == 'FAQ':
            # FAQ response
            response['similarity'] = result.get('similarity', 0)
            response['faq_question'] = result.get('faq_question', '')
        else:
            # RAG response
            response['sources'] = result.get('sources', [])
            response['num_sources'] = result.get('num_sources', 0)

        return jsonify(response)

    except Exception as e:
        print(f"Error in /api/chat: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'hybrid_rag_initialized': hybrid_rag is not None
    })


@app.route('/admin')
def admin():
    """Render admin page for FAQ approval"""
    return render_template('admin.html')


@app.route('/api/admin/pending', methods=['GET'])
def get_pending():
    """Get pending FAQs for approval"""
    try:
        pending_faqs = hybrid_rag.get_pending_approvals(limit=100)
        return jsonify({
            'success': True,
            'pending_faqs': pending_faqs
        })
    except Exception as e:
        print(f"Error in /api/admin/pending: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/update/<int:faq_id>', methods=['POST'])
def update_faq(faq_id):
    """Update a pending FAQ"""
    try:
        data = request.get_json()

        if not data or 'question' not in data or 'answer' not in data:
            return jsonify({
                'success': False,
                'error': 'Question and answer are required'
            }), 400

        question = data['question'].strip()
        answer = data['answer'].strip()

        if not question or not answer:
            return jsonify({
                'success': False,
                'error': 'Question and answer cannot be empty'
            }), 400

        success = hybrid_rag.update_pending_faq(faq_id, question, answer)

        if success:
            return jsonify({
                'success': True,
                'message': f'FAQ {faq_id} updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to update FAQ {faq_id}'
            }), 500

    except Exception as e:
        print(f"Error in /api/admin/update: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/approve/<int:faq_id>', methods=['POST'])
def approve_faq(faq_id):
    """Approve a pending FAQ"""
    try:
        success = hybrid_rag.approve_faq(faq_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'FAQ {faq_id} approved and added to database'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to approve FAQ {faq_id}'
            }), 500

    except Exception as e:
        print(f"Error in /api/admin/approve: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/reject/<int:faq_id>', methods=['POST'])
def reject_faq(faq_id):
    """Reject a pending FAQ"""
    try:
        success = hybrid_rag.reject_faq(faq_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'FAQ {faq_id} rejected'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to reject FAQ {faq_id}'
            }), 500

    except Exception as e:
        print(f"Error in /api/admin/reject: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        stats = hybrid_rag.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        print(f"Error in /api/admin/stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/rate', methods=['POST'])
def rate_answer():
    """
    Rate an answer (for RAG responses)

    Request JSON:
        {
            "query": "user question",
            "answer": "generated answer",
            "rating": "positive" or "negative"
        }

    Response JSON:
        {
            "success": true/false,
            "message": "Rating saved"
        }
    """
    try:
        data = request.get_json()

        if not data or 'query' not in data or 'answer' not in data or 'rating' not in data:
            return jsonify({
                'success': False,
                'error': 'Query, answer, and rating are required'
            }), 400

        query = data['query'].strip()
        answer = data['answer'].strip()
        rating = data['rating'].strip()

        if rating not in ['positive', 'negative']:
            return jsonify({
                'success': False,
                'error': 'Rating must be "positive" or "negative"'
            }), 400

        # Save to pending approval list (only for positive ratings)
        if rating == 'positive':
            success = hybrid_rag.save_to_pending_approval(
                query=query,
                answer=answer,
                source='RAG',
                user_rating='positive'
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Positive rating saved. Answer added to pending approval list.'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save rating'
                }), 500
        else:
            # Negative rating (just acknowledge for now)
            return jsonify({
                'success': True,
                'message': 'Negative rating noted. Thank you for your feedback.'
            })

    except Exception as e:
        print(f"Error in /api/rate: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Initialize Hybrid RAG system
    init_hybrid_rag_system()

    # Run Flask app
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    print(f"\n{'='*60}")
    print(f"RAG System Web Application")
    print(f"{'='*60}")
    print(f"Server running on: http://localhost:{port}")
    print(f"Debug mode: {debug}")
    print(f"{'='*60}\n")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
