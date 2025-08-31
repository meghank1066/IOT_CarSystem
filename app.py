from flask import Flask, render_template, session, url_for, request, redirect, send_from_directory, jsonify
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
import mysql.connector
from flask_session import Session
from pubnub.pubnub import PubNub
from pubnub.pnconfiguration import PNConfiguration
from pubnub.callbacks import SubscribeCallback
from car_options import CAR_OPTIONS
import random
from pi_code.motion import start_motion_monitor
# from pi_code.fan_control import some_function


load_dotenv()

# flask

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# pubnub
pnconfig = PNConfiguration()
pnconfig.publish_key = os.getenv("PUBNUB_PUBLISH_KEY")
pnconfig.subscribe_key = os.getenv("PUBNUB_SUBSCRIBE_KEY")
pnconfig.ssl = True
pnconfig.cipher_key = os.getenv("PUBNUB_CIPHER_KEY")
pnconfig.uuid  = os.getenv("PUBNUB_UUID")
pubnub = PubNub(pnconfig)



# pi code
def log_motion_event(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO motion_events (status) VALUES (%s)", (status,))
    conn.commit()
    cursor.close()
    conn.close()
    
start_motion_monitor(pubnub, log_motion_event)


# ##testing ref:copilot
# import threading
# import time

# # Shared motion state
# motion_status = "clear"
# gpio_available = False  # Default to False

# # Try importing gpiozero only if available (i.e., on Raspberry Pi)
# try:
#     from gpiozero import MotionSensor, LED
#     gpio_available = True
# except ImportError:
#     print("GPIOZero not available — running in non-Pi mode.")

# # Setup GPIO devices only if available
# if gpio_available:
#     green_led = LED(17)
#     pir = MotionSensor(4)
#     green_led.off()
# else:
#     green_led = None
#     pir = None


# # Setup
# green_led = LED(17)
# pir = MotionSensor(4)
# green_led.off()

# # Shared motion state
# from gpiozero import MotionSensor, LED
# motion_status = "clear"


# motion_status = "clear"

# def monitor_motion():
#     global motion_status
#     if not gpio_available:
#         print("Skipping motion monitoring — GPIO not available.")
#         return

#     while True:
#         pir.wait_for_motion()
#         motion_status = "detected"
#         green_led.on()
#         print("Motion detected")
#         pubnub.publish().channel("iot_channel").message({"motion": motion_status}).sync()
#         log_motion_event(motion_status)

#         pir.wait_for_no_motion()
#         motion_status = "clear"
#         green_led.off()
#         print("Motion stopped")
#         pubnub.publish().channel("iot_channel").message({"motion": motion_status}).sync()
#         log_motion_event(motion_status)
#         time.sleep(0.1)
# # Start sensor monitoring in a background thread
# motion_thread = threading.Thread(target=monitor_motion, daemon=True)
# motion_thread.start()



# google oauth

oauth = OAuth(app)
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
google = oauth.register(
    name='google',
    server_metadata_url=CONF_URL,
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    client_kwargs={'scope': 'openid email profile'}
)

# database

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "autosiren")
    )

# flask app
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'session'
Session(app)

pubnub.publish().channel("iot_channel").message({"data": "Hello IoT!"}).sync()

@app.route("/pubnub/token")
def pubnub_token():
   token_result = pubnub.grant_token() \
        .resources() \
        .channels({"iot_channel": {"read": True, "write": True}}) \
        .ttl(60) \
        .sync()
   return jsonify({"token": token_result.token})

class CarListener(SubscribeCallback):
    def message(self, pubnub, message):
        print("Received:", message.message)

pubnub.add_listener(CarListener())
pubnub.subscribe().channels("iot_channel").execute()

@app.route("/", methods=["GET", "POST"])
def index():
    pubnub_subscribe_key = os.getenv("PUBNUB_SUBSCRIBE_KEY")
    pubnub_publish_key = os.getenv("PUBNUB_PUBLISH_KEY")

    car = None
    if 'user' in session:
        session['email'] = session['user']['email']
        car = get_user_car(session['user']['sub'])
    else:
        session.pop('email', None)

    return render_template("index.html", 
                           pubnub_subscribe_key=pubnub_subscribe_key,
                           pubnub_publish_key=pubnub_publish_key,
                           car=car)

@app.route("/send_data", methods=["POST"])
def send_data():
    data = request.get_json()
    if data:
        message = data.get("message")
        pubnub.publish(channel="iot_channel", message={"data": message}, callback=lambda m: print("Message published:", m))
        return jsonify({"status": "success", "message": "Data sent to IoT device"})
    return jsonify({"status": "error", "message": "Invalid data"})


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/login")
def login():
  redirect_uri = url_for('authorize', _external=True)
  return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = token['userinfo']
    session['user'] = user_info
    session['email'] = user_info['email']
    store_user(user_info)
    return redirect(url_for('index'))

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route("/protected_area")
def protected_area():
    email = session.get("email")
    return f"""
        Hello, {email}! Welcome to the protected area.
        <a href='/logout'><button>Log out</button></a>
    """
# pi stuff 

@app.route("/test_log")
def test_log():
    log_motion_event("detected")
    return "Logged test motion event"

@app.route("/motion_status")
def get_motion_status():
    return jsonify({"motion": motion_status})

# @app.route("/fan/on")
# def fan_on():
#     # TODO: Add GPIO code to turn fan on
#     pubnub.publish().channel("iot_channel").message({"fan": "on"}).sync()
#     return jsonify({"status": "Fan turned on"})

# @app.route("/fan/off")
# def fan_off():
#     # TODO: Add GPIO code to turn fan off
#     pubnub.publish().channel("iot_channel").message({"fan": "off"}).sync()
#     return jsonify({"status": "Fan turned off"})

# //ref: microsoft copilot 

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
        # Insert new user
        cursor.execute("""
            INSERT INTO users (google_id, name, email)
            VALUES (%s, %s, %s)
        """, (user_info['sub'], user_info['name'], user_info['email']))
        conn.commit()
        user_id = cursor.lastrowid

        # Pick a random car
        car = random.choice(CAR_OPTIONS)

        # Assign car to user
        cursor.execute("""
            INSERT INTO cars (user_id, model, license_plate, year, color, engine, transmission, drive_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            car["model"],
            car["license_plate"],
            car["year"],
            car["color"],
            car["engine"],
            car["transmission"],
            car["drive_type"]
        ))
        conn.commit()

    cursor.close()
    conn.close()




if __name__ == "__main__":
    app.run(debug=True)
