from flask import Flask, request, jsonify, render_template
import firebase_admin
from firebase_admin import credentials, firestore, auth
from textblob import TextBlob
from flask_cors import CORS
import requests
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
import json
import statistics
import time

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
# chat_history = {}  # {user_id: [{"user": "...", "bot": "..."}, ...]}

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

    # store a timestamp so we can analyze trends over time
    db.collection('journals').add({
        "user_id": user_id,
        "journal": journal_text,
        "timestamp": firestore.SERVER_TIMESTAMP  # or int(time.time()*1000)
    })
    return jsonify({"message": "Journal saved!"}), 200

@app.route('/get_journal', methods=['GET'])
def get_journal():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    try:
        docs = db.collection('journals').where('user_id', '==', user_id) \
            .order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        journals = []
        for d in docs:
            data = d.to_dict()
            ts = data.get("timestamp")
            # Handle Firestore Timestamp, float, int, or None
            if hasattr(ts, "timestamp"):
                ts_val = int(ts.timestamp() * 1000)
            elif isinstance(ts, (float, int)):
                ts_val = int(ts)
            else:
                ts_val = 0  # fallback if missing
            journals.append({
                "journal": data.get("journal", ""),
                "timestamp": ts_val
            })
        return jsonify({"journals": journals}), 200
    except Exception as e:
        print("get_journal error:", e)
        return jsonify({"error": "Failed to fetch journals"}), 500

# New endpoint: analyze mood trends from journals and ask Gemini for suggestions
@app.route('/recommend_from_journals', methods=['POST'])
def recommend_from_journals():
    data = request.json or {}
    # Ignore any manual mood sent by frontend — derive mood from journals only
    data.pop('mood', None)

    user_id = data.get('user_id')
    max_entries = int(data.get('max_entries', 12))

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    try:
        docs = db.collection('journals').where('user_id', '==', user_id) \
            .order_by('timestamp', direction=firestore.Query.DESCENDING) \
            .limit(max_entries).stream()
        entries = [d.to_dict() for d in docs]
    except Exception:
        entries = []

    # --- CASE 1: No journals (new user) ---
    if not entries:
        mood = "happy"
        prompt = (
            "You are an empathetic assistant. The user is new and has no journal history. "
            "Generate a JSON object ONLY with the keys: "
            "\"suggestions\" (5 short actionable items), "
            "\"quote\" (short motivational quote), "
            "\"mood\" (set to 'happy'), "
            "\"trend\" (set to 'no_data'), "
            "\"details\" (object with keys: \"books\", \"movies\", \"web_series\", \"activities\"; "
            "each an array of 3 short items). "
            "Do NOT include any extra text outside JSON."
        )
    else:
        # --- CASE 2: Existing user ---
        latest_text = entries[0].get('journal', '').strip()
        try:
            latest_score = TextBlob(latest_text).sentiment.polarity
        except Exception:
            latest_score = 0.0

        # Map sentiment → mood
        if latest_score <= -0.5:
            mood = "depressed"
        elif latest_score <= -0.25:
            mood = "sad"
        elif latest_score >= 0.25:
            mood = "happy"
        else:
            mood = "stressed"

        # Collect last few journals
        recent_texts = []
        for e in entries[:6]:
            j = e.get('journal', '').strip()
            if j:
                recent_texts.append(j if len(j) <= 800 else j[:800] + "...")

        prompt = (
            "You are an empathetic assistant. Analyze the user's journals and provide tailored suggestions. "
            "Generate a JSON object ONLY with the keys: "
            "\"suggestions\" (5 short actionable items), "
            "\"quote\" (short motivational quote), "
            "\"mood\" (detected mood), "
            "\"trend\" (improving/steady/worsening), "
            "\"details\" (object with keys: \"books\", \"movies\", \"web_series\", \"activities\"; "
            "each an array of 3 short items). "
            "Do NOT include any extra text outside JSON.\n\n"
            f"Latest journal sentiment: {latest_score:.3f} → {mood}\n\n"
            "Recent entries:\n" + "\n".join([f"- {t}" for t in recent_texts])
        )

# --- Call Gemini ---
    reply = get_gemini_reply(prompt)

    parsed = None
    try:
        start, end = reply.find('{'), reply.rfind('}')
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(reply[start:end+1])
    except Exception:
        parsed = None

    if parsed and isinstance(parsed, dict):
        return jsonify(parsed), 200

    # --- Fallback JSON ---
    return jsonify({
        "mood": "happy" if not entries else mood,
        "trend": "no_data" if not entries else "steady",
        "suggestions": ["Take a short walk", "Write one positive thought"],
        "quote": "Every day may not be good, but there's something good in every day.",
        "details": {"books": [], "movies": [], "web_series": [], "activities": []}
    }), 200

# --- Personalized Suggestions ---
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json or {}
    user_id = data.get('user_id')

    # Default mood
    mood = "happy"
    has_journals = False

    # Check for latest journal to determine mood
    if user_id:
        try:
            docs = db.collection('journals').where('user_id', '==', user_id).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()
            latest = None
            for d in docs:
                latest = d.to_dict().get('journal', '')
                break
            if latest:
                has_journals = True
                try:
                    sc = TextBlob(latest).sentiment.polarity
                except Exception:
                    sc = 0.0
                if sc <= -0.5:
                    mood = "depressed"
                elif sc <= -0.25:
                    mood = "sad"
                elif sc >= 0.25:
                    mood = "happy"
                else:
                    mood = "stressed"
        except Exception:
            pass

    # Build Gemini prompt
    if not has_journals:
        prompt = (
            "You are an empathetic assistant. The user is new and has no journal history. "
            "Generate a JSON object ONLY with the keys: "
            "\"suggestions\" (5 short actionable items), "
            "\"quote\" (short motivational quote), "
            "\"mood\" (set to 'happy'), "
            "\"trend\" (set to 'no_data'), "
            "\"details\" (object with keys: \"books\", \"movies\", \"web_series\", \"activities\"; "
            "each an array of 3 short items, all recommendations must be powered by Gemini and suitable for a positive, uplifting mood). "
            "Do NOT include any extra text outside JSON."
        )
    else:
        prompt = (
            "You are an empathetic personal assistant. Based on the user's current mood, return a JSON object "
            "exactly with the following keys: "
            "\"suggestions\" (an array of 5 short actionable suggestion strings), "
            "\"quote\" (a short motivational quote), "
            "\"details\" (an object with keys: \"books\", \"movies\", \"web_series\", \"activities\"; each is an array of 3 short items, all recommendations must be powered by Gemini and tailored to the user's mood). "
            "Do NOT include any extra text outside the JSON object.\n\n"
            f"User mood: {mood}\n\n"
            "Requirements:\n"
            "- Provide 5 concise, varied suggestions in the top-level \"suggestions\" array (one sentence each).\n"
            "- In \"details\" include 3 items each for \"books\", \"movies\", \"web_series\", and \"activities\" tailored to the mood.\n"
            "- All recommendations must be Gemini-powered and relevant.\n"
            "- Keep items short (<= 6 words for titles, 1 short phrase for activities).\n\n"
            "Example output:\n"
            '{"suggestions":["..."],"quote":"...","details":{"books":["..."],"movies":["..."],"web_series":["..."],"activities":["..."]}}\n'
        )

    try:
        reply = get_gemini_reply(prompt)
    except Exception as e:
        reply = ""

    parsed = None
    suggestions = []
    quote = None
    details = {"books": [], "movies": [], "web_series": [], "activities": []}

    # Try to extract JSON object from reply
    try:
        start = reply.find('{')
        end = reply.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_text = reply[start:end+1]
            parsed = json.loads(json_text)
    except Exception:
        parsed = None

    if parsed and isinstance(parsed, dict):
        suggestions = parsed.get('suggestions') or []
        quote = parsed.get('quote')
        details = parsed.get('details') or details
        # normalize missing categories
        for k in ["books", "movies", "web_series", "activities"]:
            if k not in details or not isinstance(details[k], list):
                details[k] = []
    else:
        # Fallback: generate a simple set based on mood (safe defaults)
        if mood == "happy":
            suggestions = [
                "Keep a short gratitude list each morning.",
                "Share a fun moment with a friend.",
                "Schedule a 20-minute creative session.",
                "Try a new upbeat playlist today.",
                "Go for a brisk 15-minute walk."
            ]
            details = {
                "books": ["Atomic Habits", "The Four Agreements", "The Little Prince"],
                "movies": ["Amélie", "Paddington 2", "The Intouchables"],
                "web_series": ["Ted Lasso", "The Good Place", "Schitt's Creek"],
                "activities": ["Short walk", "Dance to a song", "Call a friend"]
            }
            quote = quote or "Every day may hold a small joy."
        elif mood == "sad" or mood == "stressed" or mood == "depressed":
            suggestions = [
                "Try a 5-minute grounding breath exercise.",
                "Write down three small wins today.",
                "Take a short break and step outside.",
                "Call or message someone you trust.",
                "Try a calming activity (drawing, stretching)."
            ]
            details = {
                "books": ["The Alchemist", "Man's Search for Meaning", "Wherever You Go, There You Are"],
                "movies": ["Inside Out", "Good Will Hunting", "Silver Linings Playbook"],
                "web_series": ["Anne with an E", "After Life", "Normal People"],
                "activities": ["Deep breathing", "Short walk", "Gentle stretching"]
            }
            quote = quote or "Small steps are real progress."
        else:
            # default neutral suggestions
            suggestions = [
                "Take 10 minutes to reflect on today's highlights.",
                "Try a short breathing or mindfulness exercise.",
                "Listen to a calming playlist.",
                "Write one thing you're grateful for.",
                "Step outside for fresh air."
            ]
            details = {
                "books": ["The Power of Now", "The Art of Happiness", "Mindfulness in Plain English"],
                "movies": ["About Time", "Finding Forrester", "The Secret Life of Walter Mitty"],
                "web_series": ["Master of None", "Chef's Table", "Somebody Feed Phil"],
                "activities": ["10 min meditation", "Short walk", "Read a chapter"]
            }
            quote = quote or "Pause, breathe, and take one step."

    # Flatten suggestions from details if suggestions empty
    if not suggestions:
        flattened = []
        for cat in ["books", "movies", "web_series", "activities"]:
            flattened.extend(details.get(cat, []))
        suggestions = flattened[:8]  # limit size

    return jsonify({
        "mood": mood,
        "suggestions": suggestions,
        "quote": quote,
        "details": details
    }), 200

# --- Chatbot (Gemini) ---
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    user_id = request.json.get("user_id")

    if not user_message or not user_id:
        return jsonify({"reply": "Please enter a message."})

    # No chat history; just send the latest message to Gemini
    conversation = f"User: {user_message}\nBot:"
    reply = get_gemini_reply(conversation)

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

    # No chat history; just send the transcript to Gemini
    conversation = f"User: {transcript}\nBot:"
    reply = get_gemini_reply(conversation)

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

# --- Analyze a single journal entry (used by frontend 'Analyze Mood') ---
@app.route('/analyze_journal', methods=['POST'])
def analyze_journal():
    """
    Accepts JSON body:
      { "journal": "...", "user_id": "..." (optional) }
    If 'journal' provided, analyze that. Otherwise, if user_id provided, analyze the latest journal.
    Returns: { mood: str, score: float, escalate: bool, reason: str (optional) }
    """
    data = request.json or {}
    text = (data.get('journal') or '').strip()
    user_id = data.get('user_id')

    # If no explicit journal text, try to fetch latest journal for user_id
    if not text and user_id:
        try:
            docs = db.collection('journals').where('user_id', '==', user_id) \
                .order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()
            latest = None
            for d in docs:
                latest = d.to_dict().get('journal','')
                break
            text = (latest or '').strip()
        except Exception as e:
            print("analyze_journal: failed to fetch latest journal:", e)
            text = ""

    if not text:
        return jsonify({"error": "Missing journal text or no journal entries for user"}), 400

    # Sentiment analysis
    try:
        score = float(TextBlob(text).sentiment.polarity)
    except Exception as e:
        print("analyze_journal: TextBlob error:", e)
        score = 0.0

    # Map polarity to mood
    if score <= -0.6:
        mood = "depressed"
    elif score <= -0.25:
        mood = "sad"
    elif score >= 0.25:
        mood = "happy"
    else:
        mood = "stressed"

    # Escalation heuristic: strong negative sentiment or explicit self-harm keywords
    escalate = False
    reason = ""
    try:
        lowered = text.lower()
        harm_keywords = ["suicide", "kill myself", "end my life", "i want to die", "hurt myself", "die by suicide", "self harm", "want to die"]
        if score <= -0.65:
            escalate = True
            reason = "very negative sentiment"
        for kw in harm_keywords:
            if kw in lowered:
                escalate = True
                reason = f"contains keyword: {kw}"
                break
    except Exception as e:
        print("analyze_journal: escalation check error:", e)

    return jsonify({
        "mood": mood,
        "score": round(score, 3),
        "escalate": escalate,
        "reason": reason
    }), 200

if __name__ == '__main__':
    app.run(debug=True)