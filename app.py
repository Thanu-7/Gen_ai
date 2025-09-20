from flask import Flask, request, jsonify, render_template
import firebase_admin
from firebase_admin import credentials, firestore, auth
from textblob import TextBlob
from flask_cors import CORS
import requests
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

app = Flask(__name__)
CORS(app)

# --- Firebase ---
cred = credentials.Certificate('service_account.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Uploads ---
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Gemini API ---
API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

# --- Deepgram API ---
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# --- Chat history ---
chat_history = {}  # {user_id: [{"user": "...", "bot": "..."}, ...]}

# --- Gemini request (chatbot) ---
def get_gemini_reply(message_text):
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {"parts": [{"text": (
                "You are a friendly chatbot that detects the user's mood "
                "from their messages and responds in a supportive, empathetic, and friendly tone.\n"
                f"{message_text}\nBot:"
            )}]}
        ]
    }
    try:
        response = requests.post(GEMINI_ENDPOINT, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return "Sorry, I couldn't generate a reply."
    except Exception as e:
        print("Gemini API Error:", e)
        return "Sorry, I couldn't process your message."

# --- Deepgram Transcription (audio mood) ---
def transcribe_audio_deepgram(audio_filepath):
    with open(audio_filepath, "rb") as f:
        audio_bytes = f.read()

    print("Audio file size (bytes):", len(audio_bytes))  # Debug

    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/mpeg"  # Change if needed
    }

    try:
        response = requests.post(
            "https://api.deepgram.com/v1/listen",
            headers=headers,
            data=audio_bytes,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        print("Deepgram response:", data)  # Debug
        transcript = data.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', '')
        if not transcript:
            error_message = data.get('error', 'No speech detected.')
            return f"Deepgram error: {error_message}"
        return transcript
    except Exception as e:
        print("Deepgram transcription error:", e)
        return f"Deepgram exception: {str(e)}"

# --- Home ---
@app.route("/")
def home():
    try:
        return render_template("index.html")
    except:
        return "Hello, Bala! Your API is working."

# --- Journal Endpoints ---
@app.route('/add_journal', methods=['POST'])
def add_journal():
    data = request.json
    user_id = data.get('user_id')
    journal_text = data.get('journal')

    if not user_id or not journal_text:
        return jsonify({"error": "Missing data"}), 400

    db.collection('journals').add({
        'user_id': user_id,
        'journal': journal_text
    })
    return jsonify({"message": "Journal saved!"}), 200

@app.route('/get_journal', methods=['GET'])
def get_journal():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    entries = db.collection('journals').where('user_id', '==', user_id).stream()
    journals = [{'id': e.id, **e.to_dict()} for e in entries]

    return jsonify(journals), 200

@app.route('/analyze_journal', methods=['POST'])
def analyze_journal():
    data = request.json
    journal_text = data.get('journal')

    if not journal_text:
        return jsonify({"error": "Missing journal text"}), 400

    blob = TextBlob(journal_text)
    sentiment = blob.sentiment.polarity

    if sentiment <= -0.5:
        mood = "depressed"
        escalate = True
    elif sentiment <= -0.25:
        mood = "sad"
        escalate = False
    elif sentiment >= 0.25:
        mood = "happy"
        escalate = False
    else:
        mood = "stressed"
        escalate = False

    return jsonify({"mood": mood, "score": sentiment, "escalate": escalate}), 200

# --- Personalized Suggestions ---
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    mood = data.get('mood', 'neutral')

    recommendations = {
        "happy": [
            "Read 'Atomic Habits'",
            "Listen to upbeat music",
            "Share your happiness with a friend"
        ],
        "sad": [
            "Read 'The Alchemist'",
            "Watch a TED talk",
            "Try journaling your feelings"
        ],
        "stressed": [
            "Try 5 min meditation",
            "Read 'The Power of Now'",
            "Take a short walk"
        ],
        "depressed": [
            "Connect with psychologist",
            "Call a helpline",
            "Reach out to a trusted person"
        ]
    }

    # Optionally, fetch a quote from an API
    quote = None
    try:
        r = requests.get("https://api.quotable.io/random")
        if r.ok:
            quote = r.json().get("content")
    except:
        pass

    return jsonify({
        "mood": mood,
        "suggestions": recommendations.get(mood, ["Take a walk", "Listen to music"]),
        "quote": quote
    }), 200

# --- Chatbot (Gemini) ---
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    user_id = request.json.get("user_id")

    if not user_message or not user_id:
        return jsonify({"reply": "Please enter a message."})

    history = chat_history.get(user_id, [])
    history.append({"user": user_message})

    conversation = ""
    for msg in history[-10:]:
        if "user" in msg:
            conversation += f"User: {msg['user']}\n"
        if "bot" in msg:
            conversation += f"Bot: {msg['bot']}\n"

    reply = get_gemini_reply(conversation)
    history.append({"bot": reply})
    chat_history[user_id] = history

    return jsonify({"reply": reply})

# --- Voice chat (audio mood + chatbot) ---
@app.route("/voice", methods=["POST"])
def voice():
    user_id = request.form.get("user_id")
    if not user_id:
        return jsonify({"reply": "Missing user ID."})

    if "audio" not in request.files:
        return jsonify({"reply": "No audio file uploaded."})

    audio_file = request.files["audio"]
    filename = secure_filename(audio_file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    audio_file.save(filepath)

    transcript = transcribe_audio_deepgram(filepath)
    os.remove(filepath)

    if not transcript:
        return jsonify({"reply": "Sorry, I couldn't understand your voice."})

    history = chat_history.get(user_id, [])
    history.append({"user": transcript})

    conversation = ""
    for msg in history[-10:]:
        if "user" in msg:
            conversation += f"User: {msg['user']}\n"
        if "bot" in msg:
            conversation += f"Bot: {msg['bot']}\n"

    reply = get_gemini_reply(conversation)
    history.append({"bot": reply})
    chat_history[user_id] = history

    return jsonify({"reply": reply})

# --- Firebase Token Verification ---
from firebase_admin import auth

def verify_firebase_token(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token  # Contains uid, email, etc.
    except Exception as e:
        print("Token verification failed:", e)
        return None

def get_authenticated_user():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    id_token = auth_header.split(" ")[1]
    return verify_firebase_token(id_token)

# Example: Protect an endpoint
@app.route('/protected', methods=['GET'])
def protected():
    user = get_authenticated_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"message": f"Hello, {user['email']}!"})

if __name__ == '__main__':
    app.run(debug=True)