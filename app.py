from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
import cv2
from deepface import DeepFace
import time
import chromadb
from gpt4all import GPT4All
import threading
import os
import bcrypt
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'Likhi_Nam_0914'  # Change this for better security

# MySQL Database Connection
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="ballast.proxy.rlwy.net",
            user="root",
            password="nqqXtXTbqtzHwgLBGOBrUtytjOlvIjTI",
            database="railway",
            port=24246
        )
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

db = get_db_connection()
if db is None:
    raise ConnectionError("Failed to connect to the MySQL database.")

# Set up model path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Get current script directory
MODEL_PATH = os.path.join(BASE_DIR, "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Please download it and place it in the correct directory.")

# Initialize GPT-4All model
try:
    gpt4all_model = GPT4All(MODEL_PATH, device="cpu")  # Ensure it runs on CPU
except Exception as e:
    raise RuntimeError(f"Failed to load GPT-4All model: {e}")

# Ensure chatbot_db directory exists
CHATBOT_DB_PATH = os.path.join(BASE_DIR, "chatbot_db")
if not os.path.exists(CHATBOT_DB_PATH):
    os.makedirs(CHATBOT_DB_PATH)

# Initialize ChromaDB for storing chat history
client = chromadb.PersistentClient(path=CHATBOT_DB_PATH)
collection = client.get_or_create_collection(name="chat_history")

# Emotion tracking file path
MEMORY_FILE = os.path.join(BASE_DIR, "data/emotions.json")

# Ensure the 'data' directory exists
if not os.path.exists(os.path.dirname(MEMORY_FILE)):
    os.makedirs(os.path.dirname(MEMORY_FILE))

# Function to load latest emotion
def load_latest_emotion():
    try:
        with open(MEMORY_FILE, 'r') as file:
            emotions = json.load(file)
            if emotions:
                return emotions[-1]['emotion']  # Get the most recent emotion
            return "neutral"
    except Exception as e:
        print(f"Error loading emotion data: {e}")
        return "neutral"

# Function to capture emotion continuously
# Function to capture emotion continuously
def capture_emotion():
    cap = cv2.VideoCapture(0)  # Open default camera
    if not cap.isOpened():
        print("Error: Camera not accessible")
        return

    emotion_buffer = []
    BUFFER_SIZE = 20

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame")
            break

        try:
            # Analyze detected face
            analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            dominant_emotion = analysis[0]['dominant_emotion']
            emotion_buffer.append(dominant_emotion)

            if len(emotion_buffer) > BUFFER_SIZE:
                emotion_buffer.pop(0)

            most_common_emotion = max(set(emotion_buffer), key=emotion_buffer.count)
            emotion_data = {
                'timestamp': str(datetime.now()),
                'emotion': most_common_emotion
            }

            # Ensure JSON file exists before writing
            if not os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, 'w') as file:
                    json.dump([], file)  # Create an empty list if file is missing

            # Append new emotion data safely
            with open(MEMORY_FILE, 'r+') as file:
                try:
                    emotions = json.load(file)
                except json.JSONDecodeError:
                    emotions = []  # If the file is corrupted, reset it

                emotions.append(emotion_data)
                file.seek(0)
                json.dump(emotions[-100:], file)  # Keep last 100 records

        except Exception as e:
            print(f"Emotion detection error: {e}")

        time.sleep(5)

    cap.release()
    cv2.destroyAllWindows()

# Start emotion detection in a separate thread
threading.Thread(target=capture_emotion, daemon=True).start()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                               (username, email, hashed_password.decode('utf-8')))
                conn.commit()
                return redirect(url_for('signin'))
            except mysql.connector.Error as err:
                return f"Error: {err}"
            finally:
                cursor.close()
                conn.close()

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True, buffered=True)
            cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
            
            # ✅ Fetch all results before closing the cursor
            user = cursor.fetchone()  # Change fetchone() to fetchall() if multiple results are expected
            cursor.fetchall()  # This ensures there are no unread results

            cursor.close()
            conn.close()

            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                session['username'] = user['username']
                return redirect(url_for('dashboard'))
            else:
                return "Invalid Credentials", 401

    return render_template('signin.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('signin'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('signin'))

@app.route('/chatbot', methods=['GET'])
def chatbot():
    return render_template('chatbot.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '').strip()
    
    if not user_input:
        return jsonify({"response": "Please enter a message."})

    latest_emotion = load_latest_emotion()
    
    try:
        past_responses = collection.get(where={"user": session.get('username', 'guest')}, limit=10)
        chat_history = past_responses.get('documents', [])
        relevant_history = "\n".join(chat_history) if chat_history else ""
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        relevant_history = ""

    full_prompt = f"User is feeling {latest_emotion}. Recent conversation: {relevant_history}\nUser: {user_input}\nAI:"
    
    try:
        response = gpt4all_model.generate(full_prompt)
    except Exception as e:
        print(f"GPT-4All generation error: {e}")
        response = "Sorry, I couldn't process that request."

    timestamp = str(time.time())
    try:
        collection.add(
            documents=[user_input, response],
            metadatas=[{"user": session.get('username', 'guest')}, {"user": "AI"}],
            ids=[f"user_{timestamp}", f"ai_{timestamp}"]
        )
    except Exception as e:
        print(f"Error storing chat history: {e}")

    return jsonify({"response": response, "emotion": latest_emotion})

if __name__ == '__main__':
    app.run(debug=True)
