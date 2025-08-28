from flask import Flask, render_template, session, url_for, abort, request, redirect, send_from_directory, jsonify
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
import mysql.connector
from flask_session import Session
import requests
from pubnub.pubnub import PubNub
from pubnub.pnconfiguration import PNConfiguration
from pubnub.models.consumer.access_manager import PNGrantTokenResult

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
pnconfig.uuid = "server-app"
# pnconfig.user_id = "server-app"

pubnub = PubNub(pnconfig)







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
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
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
    token_result: PNGrantTokenResult = pubnub.grant_token() \
        .resources() \
        .channels({"iot_channel": {"read": True, "write": True}}) \
        .ttl(60) \
        .sync()

    return jsonify({"token": token_result.token})


@app.route("/", methods=["GET", "POST"])
def index():
    if 'user' in session:
        session['email'] = session['user']['email']
    else:
        session.pop('email', None)
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
  redirect_uri = url_for('authorize', _external=True)
  return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = token['userinfo']
    session['user'] = user_info
    session['email'] = user_info['email'] 
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

# @app.route('/facebook_login', methods=['POST'])
# def facebook_login():
#     data = request.get_json()
#     access_token = data.get('accessToken')

#     validation_url = f"https://graph.facebook.com/debug_token?input_token={access_token}&access_token={app.config['FACEBOOK_APP_ID']}|{app.config['FACEBOOK_APP_SECRET']}"
#     response = requests.get(validation_url)
#     result = response.json()

#     if result.get('data', {}).get('is_valid'):
#         user_info = requests.get(f'https://graph.facebook.com/me?fields=id,name,email&access_token={access_token}')
#         user_data = user_info.json()
#         return jsonify(user_data)
#     else:
#         return jsonify({'error': 'Invalid token'}), 400

if __name__ == "__main__":
    app.run(debug=True)
