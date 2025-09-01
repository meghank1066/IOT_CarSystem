import os
import platform
import random
import tempfile
from flask import Flask, render_template, session, url_for, request, redirect, jsonify, send_from_directory
from flask_session import Session
from dotenv import load_dotenv
import mysql.connector
from authlib.integrations.flask_client import OAuth

# Optional PubNub
from pubnub.pubnub import PubNub
from pubnub.pnconfiguration import PNConfiguration
from pubnub.callbacks import SubscribeCallback

# Local car options

CAR_OPTIONS = [
    {
        "model": "Porsche 911",
        "license_plate": "1234 ABC",
        "year": 2022,
        "color": "Black",
        "engine": "3.0L Twin-Turbo Boxer 6",
        "transmission": "8-speed PDK",
        "drive_type": "AWD"
    },
    {
        "model": "Tesla Model 3",
        "license_plate": "5678 XYZ",
        "year": 2023,
        "color": "White",
        "engine": "Electric Dual Motor",
        "transmission": "Single-Speed",
        "drive_type": "RWD"
    },
    {
        "model": "BMW M4 Competition",
        "license_plate": "M4 FAST",
        "year": 2021,
        "color": "Blue",
        "engine": "3.0L Twin-Turbo I6",
        "transmission": "8-speed Automatic",
        "drive_type": "RWD"
    },
    {
        "model": "Audi RS Q8",
        "license_plate": "RSQ8 88",
        "year": 2022,
        "color": "Red",
        "engine": "4.0L Twin-Turbo V8",
        "transmission": "8-speed Tiptronic",
        "drive_type": "AWD"
    },
    {
        "model": "Toyota GR Yaris",
        "license_plate": "GR-2023",
        "year": 2023,
        "color": "Grey",
        "engine": "1.6L Turbo I3",
        "transmission": "6-speed Manual",
        "drive_type": "AWD"
    }
]


load_dotenv()

# ----- Flask App Setup -----
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

# ----- Session Config -----
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = tempfile.mkdtemp()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
Session(app)

# ----- PubNub Setup -----
try:
    pnconfig = PNConfiguration()
    pnconfig.publish_key = os.getenv("PUBNUB_PUBLISH_KEY")
    pnconfig.subscribe_key = os.getenv("PUBNUB_SUBSCRIBE_KEY")
    pnconfig.ssl = True
    pnconfig.cipher_key = os.getenv("PUBNUB_CIPHER_KEY")
    pnconfig.uuid = os.getenv("PUBNUB_UUID", "server")
    pubnub = PubNub(pnconfig)

    class PubSubListener(SubscribeCallback):
        def message(self, pubnub, message):
            print("PubNub message:", message.message)

    pubnub.add_listener(PubSubListener())
    # Do NOT call blocking subscribe() here under Apache
except Exception as e:
    print("PubNub setup failed:", e)

# ----- Motion Sensor -----
motion_status = "unknown"

def is_raspberry_pi():
    return platform.machine().startswith("arm") or platform.uname().machine.startswith("arm")

def log_motion_event(status):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO motion_events (status) VALUES (%s)", (status,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("DB log error:", e)

if is_raspberry_pi():
    from pi_code.motion import start_motion_monitor
    motion_status = "clear"
    start_motion_monitor(pubnub, log_motion_event)
else:
    print("Not a Raspberry Pi â€” skipping motion monitor")

# ----- Database Connection -----
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "autosiren")
    )

# ----- OAuth Setup -----
oauth = OAuth(app)
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
google = oauth.register(
    name='google',
    server_metadata_url=CONF_URL,
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    client_kwargs={'scope': 'openid email profile'}
)

# ----- Flask Routes -----
@app.route("/")
def index():
    car = None
    if 'user' in session:
        session['email'] = session['user']['email']
        car = get_user_car(session['user']['sub'])
    else:
        session.pop('email', None)
    return render_template("index.html", car=car,
                           pubnub_publish_key=os.getenv("PUBNUB_PUBLISH_KEY"),
                           pubnub_subscribe_key=os.getenv("PUBNUB_SUBSCRIBE_KEY"))

@app.route("/login")
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/authorize")
def authorize():
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token)
    session['user'] = user_info
    session['email'] = user_info['email']
    store_user(user_info)
    return redirect(url_for('index'))


@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect("/")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/protected_area")
def protected_area():
    email = session.get("email")
    return f"Hello, {email}! <a href='/logout'>Logout</a>"

@app.route("/motion_status")
def get_motion():
    return jsonify({"motion": motion_status})

@app.route("/test_log")
def test_log():
    log_motion_event("detected")
    return "Logged test motion event"

# ----- Database Helpers -----
def get_user_car(google_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.* FROM cars c
        JOIN users u ON u.id = c.user_id
        WHERE u.google_id = %s
    """, (google_id,))
    car = cursor.fetchone()
    cursor.close()
    conn.close()
    return car

def store_user(user_info):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE google_id = %s", (user_info['sub'],))
    result = cursor.fetchone()
    if not result:
        cursor.execute("""
            INSERT INTO users (google_id, name, email)
            VALUES (%s, %s, %s)
        """, (user_info['sub'], user_info['name'], user_info['email']))
        conn.commit()
        user_id = cursor.lastrowid
        car = random.choice(CAR_OPTIONS)
        cursor.execute("""
            INSERT INTO cars (user_id, model, license_plate, year, color, engine, transmission, drive_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, car["model"], car["license_plate"], car["year"],
              car["color"], car["engine"], car["transmission"], car["drive_type"]))
        conn.commit()
    cursor.close()
    conn.close()

# ----- WSGI Entry Point -----
application = app

