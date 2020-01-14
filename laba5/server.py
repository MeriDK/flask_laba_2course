import datetime
import os

import jwt
import requests
from flask import Flask, request, jsonify, make_response
import couchdb
from flask_swagger_ui import get_swaggerui_blueprint
import config as cfg


"""
user = cfg.db['user']
password = cfg.db['password']
host = cfg.db['host']
host = os.getenv('host')
couch = couchdb.Server('http://%s:%s@%s/' % (user, password, host))


"""

user = os.getenv('user')
password = os.getenv('password')
host = os.getenv('host')
couch = couchdb.Server('http://%s:%s@%s/' % (user, password, host))

events_db_name = cfg.events_db_name
users_db_name = cfg.users_db_name

app = Flask(__name__)


# swagger specific
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': 'test'
    }
)
app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)


def encode_auth_token(user_id):
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=0, seconds=60),
            'iat': datetime.datetime.utcnow(),
            'sub': user_id
        }
        return jwt.encode(
            payload,
            cfg.SECRET_KEY,
            algorithm='HS256'
        )
    except Exception as e:
        return e


def decode_auth_token(auth_token):
    try:
        payload = jwt.decode(auth_token, cfg.SECRET_KEY)
        return payload['sub']
    except jwt.ExpiredSignatureError:
        return 'Signature expired. Please log in again.'
    except jwt.InvalidTokenError:
        return 'Invalid token. Please log in again.'


@app.route('/events/', methods=['GET'])
def get_all():
    db = couch[events_db_name]
    res = {}
    for event in db:
        res[event] = db[event]
    return jsonify(res)


@app.route('/events/<user_id>', methods=['POST'])
def create_event(user_id):
    try:
        token = request.headers['token']
        print(user_id)
        print(type(token))
        print(decode_auth_token(token))

        db = couch[events_db_name]
        uuid = requests.get('http://127.0.0.1:5984/_uuids').json()['uuids'][0]

        event = {
            'users': [user_id],
            'date': request.json['date'],
            'description': request.json['description']
        }

        db[uuid] = event

        users = couch[users_db_name]
        userok = users[user_id]
        userok['events'].append(uuid)
        users.save(userok)

        return uuid
    except KeyError:
        return make_response(jsonify('date and description are obligatory'), 500)


@app.route('/events/<event_id>', methods=['GET'])
def get_event(event_id):
    try:
        return jsonify(couch[events_db_name][event_id])
    except couchdb.http.ResourceNotFound:
        return make_response(jsonify('events id not found'), 404)


@app.route('/events/<event_id>', methods=['PUT'])
def update_event(event_id):
    try:
        db = couch[events_db_name]
        event = db[event_id]

        for key, value in request.json.items():
            event[key] = value

        db.save(event)
        return 'Updated'
    except couchdb.http.ResourceNotFound:
        return make_response(jsonify('event id not found'), 404)


@app.route('/events/<event_id>/<user_id>', methods=['PUT'])
def add_user_to_event(event_id, user_id):
    try:
        db = couch[events_db_name]
        event = db[event_id]

        users = event['users']
        users.append(user_id)

        db.save(event)

        db = couch[users_db_name]
        userok = db[user_id]
        userok['events'].append(event_id)
        db.save(userok)

        return jsonify('Added')
    except couchdb.http.ResourceNotFound:
        return make_response(jsonify('event or user id not found'), 404)


@app.route('/events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    try:
        db = couch[events_db_name]
        users = couch[users_db_name]
        event = db[event_id]

        for u in event['users']:
            userok = users[u]
            userok['events'].remove(event_id)
            users.save(userok)

        return 'Deleted'
    except couchdb.http.ResourceNotFound:
        return make_response(jsonify('event id not found'), 404)


@app.route('/users/<user_id>', methods=['GET'])
def get_users_events(user_id):
    try:
        return jsonify(couch[users_db_name][user_id]['events'])
    except couchdb.http.ResourceNotFound:
        return make_response(jsonify('user id not found'), 404)



@app.route('/users/', methods=['POST'])
def create_user():
    try:
        db = couch[users_db_name]
        uuid = requests.get('http://127.0.0.1:5984/_uuids').json()['uuids'][0]
        token = encode_auth_token(uuid)

        userok = {
            'events': []
        }

        db[uuid] = userok

        return uuid
    except KeyError:
        return make_response(jsonify('date and description are obligatory'), 500)


@app.route('/users/', methods=['GET'])
def get_all_users():
    db = couch[users_db_name]
    res = {}
    for user_id in db:
        res[user_id] = db[user_id]
    return jsonify(res)


if __name__ == '__main__':
    app.run(debug=True)
