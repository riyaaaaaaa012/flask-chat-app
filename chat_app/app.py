import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_socketio import SocketIO, send
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# Adjust these imports according to your project structure
from chat_app.models import db, User, ChatMessage
from chat_app.forms import LoginForm, RegisterForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'

# Setup DB path
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, '..', 'chat.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print("Using DB file at:", db_path)

db.init_app(app)
socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create ChatBot user once right after app setup (no decorators)
with app.app_context():
    bot_user = User.query.filter_by(username="ChatBot").first()
    if not bot_user:
        bot_user = User(username="ChatBot")
        bot_user.set_password('botpassword')  # Ensure this hashes password correctly
        db.session.add(bot_user)
        db.session.commit()
        print("ChatBot user created.")
    else:
        print("ChatBot user already exists.")

@app.route('/')
def home():
    return redirect(url_for('chat'))

@app.route('/chat')
@login_required
def chat():
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.asc()).all()
    return render_template('chat.html', username=current_user.username, messages=messages)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('chat'))
        flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Username already exists")
        else:
            new_user = User(username=form.username.data)
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created! Please log in.")
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Load transformer model once
model_name = "microsoft/DialoGPT-medium"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

def generate_bot_response(user_input, chat_history_ids=None):
    new_input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors='pt')
    if chat_history_ids is not None:
        bot_input_ids = torch.cat([chat_history_ids, new_input_ids], dim=-1)
    else:
        bot_input_ids = new_input_ids
    chat_history_ids = model.generate(bot_input_ids, max_length=1000, pad_token_id=tokenizer.eos_token_id)
    bot_reply = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)
    return bot_reply, chat_history_ids

@socketio.on('message')
def handle_message(msg):
    if current_user.is_authenticated:
        # Save user's message
        user_message = ChatMessage(
            user_id=current_user.id,
            username=current_user.username,
            content=msg,
            timestamp=datetime.utcnow()
        )
        db.session.add(user_message)
        db.session.commit()

        # Generate bot reply
        bot_reply, _ = generate_bot_response(msg)

        # Get ChatBot user
        bot_user = User.query.filter_by(username='ChatBot').first()

        # Save bot reply message
        bot_message = ChatMessage(
            user_id=bot_user.id,
            username='ChatBot',
            content=bot_reply,
            timestamp=datetime.utcnow()
        )
        db.session.add(bot_message)
        db.session.commit()

        # Broadcast messages
        send(f'{current_user.username} [{user_message.timestamp.strftime("%H:%M")}]: {msg}', broadcast=True)
        send(f'{bot_message.username} [{bot_message.timestamp.strftime("%H:%M")}]: {bot_reply}', broadcast=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)
