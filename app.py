from flask import Flask, render_template, session, url_for, abort, request, redirect, send_from_directory, jsonify
from google_auth_oauthlib.flow import Flow
import os
from dotenv import load_dotenv
import mysql.connector
from flask_session import Session
import requests
from pubnub import Pubnub
from dotenv import load_dotenv
from pubnub.pam import AccessManager

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "autosiren")
    )

pubnub = Pubnub(publish_key=os.getenv("PUBNUB_PUBLISH_KEY"),
                subscribe_key=os.getenv("PUBNUB_SUBSCRIBE_KEY"))

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'session'
Session(app)

def pubnub_callback(message, channel):
    print(f"Received message from {channel}: {message}")

pubnub.subscribe(channels=["iot_channel"], callback=pubnub_callback)

pam = AccessManager(pubnub)

pubnub.grant(
    channels=["iot_channel"],
    read=True,
    write=True,
    ttl=60,
    auth_keys=["device_auth_key"]
)


@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")


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
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/protected_area")
def protected_area():
    email = session.get("email")
    return f"""
        Hello, {email}! Welcome to the protected area.
        <a href='/logout'><button>Log out</button></a>
    """

@app.route('/facebook_login', methods=['POST'])
def facebook_login():
    data = request.get_json()
    access_token = data.get('accessToken')

    validation_url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={app.config['FACEBOOK_APP_ID']}|{app.config['FACEBOOK_APP_SECRET']}"
    response = requests.get(validation_url)
    result = response.json()

    if result.get('data', {}).get('is_valid'):
        user_info = requests.get(f'https://graph.facebook.com/me?fields=id,name,email&access_token={access_token}')
        user_data = user_info.json()
        return jsonify(user_data)
    else:
        return jsonify({'error': 'Invalid token'}), 400

if __name__ == "__main__":
    app.run(debug=True)
