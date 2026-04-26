#!/usr/bin/env python3
"""
Haramain Fridays - Flask Backend Server
Handles email subscriptions using Firebase Firestore.
"""

import os
import re
import json
import uuid
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template_string, abort
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


# Known valid email domains for typo detection
KNOWN_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com',
    'aol.com', 'protonmail.com', 'live.com', 'msn.com', 'mail.com',
    'zoho.com', 'yandex.com', 'gmx.com', 'fastmail.com', 'me.com',
    'yahoo.co.uk', 'hotmail.co.uk', 'googlemail.com',
}

# Common typos mapping to correct domains
DOMAIN_TYPOS = {
    'gmial.com': 'gmail.com', 'gmal.com': 'gmail.com', 'gmai.com': 'gmail.com',
    'gmail.cmo': 'gmail.com', 'gmail.co': 'gmail.com', 'gmail.cim': 'gmail.com',
    'gmail.con': 'gmail.com', 'gmail.vom': 'gmail.com', 'gmail.xom': 'gmail.com',
    'gmail.comm': 'gmail.com', 'gmail.comi': 'gmail.com', 'gmail.coim': 'gmail.com',
    'gamil.com': 'gmail.com', 'gnail.com': 'gmail.com', 'hmail.com': 'gmail.com',
    'gmaill.com': 'gmail.com', 'gmail.om': 'gmail.com',
    'yaho.com': 'yahoo.com', 'yahooo.com': 'yahoo.com', 'yahoo.cmo': 'yahoo.com',
    'yahoo.con': 'yahoo.com', 'yahoo.co': 'yahoo.com',
    'hotmal.com': 'hotmail.com', 'hotmial.com': 'hotmail.com', 'hotmail.con': 'hotmail.com',
    'hotmail.cmo': 'hotmail.com', 'hotamil.com': 'hotmail.com',
    'outlok.com': 'outlook.com', 'outllook.com': 'outlook.com', 'outlook.con': 'outlook.com',
    'icloud.con': 'icloud.com', 'icoud.com': 'icloud.com', 'iclould.com': 'icloud.com',
}

# Valid TLDs (most common)
VALID_TLDS = {
    'com', 'org', 'net', 'edu', 'gov', 'io', 'co', 'uk', 'ca', 'au', 'de',
    'fr', 'jp', 'in', 'br', 'ru', 'info', 'biz', 'me', 'tv', 'us', 'za',
    'sa', 'ae', 'pk', 'eg', 'my', 'sg', 'id', 'ng', 'ke', 'gh', 'tr',
}


def validate_email(email):
    """
    Validate an email address. Returns (is_valid, error_message, suggestion).
    - is_valid: True if email is acceptable
    - error_message: Human-readable error if invalid
    - suggestion: Corrected email if a typo is detected, else None
    """
    if not email or not isinstance(email, str):
        return False, 'Please provide an email address.', None

    email = email.strip().lower()

    # Basic format check with regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, 'Please enter a valid email address (e.g. name@example.com).', None

    local, domain = email.rsplit('@', 1)

    # Check local part length
    if len(local) > 64 or len(local) < 1:
        return False, 'The email username is invalid.', None

    # Check domain length
    if len(domain) > 253 or len(domain) < 3:
        return False, 'The email domain is invalid.', None

    # Extract TLD
    tld = domain.rsplit('.', 1)[-1]

    # Check for known domain typos
    if domain in DOMAIN_TYPOS:
        corrected = DOMAIN_TYPOS[domain]
        suggestion = f"{local}@{corrected}"
        return False, f'Did you mean {suggestion}?', suggestion

    # If domain is known valid, accept immediately
    if domain in KNOWN_DOMAINS:
        return True, None, None

    # For unknown domains, check TLD validity
    if tld not in VALID_TLDS and len(tld) > 3:
        # Likely a typo like .comi, .comm, .coim
        return False, f'The domain "{domain}" doesn\'t look right. Please check for typos.', None

    # Accept the email (unknown but plausible domain)
    return True, None, None


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
        is_valid, error_msg, suggestion = validate_email(email)
        if not is_valid:
            response = {'error': error_msg}
            if suggestion:
                response['suggestion'] = suggestion
            return jsonify(response), 400
        
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


@app.route('/api/approve_draft')
def approve_draft():
    """Handle draft approval requests."""
    date_str = request.args.get('date', '').strip()
    token = request.args.get('token', '').strip()
    
    if not date_str or not token or not db:
        return render_status_page("❌ Invalid Link", "This approval link is invalid or missing parameters.", 400)
        
    try:
        draft_ref = db.collection('drafts').document(date_str)
        doc = draft_ref.get()
        
        if not doc.exists:
            return render_status_page("🔍 Not Found", "No draft found for this date.", 404)
            
        draft_data = doc.to_dict()
        
        if draft_data.get('token') != token:
            return render_status_page("❌ Invalid Token", "The security token does not match.", 403)
            
        if draft_data.get('status') == 'approved':
            return render_status_page("✓ Already Approved", "This draft has already been approved and is scheduled to send at 6 PM.", 200)
            
        if draft_data.get('status') == 'sent':
            return render_status_page("✓ Already Sent", "This draft was already fully sent to subscribers.", 200)
            
        # Update status
        draft_ref.update({'status': 'approved'})
        
        return render_status_page("✅ Draft Approved!", "The sermon summary has been approved. It will be sent automatically to all subscribers at 6:00 PM PST.", 200)
        
    except Exception as e:
        print(f"Error approving draft: {e}")
        return render_status_page("⚠️ Error", "An error occurred while approving the draft. Please try again later.", 500)


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


@app.route('/sermons/<slug>')
def sermon_page(slug):
    """Serve a dedicated, server-side rendered SEO page for a single sermon."""
    slug_parts = slug.split('-', 1)
    if len(slug_parts) != 2:
        return abort(404)
    mosque, date = slug_parts
        
    if mosque not in ('makkah', 'madinah'):
        return abort(404)
        
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return abort(404)
        
    archive_path = os.path.join(os.path.dirname(__file__), 'sermons_archive.json')
    if not os.path.exists(archive_path):
        return abort(404)
        
    with open(archive_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    sermons = data.get('sermons', [])
    imams = data.get('imams', {})
    
    sermon = next((s for s in sermons if s['date'] == date and s['mosque'] == mosque), None)
    if not sermon:
        return abort(404)
        
    imam_key = sermon.get('imam_key')
    imam = imams.get(imam_key, {})
    imam_name = sermon.get('imam_name', 'Unknown Imam')
    imam_bio = imam.get('bio', '')
    
    mosque_name = "Masjid al-Haram, Makkah" if mosque == 'makkah' else "Masjid an-Nabawi, Madinah"
    mosque_icon = "🕋" if mosque == 'makkah' else "🌙"
    
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    date_formatted = date_obj.strftime('%B %d, %Y')
    
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ sermon.topic }} | {{ imam_name }} | Friday Sermon</title>
        <meta name="description" content="{{ sermon.summary }}">
        <meta property="og:title" content="{{ sermon.topic }} - {{ mosque_name }}">
        <meta property="og:description" content="{{ sermon.summary }}">
        <meta property="og:type" content="article">
        <link rel="stylesheet" href="/index.css">
        <link rel="stylesheet" href="/archive.css">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="background-pattern"></div>
        <header>
            <nav class="container">
                <a href="/" class="logo">
                    <span class="logo-icon">🕌</span>
                    <span class="logo-text">Haramain Fridays</span>
                </a>
                <div class="nav-links">
                    <a href="/archive" class="nav-link">📚 Archive</a>
                </div>
            </nav>
        </header>

        <main class="container" style="max-width: 800px; margin: 40px auto; padding: 0 20px;">
            <article class="sermon-detail-card" style="display: block; opacity: 1;">
                <div class="sermon-header" style="text-align: center; margin-bottom: 30px;">
                    <span class="mosque-icon" style="font-size: 3em; display: block; margin-bottom: 20px;">{{ mosque_icon }}</span>
                    <h1 style="color: #0d5c3f; margin-bottom: 15px; font-size: 2.2em;">{{ sermon.topic or 'Friday Sermon' }}</h1>
                    <div style="font-size: 1.1em; color: #555; margin-bottom: 20px; line-height: 1.5;">
                        <strong>{{ imam_name }}</strong><br>
                        {{ mosque_name }}<br>
                        {{ date_formatted }}
                    </div>
                </div>

                <div class="sermon-summary" style="background: #f8f9f8; padding: 25px; border-radius: 12px; border-left: 5px solid #c89d2a; margin-bottom: 30px; font-size: 1.15em; line-height: 1.8;">
                    {{ sermon.summary or 'Summary not available.' }}
                </div>

                <div class="imam-bio" style="margin-bottom: 40px; padding: 25px; border: 1px solid #eee; background: white; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border-radius: 12px;">
                    <h3 style="color: #0d5c3f; margin-top: 0; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 10px;">About the Imam</h3>
                    <p style="color: #666; line-height: 1.7; margin: 0; font-size: 0.95em;">{{ imam_bio or 'Biography not available.' }}</p>
                </div>

                <div style="display: flex; gap: 15px; justify-content: center; margin-bottom: 50px; flex-wrap: wrap;">
                    {% if sermon.audio_url %}
                    <a href="{{ sermon.audio_url }}" target="_blank" class="audio-link" style="padding: 12px 24px;">🎧 Listen to Khutbah</a>
                    {% endif %}
                    {% if sermon.page_url %}
                    <a href="{{ sermon.page_url }}" target="_blank" class="page-link" style="padding: 12px 24px;">📄 View original on haramain.info</a>
                    {% endif %}
                </div>

                <!-- Email Capture Form -->
                <div class="hero-card" style="margin-top: 40px; text-align: center; max-width: 100%; box-shadow: 0 10px 30px rgba(13, 92, 63, 0.1);">
                    <div class="hero-content">
                        <h2 style="color: #0d5c3f; margin-bottom: 15px;">Get Weekly Summaries</h2>
                        <p style="color: #555; margin-bottom: 25px;">Join our newsletter to receive the Makkah and Madinah Friday sermon summaries straight to your inbox.</p>
                        <form id="subscribe-form" style="max-width: 450px; margin: 0 auto; display: flex; flex-direction: column;">
                            <div class="input-group" style="display: flex; gap: 10px;">
                                <input type="email" id="email" placeholder="Enter your email" required class="email-input" style="flex: 1;">
                                <button type="submit" class="submit-btn" id="submit-btn" style="white-space: nowrap;">Subscribe</button>
                            </div>
                            <p id="form-message" class="form-message" style="margin-top: 15px; height: 20px;"></p>
                        </form>
                    </div>
                </div>
            </article>
        </main>

        <footer>
            <div class="container">
                <p class="copyright">
                    &copy; 2026 <span class="footer-brand">🕌 Haramain Fridays</span>. All rights reserved.
                </p>
            </div>
        </footer>

        <script>
            document.getElementById('subscribe-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const email = document.getElementById('email').value;
                const messageEl = document.getElementById('form-message');
                const btn = document.getElementById('submit-btn');
                
                messageEl.textContent = '';
                messageEl.className = 'form-message';
                btn.disabled = true;
                btn.innerHTML = 'Subscribing...';
                
                try {
                    const resp = await fetch('/subscribe', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email: email })
                    });
                    
                    const data = await resp.json();
                    
                    if (resp.ok) {
                        messageEl.textContent = data.message || 'Successfully subscribed!';
                        messageEl.style.color = '#0d5c3f';
                        document.getElementById('email').value = '';
                    } else {
                        messageEl.textContent = data.error || data.suggestion || 'Failed to subscribe.';
                        messageEl.style.color = '#dc3545';
                    }
                } catch (err) {
                    messageEl.textContent = 'An error occurred. Please try again later.';
                    messageEl.style.color = '#dc3545';
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = 'Subscribe';
                }
            });
        </script>
    </body>
    </html>
    """
    
    return render_template_string(html_template, 
                                sermon=sermon, 
                                imam_name=imam_name, 
                                imam_bio=imam_bio,
                                mosque_name=mosque_name,
                                mosque_icon=mosque_icon,
                                date_formatted=date_formatted)


if __name__ == '__main__':
    print("=" * 50)
    print("🕌 Haramain Fridays Server (Firebase Edition)")
    print("=" * 50)
    print("\nStarting server at http://localhost:3000")
    print("Press Ctrl+C to stop\n")
    
    app.run(host='0.0.0.0', port=3000, debug=True)

