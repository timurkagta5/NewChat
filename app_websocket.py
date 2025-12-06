"""
Speeky Messenger - Backend Server (WebSocket Version)
For Railway.app, Heroku, Render.com and other platforms with WebSocket support
"""

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
from dotenv import load_dotenv
import bcrypt
import jwt
import os

load_dotenv()

# ============================================================================
# Configuration
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///messenger.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, resources={r"/*": {"origins": "*"}})
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ============================================================================
# Database Models
# ============================================================================

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    tag = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(128))
    avatar = db.Column(db.String(256))
    bio = db.Column(db.String(256))
    status = db.Column(db.String(20), default='offline')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    messages = db.relationship('Message', backref='author', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'tag': self.tag,
            'display_name': self.display_name,
            'avatar': self.avatar,
            'bio': self.bio,
            'status': self.status
        }

class Chat(db.Model):
    __tablename__ = 'chats'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    is_group = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    messages = db.relationship('Message', backref='chat', lazy='dynamic')
    members = db.relationship('ChatMember', backref='chat', lazy='dynamic')

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')
    status = db.Column(db.String(20), default='sent')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'content': self.content,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }

class ChatMember(db.Model):
    __tablename__ = 'chat_members'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================================
# API Routes - General
# ============================================================================

@app.route('/')
def index():
    return {'status': 'Speeky Messenger API (WebSocket)', 'version': '1.0.0'}

@app.route('/api/health')
def health():
    return {'status': 'healthy', 'websocket': True}

# ============================================================================
# API Routes - Authentication
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    tag = data.get('tag')
    password = data.get('password')
    
    if not username or not tag or not password:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(tag=tag).first():
        return jsonify({'error': 'Tag already exists'}), 400
    
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(
        username=username,
        tag=tag,
        password_hash=password_hash,
        display_name=username,
        status='online'
    )
    
    db.session.add(user)
    db.session.commit()
    
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=30)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'token': token,
        'user': user.to_dict()
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    tag = data.get('tag')
    password = data.get('password')
    
    if not tag or not password:
        return jsonify({'error': 'Missing credentials'}), 400
    
    user = User.query.filter_by(tag=tag).first()
    
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    user.status = 'online'
    db.session.commit()
    
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=30)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'token': token,
        'user': user.to_dict()
    })

@app.route('/api/auth/verify', methods=['POST'])
def verify_token():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = User.query.get(payload['user_id'])
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()})
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

# ============================================================================
# API Routes - Users
# ============================================================================

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json
    
    if 'display_name' in data:
        user.display_name = data['display_name']
    if 'bio' in data:
        user.bio = data['bio']
    if 'avatar' in data:
        user.avatar = data['avatar']
    if 'status' in data:
        user.status = data['status']
    
    db.session.commit()
    return jsonify(user.to_dict())

@app.route('/api/users/search', methods=['GET'])
def search_users():
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify([])
    
    users = User.query.filter(
        (User.username.ilike(f'%{query}%')) |
        (User.tag.ilike(f'%{query}%'))
    ).limit(20).all()
    
    return jsonify([user.to_dict() for user in users])

@app.route('/api/users/<string:tag>/by-tag', methods=['GET'])
def get_user_by_tag(tag):
    user = User.query.filter_by(tag=tag).first_or_404()
    return jsonify(user.to_dict())

# ============================================================================
# API Routes - Chats
# ============================================================================

@app.route('/api/chats/<int:user_id>', methods=['GET'])
def get_user_chats(user_id):
    memberships = ChatMember.query.filter_by(user_id=user_id).all()
    chats = []
    
    for membership in memberships:
        chat = Chat.query.get(membership.chat_id)
        last_message = Message.query.filter_by(chat_id=chat.id)\
            .order_by(Message.created_at.desc()).first()
        
        unread_count = Message.query.filter_by(chat_id=chat.id, status='sent')\
            .filter(Message.user_id != user_id).count()
        
        chats.append({
            'id': chat.id,
            'name': chat.name,
            'is_group': chat.is_group,
            'avatar': chat.avatar,
            'last_message': last_message.content if last_message else '',
            'last_message_time': last_message.created_at.isoformat() if last_message else '',
            'unread_count': unread_count
        })
    
    return jsonify(chats)

@app.route('/api/chats/create', methods=['POST'])
def create_chat():
    data = request.json
    name = data.get('name')
    is_group = data.get('is_group', False)
    member_ids = data.get('members', [])
    
    chat = Chat(name=name, is_group=is_group)
    db.session.add(chat)
    db.session.flush()
    
    for user_id in member_ids:
        member = ChatMember(chat_id=chat.id, user_id=user_id)
        db.session.add(member)
    
    db.session.commit()
    
    return jsonify({'id': chat.id, 'name': chat.name}), 201

@app.route('/api/chats/<int:chat_id>/messages', methods=['GET'])
def get_messages(chat_id):
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    messages = Message.query.filter_by(chat_id=chat_id)\
        .order_by(Message.created_at.desc())\
        .limit(limit).offset(offset).all()
    
    return jsonify([msg.to_dict() for msg in reversed(messages)])

@app.route('/api/chats/<int:chat_id>/members', methods=['GET'])
def get_chat_members(chat_id):
    members = ChatMember.query.filter_by(chat_id=chat_id).all()
    users = []
    
    for member in members:
        user = User.query.get(member.user_id)
        users.append(user.to_dict())
    
    return jsonify(users)

# ============================================================================
# WebSocket Events
# ============================================================================

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('connected', {'status': 'success'})

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')

@socketio.on('join_chat')
def handle_join(data):
    user_id = data.get('user_id')
    chat_id = data.get('chat_id')
    
    room = f'chat_{chat_id}'
    join_room(room)
    
    user = User.query.get(user_id)
    if user:
        user.status = 'online'
        db.session.commit()
    
    print(f'👤 User {user_id} joined chat {chat_id}')
    emit('joined', {'chat_id': chat_id}, room=room)

@socketio.on('leave_chat')
def handle_leave(data):
    chat_id = data.get('chat_id')
    room = f'chat_{chat_id}'
    leave_room(room)
    print(f'👋 User left chat {chat_id}')

@socketio.on('send_message')
def handle_send_message(data):
    chat_id = data.get('chat_id')
    user_id = data.get('user_id')
    content = data.get('content')
    message_type = data.get('type', 'text')
    
    message = Message(
        chat_id=chat_id,
        user_id=user_id,
        content=content,
        message_type=message_type,
        status='sent'
    )
    
    db.session.add(message)
    db.session.commit()
    
    room = f'chat_{chat_id}'
    print(f'💬 Message sent to chat {chat_id}')
    emit('new_message', message.to_dict(), room=room)

@socketio.on('typing')
def handle_typing(data):
    chat_id = data.get('chat_id')
    user_id = data.get('user_id')
    is_typing = data.get('is_typing', True)
    
    room = f'chat_{chat_id}'
    emit('user_typing', {
        'user_id': user_id,
        'is_typing': is_typing
    }, room=room, include_self=False)

@socketio.on('message_read')
def handle_message_read(data):
    message_id = data.get('message_id')
    
    message = Message.query.get(message_id)
    if message:
        message.status = 'read'
        db.session.commit()
        
        room = f'chat_{message.chat_id}'
        emit('message_status_updated', {
            'message_id': message_id,
            'status': 'read'
        }, room=room)

# ============================================================================
# Database Initialization
# ============================================================================

with app.app_context():
    db.create_all()
    print("✓ Database tables created")

# ============================================================================
# Run Application
# ============================================================================

if __name__ == '__main__':
    print("="*60)
    print("🚀 Speeky Messenger Server (WebSocket)")
    print("="*60)
    print("📡 Mode: WebSocket (Real-time)")
    print("🌐 For Railway.app, Heroku, Render.com")
    print("📍 Running on: http://0.0.0.0:5000")
    print("="*60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
