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
    # Ensure the file exists before attempting to read
    if not os.path.exists(MEMORY_FILE):
        print("Emotion file not found, creating a new one.")
        with open(MEMORY_FILE, "w") as file:
            json.dump([], file)  # Initialize with an empty list
        return "neutral"

    try:
        with open(MEMORY_FILE, 'r') as file:
            emotions = json.load(file)

            # Validate data structure
            if isinstance(emotions, list) and emotions:
                return emotions[-1].get("emotion","neutral")

    except json.JSONDecodeError:
        print("Error: Corrupt emotions.json file. Attempting recovery.")
        with open(MEMORY_FILE, "w") as file:
            json.dump([], file)  # Reset the file completely
        return "neutral"

    except Exception as e:
        print(f"Error loading emotion data: {e}")
        return "neutral"

#Stores emotion
def store_emotion(emotion):
    try:
        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'w') as file:
                json.dump([], file)

        with open(MEMORY_FILE, 'r') as file:
            try:
                emotions = json.load(file)
                if not isinstance(emotions, list):
                    emotions = []
            except json.JSONDecodeError:
                emotions = []

        new_entry = {"timestamp": str(datetime.now()), "emotion": emotion}
        emotions.append(new_entry)
        emotions = emotions[-5:]

        with open(MEMORY_FILE, 'w') as file:
            json.dump(emotions, file, indent=4)
    except Exception as e:
        print(f"Error storing emotion: {e}")

# Function to capture emotion continuously
def capture_emotion():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Camera not accessible")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame")
            break
        try:
            analysis = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            if analysis and isinstance(analysis, list) and 'dominant_emotion' in analysis[0]:
                dominant_emotion = analysis[0]['dominant_emotion']
                print(f"Detected Emotion: {dominant_emotion}")
                store_emotion(dominant_emotion)
        except Exception as e:
            print(f"Emotion detection error: {e}")
        time.sleep(3)

    cap.release()
    cv2.destroyAllWindows()

threading.Thread(target=capture_emotion, daemon=True).start()

@app.route('/')
def home():
    return render_template('home.html')

# Sign Up Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        userid = request.form['userid']
        email = request.form['email']
        password = request.form['password']

        # Database operation
        try:
            cursor = db.cursor(buffered=True)

            # Check if userid or email already exists
            cursor.execute("SELECT * FROM users WHERE userid = %s OR email = %s", (userid, email))
            existing_user = cursor.fetchone()

            # Check which field is already taken and send appropriate messages
            if existing_user:
                if existing_user[2] == userid and existing_user[3] == email:
                    error = "Both User ID and Email are already taken. Please use different ones."
                elif existing_user[2] == userid:
                    error = "User ID is already taken. Please choose a different one."
                elif existing_user[3] == email:
                    error = "Email is already taken. Please use a different email."
                return render_template('signup.html', error=error)

            # If no conflicts, proceed to insert user
            cursor.execute("INSERT INTO users (name, userid, email, password) VALUES (%s, %s, %s, %s)",
                           (name, userid, email, password))
            db.commit()
            return redirect(url_for('signin'))

        except mysql.connector.Error as e:
            error = f"Database Error: {str(e)}"
            return render_template('signup.html', error=error)
        
        finally:
            cursor.close()

    return render_template('signup.html')

# Sign In Route
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        userid = request.form['userid']
        password = request.form['password']

        # Database operation
        try:
            cursor = db.cursor(buffered=True)
            cursor.execute("SELECT * FROM users WHERE userid = %s AND password = %s", (userid, password))
            user = cursor.fetchone()

            if user:
                # Store user ID and name in session
                session['userid'] = user[2]
                session['name'] = user[1]
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid User ID or Password. Please try again."
                return render_template('signin.html', error=error)
        
        except mysql.connector.Error as e:
            error = f"Database Error: {str(e)}"
            return render_template('signin.html', error=error)
        
        finally:
            cursor.close()

    return render_template('signin.html')

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'name' in session:
        return render_template('dashboard.html', name=session['name'])
    else:
        return redirect(url_for('signin'))
    
# Logout Route
@app.route('/logout')
def logout():
    session.pop('userid', None)
    session.pop('name', None)
    return redirect(url_for('signin'))

@app.route('/chatbot', methods=['GET'])
def chatbot():
    return render_template('chatbot.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '').strip()

    if not user_input:
        return jsonify({"response": "Please enter a message."})

    # Load the latest detected emotion
    latest_emotion = load_latest_emotion()

    # Fetch relevant chat history using similarity search
    try:
        search_results = collection.query(
            query_texts=[user_input],
            n_results=5  # Fetch top 5 most similar responses
        )
        relevant_history = search_results.get('documents', [])

        # Ensure relevant_history is a list of strings
        if isinstance(relevant_history, list):
            chat_history = "\n".join(map(str, relevant_history)) if relevant_history else ""
        else:
            chat_history = ""
    except Exception as e:
        print(f"Error fetching chat history: {e}")
        chat_history = ""

        # Construct a well-structured prompt
    full_prompt = (
        f"The user is currently feeling {latest_emotion}.\n"
        f"Recent chat history:\n{chat_history}\n"
        f"User's message: {user_input}\n"
        f"AI response:"
    )
    print(
        f"The user is currently feeling {latest_emotion}.\n"
        f"Recent chat history:\n{chat_history}\n"
        f"User's message: {user_input}\n"
        f"AI response:"
    )
    
    # Generate response
    try:
        response = gpt4all_model.generate(full_prompt, max_tokens=800).strip()
    except Exception as e:
        print(f"GPT-4All generation error: {e}")
        response = "Sorry, I couldn't process that request."

    # Store chat interaction in the database
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
