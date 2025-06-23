import streamlit as st
import openai
from PIL import Image
import pytesseract
import speech_recognition as sr
import psycopg2
import bcrypt
import base64
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="AI Math Agent", page_icon="🧮", layout="centered", initial_sidebar_state="auto")

# --- COLOR THEME ---
PRIMARY_COLOR = "#18181B"  # Black
SECONDARY_COLOR = "#1E293B"  # Blue
ACCENT_COLOR = "#FF69B4"  # Light Pink
BG_GRADIENT = f"linear-gradient(90deg, {PRIMARY_COLOR} 0%, {SECONDARY_COLOR} 60%, {ACCENT_COLOR} 100%)"

# --- POSTGRESQL DATABASE SETUP ---
DB_HOST = "localhost"
DB_NAME = "aiagent"
DB_USER = "postgres"
DB_PASS = "yourpassword"  # <-- Replace with your Postgres password

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def create_users_table():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(50) PRIMARY KEY,
            password BYTEA
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def add_user(username, password):
    conn = get_db_conn()
    cur = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
    conn.commit()
    cur.close()
    conn.close()

def check_user(username, password):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=%s", (username,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    if result:
        return bcrypt.checkpw(password.encode(), result[0])
    return False

def user_exists(username):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username=%s", (username,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None

create_users_table()

# --- OPENAI API KEY ---
openai.api_key = "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"  # <-- Replace with your OpenAI API key

# --- SVG BANNER ---
def render_banner():
    svg = f"""
    <svg width="100%" height="120" viewBox="0 0 800 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="grad1" x1="0" y1="0" x2="800" y2="0" gradientUnits="userSpaceOnUse">
          <stop stop-color="{PRIMARY_COLOR}"/>
          <stop offset="0.6" stop-color="{SECONDARY_COLOR}"/>
          <stop offset="1" stop-color="{ACCENT_COLOR}"/>
        </linearGradient>
      </defs>
      <rect width="800" height="120" fill="url(#grad1)"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="48" fill="#fff" font-family="Arial Black, Arial, sans-serif">AI Math Agent</text>
      <g>
        <circle cx="60" cy="60" r="30" fill="#60A5FA" opacity="0.3"/>
        <circle cx="740" cy="60" r="30" fill="{ACCENT_COLOR}" opacity="0.3"/>
        <text x="60" y="70" font-size="40" text-anchor="middle" fill="#fff">🧮</text>
        <text x="740" y="70" font-size="40" text-anchor="middle" fill="#fff">🤖</text>
      </g>
    </svg>
    """
    st.markdown(f'<div style="margin-bottom: 1rem;">{svg}</div>', unsafe_allow_html=True)

# --- CUSTOM CSS FOR DESIGN ---
st.markdown(f"""
    <style>
    .stApp {{
        background: {BG_GRADIENT};
        color: #fff;
    }}
    .stTextInput > div > div > input, .stTextArea textarea {{
        background: #232336;
        color: #fff;
        border-radius: 8px;
        border: 1px solid {ACCENT_COLOR};
    }}
    .stButton > button {{
        background: {ACCENT_COLOR};
        color: #fff;
        border-radius: 8px;
        font-weight: bold;
    }}
    .stChatMessage {{
        background: #232336;
        border-radius: 10px;
        margin-bottom: 8px;
        padding: 10px;
        color: #fff;
    }}
    </style>
""", unsafe_allow_html=True)

# --- LOGIN/SIGNUP LOGIC ---
def login_signup():
    st.sidebar.title("🔐 Login / Signup")
    mode = st.sidebar.radio("Choose mode", ["Login", "Signup"])
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    login_status = False
    if mode == "Signup":
        if st.sidebar.button("Create Account"):
            if not username or not password:
                st.sidebar.error("Please enter username and password.")
            elif user_exists(username):
                st.sidebar.error("Username already exists.")
            else:
                add_user(username, password)
                st.sidebar.success("Account created! Please login.")
    else:
        if st.sidebar.button("Login"):
            if check_user(username, password):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                login_status = True
                st.sidebar.success("Logged in successfully!")
            else:
                st.sidebar.error("Invalid username or password.")
    return st.session_state.get("logged_in", False)

# --- MATH AGENT CHAT LOGIC ---
def get_math_response(prompt):
    system_prompt = (
        "You are an expert AI math tutor. "
        "Answer the user's math question step by step, clearly and concisely. "
        "If the question is not math-related, politely ask for a math query."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=512,
            temperature=0.2,
        )
        content = response.choices[0].message.content if response.choices and response.choices[0].message and hasattr(response.choices[0].message, "content") else None
        if content is not None:
            return content.strip()
        else:
            return "Error: No response from model."
    except Exception as e:
        return f"Error: {e}"

def extract_text_from_image(image):
    try:
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return f"Error extracting text: {e}"

def extract_text_from_audio(audio_bytes):
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
        audio = recognizer.record(source)
        try:
            # Use the recognize_google method from the recognizer instance
            text = recognizer.recognize_google(audio)  # type: ignore
            return text
        except Exception as e:
            return f"Error recognizing speech: {e}"

# --- MAIN APP ---
def main():
    render_banner()
    st.markdown(
        f"<h3 style='color:{ACCENT_COLOR};text-align:center;'>Ask your Math Questions via Text, Voice, or Image!</h3>",
        unsafe_allow_html=True
    )

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # --- Input Tabs ---
    tab1, tab2, tab3 = st.tabs(["💬 Text", "🎤 Voice", "🖼️ Image"])

    user_input = None

    with tab1:
        user_input = st.text_area("Type your math question here:", key="text_input")
        if st.button("Send (Text)", key="send_text"):
            if user_input.strip():
                st.session_state["chat_history"].append(("user", user_input.strip()))
                response = get_math_response(user_input.strip())
                st.session_state["chat_history"].append(("ai", response))
            else:
                st.warning("Please enter a question.")

    with tab2:
        audio_file = st.file_uploader("Upload a voice question (wav/mp3)", type=["wav", "mp3"], key="audio_input")
        if st.button("Send (Voice)", key="send_voice"):
            if audio_file is not None:
                audio_bytes = audio_file.read()
                try:
                    text = extract_text_from_audio(audio_bytes)
                    st.session_state["chat_history"].append(("user", f"[Voice] {text}"))
                    response = get_math_response(text)
                    st.session_state["chat_history"].append(("ai", response))
                except Exception as e:
                    st.error(f"Error processing audio: {e}")
            else:
                st.warning("Please upload an audio file.")

    with tab3:
        image_file = st.file_uploader("Upload an image with a math question", type=["png", "jpg", "jpeg"], key="image_input")
        if st.button("Send (Image)", key="send_image"):
            if image_file is not None:
                image = Image.open(image_file)
                text = extract_text_from_image(image)
                st.session_state["chat_history"].append(("user", f"[Image] {text}"))
                response = get_math_response(text)
                st.session_state["chat_history"].append(("ai", response))
            else:
                st.warning("Please upload an image.")

    # --- Chat Display ---
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='color:{SECONDARY_COLOR};'>Chat History</h4>", unsafe_allow_html=True)
    for sender, message in st.session_state["chat_history"]:
        if sender == "user":
            st.markdown(
                f"<div class='stChatMessage' style='background:{SECONDARY_COLOR};text-align:right;'><b>You:</b> {message}</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div class='stChatMessage' style='background:{ACCENT_COLOR};color:#18181B;'><b>AI:</b> {message}</div>",
                unsafe_allow_html=True
            )

    if st.button("Clear Chat"):
        st.session_state["chat_history"] = []

# --- APP ENTRYPOINT ---
if __name__ == "__main__":
    if login_signup():
        main()
    else:
        st.warning("Please login or signup to use the AI Math Agent.")
