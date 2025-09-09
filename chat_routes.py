from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import Conversation, Message

# A Blueprint for API-related routes for better organization.
api_bp = Blueprint('api_bp', __name__)

@api_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    """Fetches all conversation histories for the current user."""
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
    return jsonify([conv.to_dict() for conv in conversations])

@api_bp.route('/conversation/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Fetches all messages for a specific conversation."""
    conv = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()
    messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.asc()).all()
    return jsonify([msg.to_dict() for msg in messages])
