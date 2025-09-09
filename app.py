import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv
from models import db, User
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import click

# Load environment variables
load_dotenv()

# --- NEW: Full, Re-ordered Model List ---
# Models are ordered from highest perceived tier to lowest.
# The 'models/' prefix has been removed as it's part of the URL template.
GEMINI_MODELS = [
    'gemini-2.5-pro',
    'gemini-2.5-flash',
    'gemini-2.5-flash-preview-05-20',
    'gemini-2.5-flash-lite-preview-06-17',
    'gemini-1.5-pro-latest', # Added for stability
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash',
    'gemini-1.5-flash-002',
    'gemini-1.5-flash-8b-latest',
    'gemini-1.5-flash-8b',
    'gemini-1.5-flash-8b-001',
    'gemini-2.0-flash-exp',
    'gemini-2.0-flash',
    'gemini-2.0-flash-001',
    'gemini-2.0-flash-lite',
    'gemini-2.0-flash-lite-001',
    'gemini-2.0-flash-lite-preview',
    'gemini-2.0-flash-lite-preview-02-05',
    'gemini-2.0-flash-thinking-exp',
    'gemini-2.0-flash-thinking-exp-01-21',
    'gemini-2.0-flash-thinking-exp-1219',
]

GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
API_KEY = os.environ.get('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY not found in .env file. Please ensure it is set correctly.")

# --- Flask Application Setup ---
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key-for-dev-only')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

@login_manager.user_loader
def load_user(user_id):
    # FIX: Updated to use db.session.get to resolve LegacyAPIWarning
    return db.session.get(User, int(user_id))

# --- Authentication Routes ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user)
        return redirect(url_for('chat'))
    else:
        flash('Invalid username or password.', 'danger')
        return redirect(url_for('index'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'warning')
        return redirect(url_for('index'))
    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    flash('Registration successful! Please log in.', 'success')
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/chat')
@login_required
def chat():
    # UPDATE: Pass the list of models to the frontend template
    return render_template('chat.html', models=GEMINI_MODELS)

# --- API Logic Implementation ---
def call_gemini_api(model, prompt):
    """Helper function to call a single Gemini model."""
    api_url = GEMINI_API_URL_TEMPLATE.format(model=model, api_key=API_KEY)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {'Content-Type': 'application/json'}
    try:
        print(f"Attempting to call model: {model}...")
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        response_json = response.json()
        candidates = response_json.get('candidates', [])
        if candidates and 'content' in candidates[0] and 'parts' in candidates[0]['content'] and candidates[0]['content']['parts']:
            extracted_text = candidates[0]['content']['parts'][0].get('text', 'No text content found.')
            print(f"Success with model: {model}")
            return extracted_text
    except requests.exceptions.RequestException as e:
        print(f"Model {model} failed with network/HTTP error: {e}")
    except (KeyError, IndexError) as e:
        print(f"Model {model} returned an unexpected JSON structure: {e}")
    return None

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    # UPDATE: Handle manual model selection from the frontend
    if not request.json or 'prompt' not in request.json:
        return jsonify({'error': 'Invalid request. Missing JSON body or prompt.'}), 400
    
    prompt = request.json.get('prompt')
    selected_model = request.json.get('model', 'auto')

    if selected_model == 'auto':
        # Auto mode: Iterate through the prioritized list
        for model in GEMINI_MODELS:
            response_text = call_gemini_api(model, prompt)
            if response_text is not None:
                # UPDATE: Return the successful model name along with the response
                return jsonify({'response': response_text, 'model_used': model})
        return jsonify({'error': 'All AI models are currently unavailable. Please try again later.'}), 503
    else:
        # Manual mode: Try only the selected model
        if selected_model not in GEMINI_MODELS:
            return jsonify({'error': 'Invalid model selected.'}), 400
        response_text = call_gemini_api(selected_model, prompt)
        if response_text is not None:
            return jsonify({'response': response_text, 'model_used': selected_model})
        else:
            return jsonify({'error': f'The selected model "{selected_model}" failed to respond. Please try another model or use Auto mode.'}), 503

# --- Database Initialization Command ---
@app.cli.command("init-db")
def init_db_command():
    """Clears the existing data and creates new tables."""
    db.create_all()
    click.echo("Initialized the database.")

# --- Server Execution Block ---
if __name__ == '__main__':
    app.run(debug=True)
