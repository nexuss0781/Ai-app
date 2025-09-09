import os
import requests
import re
import ast
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv
from models import db, User, Conversation, Message
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import click
from chat_routes import api_bp
# MODIFIED: Import the specific tool registry from the tools file
from tools import SUB_TOOL_REGISTRY

load_dotenv()

# --- System Prompt & Agent Configuration ---
with open("prompt.md", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# USER-DEFINED MODEL LIST (UNCHANGED AS PER REQUEST)
AGENT_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-1.5-pro-latest',
    'gemini-2.5-flash-preview-05-20',
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash',
    'gemini-1.5-flash-8b-latest',
    'gemini-2.0-flash',
    'gemini-2.0-flash-exp',
    'gemini-1.5-flash-002',
    'gemini-1.5-flash-8b',
    'gemini-1.5-flash-8b-001',
    'gemini-2.0-flash-001',
    'gemini-2.0-flash-lite',
    'gemini-2.0-flash-lite-001',
    'gemini-2.0-flash-lite-preview',
    'gemini-2.0-flash-lite-preview-02-05',
    'gemini-2.0-flash-thinking-exp',
    'gemini-2.0-flash-thinking-exp-01-21',
    'gemini-2.0-flash-thinking-exp-1219'
]

# --- API Config ---
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
app.register_blueprint(api_bp, url_prefix='/api')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Standard Routes (Unchanged) ---
@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('chat'))
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
    return render_template('chat.html')

# --- Core Agent Logic ---

def call_agent_llm(prompt):
    """Calls the Gemini API with the full, prioritized model list."""
    for model in AGENT_MODELS:
        api_url = GEMINI_API_URL_TEMPLATE.format(model=model, api_key=API_KEY)
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        headers = {'Content-Type': 'application/json'}
        try:
            print(f"Attempting to call model: {model}...")
            response = requests.post(api_url, json=payload, headers=headers, timeout=40)
            response.raise_for_status()
            print(f"Success with model: {model}")
            return response.json()['candidates'][0]['content']['parts'][0]['text'], model
        except Exception as e:
            print(f"Model {model} failed: {e}")
    return None, None

def autonomous_loop(initial_prompt: str, llm_caller: callable, system_prompt: str):
    """
    NEW: This function contains the agent's internal reasoning loop.
    It is invoked for complex tasks requiring multiple tool uses.
    """
    history = [f"User task: {initial_prompt}"]
    response_events = []
    max_turns = 7

    for turn in range(max_turns):
        full_prompt = system_prompt + "\n\n**Internal Monologue History:**\n" + "\n".join(history)
        
        llm_response, model_used = llm_caller(full_prompt)
        if not llm_response:
            response_events.append({'type': 'error', 'content': 'Agent failed to respond during loop.'})
            break

        tool_match = re.search(r'<tool_code>(.*?)</tool_code>', llm_response, re.DOTALL)
        
        if tool_match:
            thought = llm_response.split('<tool_code>')[0].strip()
            if thought: response_events.append({'type': 'thought', 'content': thought})
            
            tool_call_str = tool_match.group(1).strip()
            response_events.append({'type': 'tool_call', 'content': tool_call_str})
            
            try:
                func_name = tool_call_str.split('(', 1)[0]
                args_str = tool_call_str[len(func_name)+1:-1]
                args = ast.literal_eval(f"({args_str},)") if args_str else ()
                
                tool_func = SUB_TOOL_REGISTRY.get(func_name)
                if tool_func: tool_output = tool_func(*args)
                else: tool_output = f"Error: Tool '{func_name}' not found."
            except Exception as e:
                tool_output = f"Error executing tool: {e}"

            response_events.append({'type': 'tool_output', 'content': str(tool_output)})
            history.append(f"AI Thought: {llm_response}")
            history.append(f"Tool Output: {tool_output}")
        else:
            response_events.append({'type': 'final_answer', 'content': llm_response, 'model_used': model_used})
            break
    else:
        response_events.append({'type': 'error', 'content': 'Agent exceeded maximum turns.'})

    return response_events

@app.route('/ask', methods=['POST'])
@login_required
def ask():
    """
    MODIFIED: This route is now a high-level dispatcher.
    It makes one LLM call to decide if a task is simple or needs the autonomous loop.
    """
    data = request.json
    prompt = data.get('prompt')
    conversation_id = data.get('conversation_id')
    
    if not conversation_id:
        title = (prompt[:35] + '...') if len(prompt) > 35 else prompt
        new_conv = Conversation(user_id=current_user.id, title=title)
        db.session.add(new_conv)
        db.session.commit()
        conversation_id = new_conv.id
    
    user_message = Message(conversation_id=conversation_id, sender='user', content=prompt)
    db.session.add(user_message)
    db.session.commit()

    full_prompt = SYSTEM_PROMPT + f"\n\n**User Request:**\n{prompt}"
    
    llm_response, model_used = call_agent_llm(full_prompt)
    if not llm_response:
        return jsonify({'events': [{'type': 'error', 'content': 'Agent dispatcher failed.'}]}), 500

    tool_match = re.search(r'<tool_code>(.*?)</tool_code>', llm_response, re.DOTALL)
    response_events = []

    if tool_match and 'autonomous_loop' in tool_match.group(1):
        # LLM decided the task is complex. Delegate to the autonomous loop.
        try:
            loop_events = autonomous_loop(
                initial_prompt=prompt, 
                llm_caller=call_agent_llm, 
                system_prompt=SYSTEM_PROMPT
            )
            response_events.append({'type': 'loop_event', 'content': loop_events})
            final_answer = next((e['content'] for e in loop_events if e['type'] == 'final_answer'), "Loop finished.")
            ai_message = Message(conversation_id=conversation_id, sender='ai', content=final_answer, model_used=model_used)
        except Exception as e:
            response_events.append({'type': 'error', 'content': f"Failed to execute loop: {e}"})
            ai_message = Message(conversation_id=conversation_id, sender='ai', content=f"Error: {e}", model_used=model_used)
    else:
        # LLM decided the task is simple. Return the direct answer.
        response_events.append({'type': 'final_answer', 'content': llm_response})
        ai_message = Message(conversation_id=conversation_id, sender='ai', content=llm_response, model_used=model_used)

    db.session.add(ai_message)
    db.session.commit()
        
    return jsonify({'events': response_events, 'conversation_id': conversation_id})

# --- Database Command ---
@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    click.echo("Initialized the database.")

if __name__ == '__main__':
    app.run(debug=True)
