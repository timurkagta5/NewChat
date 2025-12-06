# Deprecated: Use python app.py instead
# This file is kept for backwards compatibility

from app import app, socketio

if __name__ == '__main__':
    print("⚠️  Please use 'python app.py' instead of 'python run.py'")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
