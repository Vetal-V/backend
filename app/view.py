from app import app, db
from models import BleData, BleDataSchema, User
from flask import request, jsonify, abort, make_response
from sqlalchemy import func
import uuid # for public id 
from werkzeug.security import generate_password_hash, check_password_hash 
import jwt #for PyJWT authentication 
from datetime import datetime, timedelta 
from functools import wraps 


bleDataSchemaAll = BleDataSchema(many=True)
bleDataSchemaOne = BleDataSchema()

blacklist = set()


# example
@app.route('/hello')
def index():
    return 'Hello world'


# check token in black list
def check_if_token_in_blacklist(token):
    return token in blacklist


# decorator for verifying the JWT 
def token_required(f): 
    @wraps(f) 
    def decorated(*args, **kwargs): 
        token = None
        # jwt is passed in the request header 
        if 'x-access-token' in request.headers: 
            token = request.headers['x-access-token']  
        if not token: 
            return jsonify({'error':'Login required', 'response':None}), 401
        try: 
            # decoding the payload to fetch the stored details 
            if check_if_token_in_blacklist(token):
                raise Exception
            data = jwt.decode(token, app.config['SECRET_KEY']) 
            current_user = User.query.filter_by(public_id = data['public_id']).first() 
        except: 
            return jsonify({'error':'Invalid token', 'response':None}), 401
        # returns the current logged in users contex to the routes 
        return  f(current_user, *args, **kwargs) 

    return decorated 


# get data /api/bledata/ - all data, /api/bledata/?count=NUM&page=NUM - get with pagination
@app.route('/api/bledata/', methods=['GET'])
@token_required
def get_one_page(current_user):
    error = None
    try:
        num_page = int(request.args['page'])
        count_data = int(request.args['count'])
    except:
        num_page = 0
        count_data = 0

    if num_page and count_data:
        try:
            data_page = BleData.query.order_by(BleData.id.desc()).paginate(num_page,count_data,error_out=False)
            data_page_dump = bleDataSchemaAll.dump(data_page.items)
        except Exception as er:
            error = er

        if data_page_dump:
            totalCount = db.session.query(func.count(BleData.id)).scalar()
            result = {'items':data_page_dump, 'totalCount':totalCount, 'error': error}
            return jsonify(result)
        else:
            return not_found(error)
    else:
        all_data = BleData.query.order_by(BleData.id.desc()).all()
        all_data_dump = bleDataSchemaAll.dump(all_data)
        totalCount = db.session.query(func.count(BleData.id)).scalar()
        result = {'items':all_data_dump, 'totalCount':totalCount, 'error': error}
        return jsonify(result)


# upload data to db
@app.route('/api/bledata/upload/', methods=['POST'])
@token_required
def add_one_data(current_user):
    try:
        mac = request.json['mac']
        level = int(request.json['level'])
        time = request.json['time']

        new_data = BleData(mac, level, time)
        db.session.add(new_data)
        db.session.commit()

        return bleDataSchemaOne.jsonify(new_data)

    except Exception as er:
        return jsonify({'error':'wrong data format', 'wrong': str(er)})


# delete all data from db
@app.route('/api/bledata/delete/')
@token_required
def delete_all_data(current_user):
    try:
        num_rows_deleted = db.session.query(BleData).delete()
        db.session.commit()
        return jsonify({"deleted":num_rows_deleted})
    except Exception as er:
        db.session.rollback()
        return jsonify({'error': str(er)})


# get list of users
@app.route('/users', methods =['GET']) 
@token_required
def get_all_users(current_user): 
    users = User.query.all() 
    output = [] 
    for user in users: 
        output.append({ 
            'public_id': user.public_id, 
            'email' : user.email, 
            'username': user.username
        }) 
    return jsonify({'users': output}) 


# loging user in, return token if susses
@app.route('/login', methods =['POST']) 
def login(): 
    # creates dictionary of form data 
    auth = request.form 
   
    if not auth or not auth.get('email') or not auth.get('password'): 
        return jsonify({'error':'Missing email or password', 'response': None}), 401 
   
    user = User.query.filter_by(email = auth.get('email')).first() 
   
    if not user: 
        return jsonify({'error':'User does not exist', 'response': None}), 401  
   
    if check_password_hash(user.password, auth.get('password')): 
        # generates the JWT Token 
        token = jwt.encode({'public_id':user.public_id, 'exp':datetime.utcnow()+timedelta(minutes = 30)}, app.config['SECRET_KEY']) 
   
        return make_response(jsonify({'token' : token.decode('UTF-8')}), 201) 
    return jsonify({'error':'Wrong password', 'response': None}), 403 


# log user out
@app.route('/logout', methods=['DELETE'])
@token_required
def logout(current_user):
    token = None
    # jwt is passed in the request header 
    if 'x-access-token' in request.headers: 
        token = request.headers['x-access-token']  
    if not token: 
        return jsonify({'error':'Login required', 'response':None}), 401
    blacklist.add(token)
    return jsonify({'response': 'Successfully logged out', 'error': None}), 200


# registration new user  
@app.route('/signup', methods =['POST']) 
def signup(): 
    data = request.form 
    username, email, password = data.get('username'), data.get('email'), data.get('password') 

    # checking for existing user 
    user = User.query.filter_by(email = data.get('email')).first() 
    if username and email and password:
        if not user: 
            # database ORM object 
            user = User( 
                public_id = str(uuid.uuid4()), 
                username = username, 
                email = email, 
                password = generate_password_hash(password) 
            ) 
            # insert user 
            db.session.add(user) 
            db.session.commit() 
    
            return jsonify({'response':'Successfully registered','error': None}), 201  
        else: 
            return jsonify({'error':'User already exists. Please Log in', 'response': None}), 202  
    else:
        return jsonify({'error':'Missing username or email or password', 'response': None}), 403 


# page not found
@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error':'not found page', 'description':str(error)}), 404)