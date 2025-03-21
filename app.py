from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from notion.client import NotionClient
from notion.block import HeaderBlock, VideoBlock
import secrets
import json
import logging
import datetime
from kafka_utils import KafkaClient

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize Kafka client
kafka_client = KafkaClient()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Kafka topics
USER_ACTIVITY_TOPIC = 'user-activity'
NOTION_EVENTS_TOPIC = 'notion-events'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    notion_token = db.Column(db.String(200), nullable=True)

    def set_password(self, password):
        self.password_hash = pbkdf2_sha256.hash(password)

    def check_password(self, password):
        return pbkdf2_sha256.verify(password, self.password_hash)

# Create all database tables
with app.app_context():
    db.create_all()
    # Create default admin user if it doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin')
        admin.set_password('password123')
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    notion_status = 'Not configured'
    pages = []
    if user.notion_token:
        try:
            client = NotionClient(token_v2=user.notion_token)
            top_pages = client.get_top_level_pages()
            print("Top Pages:", top_pages)
            pages = [{'title': page.title, 'id': page.id, 'display_id': page.id.replace('-', ''), 'count': None} for page in top_pages if page.type == 'page']
            print("Pages:", pages)
            notion_status = f'Connected - {len(pages)} pages found'
            print("Notion Status:", notion_status)
        except Exception as e:
            notion_status = f'Error: Invalid token'
    return render_template('home.html', username=session['username'], 
                         notion_token=user.notion_token,
                         notion_status=notion_status,
                         pages=pages)

@app.route('/update_token', methods=['POST'])
def update_token():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    new_token = request.form['notion_token']
    current_user = User.query.filter_by(username=session['username']).first()
    
    if new_token:
        try:
            client = NotionClient(token_v2=new_token)
            client.get_top_level_pages()  # Test the connection
            current_user.notion_token = new_token
            db.session.commit()
            flash('Notion token updated successfully!')
        except Exception as e:
            flash('Error: Invalid Notion token', 'error')
            return render_template('home.html', username=session['username'],
                                notion_token=current_user.notion_token,
                                error='Invalid Notion token')
    else:
        current_user.notion_token = None
        db.session.commit()
        flash('Notion token removed')
    
    return redirect(url_for('home'))

@app.route('/update_username', methods=['POST'])
def update_username():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    new_username = request.form['new_username']
    current_user = User.query.filter_by(username=session['username']).first()
    
    if not new_username or new_username.strip() == '':
        return render_template('home.html', username=session['username'], error='Username cannot be empty')
    
    if User.query.filter_by(username=new_username).first() and new_username != session['username']:
        return render_template('home.html', username=session['username'], error='Username already exists')
    
    current_user.username = new_username
    session['username'] = new_username
    db.session.commit()
    
    flash('Username updated successfully!')
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = username
            
            # Send login event to Kafka
            kafka_client.send_message(
                USER_ACTIVITY_TOPIC,
                {
                    'event_type': 'login',
                    'username': username,
                    'timestamp': str(datetime.datetime.now())
                }
            )
            
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Username already exists')
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/activate_page', methods=['POST'])
def activate_page():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    page_id = request.json.get('page_id')
    if not page_id:
        return jsonify({'success': False, 'error': 'No page ID provided'}), 400
    
    user = User.query.filter_by(username=session['username']).first()
    if not user.notion_token:
        return jsonify({'success': False, 'error': 'Notion token not configured'}), 400
    
    try:
        client = NotionClient(token_v2=user.notion_token, enable_kafka=True, kafka_bootstrap_servers='kafka:9092')
        page = client.get_block(page_id)
        page.children.add_new(HeaderBlock, title="The finest music:")
        video = page.children.add_new(VideoBlock, width=100)
        video.set_source_url("https://www.youtube.com/watch?v=oHg5SJYRHA0")
        
        # Send notion event to Kafka
        kafka_client.send_message(
            NOTION_EVENTS_TOPIC,
            {
                'event_type': 'page_activated',
                'username': session['username'],
                'page_id': page_id,
                'page_title': page.title,
                'timestamp': str(datetime.datetime.now())
            }
        )
        
        return jsonify({'success': True, 'count': 1})
    except Exception as e:
        # Send error event to Kafka
        kafka_client.send_message(
            NOTION_EVENTS_TOPIC,
            {
                'event_type': 'error',
                'username': session['username'],
                'page_id': page_id,
                'error': str(e),
                'timestamp': str(datetime.datetime.now())
            }
        )
        return jsonify({'success': False, 'error': str(e)}), 500

# Setup Kafka consumer for demonstration purposes
def handle_user_activity(key, value):
    logger.info(f"Received user activity: {value}")

def handle_notion_events(key, value):
    logger.info(f"Received notion event: {value}")

# Start Kafka consumers
if __name__ == '__main__':
    # Start Kafka consumers in background threads
    kafka_client.start_consumer_thread(USER_ACTIVITY_TOPIC, handle_user_activity, 'flask-app-group')
    kafka_client.start_consumer_thread(NOTION_EVENTS_TOPIC, handle_notion_events, 'flask-app-group')
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5001, debug=True)
