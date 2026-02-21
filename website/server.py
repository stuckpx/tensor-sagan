#!/usr/bin/env python3
"""
Haramain Fridays - Flask Backend Server
Handles email subscriptions using Firebase Firestore.
"""

import os
import json
import uuid
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__, static_folder='.', static_url_path='')

# Firebase Setup
# Path to service account key in parent directory
FIREBASE_CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'harmainfridays-firebase-adminsdk-fbsvc-c21f19e297.json')

# Support environment variable for Vercel
FIREBASE_ENV_JSON = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')

try:
    if FIREBASE_ENV_JSON:
        import json
        cred_dict = json.loads(FIREBASE_ENV_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✓ Connected to Firebase using Environment Variable")
    elif os.path.exists(FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print(f"✓ Connected to Firebase using {FIREBASE_CREDENTIALS_PATH}")
    else:
        print("Warning: No Firebase credentials found (File or Env)")
        db = None
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    db = None
    print(f"⚠️ Firebase credentials not found at {FIREBASE_CREDENTIALS_PATH}")
    print("Please set FIREBASE_CREDENTIALS_PATH environment variable or place serviceAccountKey.json in this directory.")
    db = None


def generate_token(email):
    """Generate a unique unsubscribe token for an email."""
    unique_string = f"{email}-{datetime.now().isoformat()}-{uuid.uuid4()}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:32]


@app.route('/')
def index():
    """Serve the main website."""
    return send_from_directory('.', 'index.html')


@app.route('/archive')
def archive():
    """Serve the archive page."""
    return send_from_directory('.', 'archive.html')


@app.route('/api/archive')
def archive_data():
    """Serve the sermon archive JSON."""
    archive_path = os.path.join(os.path.dirname(__file__), 'sermons_archive.json')
    if os.path.exists(archive_path):
        with open(archive_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({'sermons': [], 'imams': {}}), 404


@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handle new email subscriptions."""
    if not db:
        return jsonify({'error': 'Database not configured'}), 503

    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        
        # Validate email
        if not email or '@' not in email:
            return jsonify({'error': 'Please provide a valid email address'}), 400
        
        # Check if already subscribed
        users_ref = db.collection('subscribers')
        query = users_ref.where('email', '==', email).limit(1).stream()
        
        for doc in query:
            user_data = doc.to_dict()
            if not user_data.get('active', True):
                # Reactivate
                users_ref.document(doc.id).update({
                    'active': True,
                    'subscribed_at': datetime.now().isoformat()
                })
                return jsonify({'message': 'Welcome back! Subscription reactivated.'}), 200
            else:
                return jsonify({'message': 'You are already subscribed.'}), 200
        
        # New subscriber
        new_subscriber = {
            'email': email,
            'token': generate_token(email),
            'subscribed_at': datetime.now().isoformat(),
            'active': True
        }
        
        users_ref.add(new_subscriber)
        
        return jsonify({
            'message': 'Successfully subscribed',
            'email': email
        }), 201
        
    except Exception as e:
        print(f"Error in subscribe: {e}")
        return jsonify({'error': 'Server error processing subscription'}), 500


@app.route('/unsubscribe')
def unsubscribe():
    """Handle unsubscribe requests via token."""
    token = request.args.get('token', '').strip()
    
    if not token or not db:
        return render_status_page("❌ Invalid Link", "This unsubscribe link is invalid or the system is unavailable.", 400)
    
    try:
        users_ref = db.collection('subscribers')
        query = users_ref.where('token', '==', token).limit(1).stream()
        
        found = False
        for doc in query:
            found = True
            users_ref.document(doc.id).update({'active': False})
            
        if found:
            return render_status_page("✓ Unsubscribed", "You have been successfully unsubscribed from Haramain Fridays.<br><br><a href='/'>Subscribe again</a>")
        else:
            return render_status_page("🔍 Not Found", "This subscription was not found or has already been removed.", 404)
            
    except Exception as e:
        print(f"Error in unsubscribe: {e}")
        return render_status_page("⚠️ Error", "An error occurred. Please try again later.", 500)


def render_status_page(title, message, status_code=200):
    """Helper to render simple status pages."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title.split(' ')[-1]} - Haramain Fridays</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f5f5f0; }}
            .card {{ background: white; padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            h1 {{ color: #0d5c3f; }}
            p {{ color: #666; line-height: 1.5; }}
            a {{ color: #0d5c3f; text-decoration: none; font-weight: bold; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>{title}</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """
    return html, status_code


@app.route('/api/debug/subscribers')
def list_subscribers():
    """Debug endpoint to list subscribers."""
    # TODO: Remove in production
    if not db:
        return jsonify({'error': 'Database not connected'})
    
    users = []
    docs = db.collection('subscribers').where('active', '==', True).stream()
    for doc in docs:
        d = doc.to_dict()
        users.append(d.get('email'))
        
    return jsonify({'count': len(users), 'emails': users})


if __name__ == '__main__':
    print("=" * 50)
    print("🕌 Haramain Fridays Server (Firebase Edition)")
    print("=" * 50)
    print("\nStarting server at http://localhost:3000")
    print("Press Ctrl+C to stop\n")
    
    app.run(host='0.0.0.0', port=3000, debug=True)

