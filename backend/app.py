from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST', 'localhost')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=8)

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    observations = db.relationship('Observation', backref='observer', lazy=True)

class Observation(db.Model):
    __tablename__ = 'observations'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')
    image_url = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Test endpoint
@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({"message": "API is working!"}), 200

# ============= AUTH ENDPOINTS =============
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        required_fields = ['username', 'password', 'full_name']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Field {field} is required"}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({"error": "Username already exists"}), 400
        
        new_user = User(
            username=data['username'],
            password=data['password'],
            full_name=data['full_name'],
            role=data.get('role', 'user')
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            "message": "User created successfully",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "full_name": new_user.full_name,
                "role": new_user.role
            }
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({"error": "Username and password required"}), 400
        
        user = User.query.filter_by(username=data['username']).first()
        
        if not user or user.password != data['password']:
            return jsonify({"error": "Invalid username or password"}), 401
        
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={
                "username": user.username,
                "role": user.role,
                "full_name": user.full_name
            }
        )
        
        return jsonify({
            "access_token": access_token,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============= OBSERVATION ENDPOINTS =============
@app.route('/api/observations', methods=['GET'])
@jwt_required()
def get_observations():
    try:
        status = request.args.get('status')
        category = request.args.get('category')
        severity = request.args.get('severity')
        
        query = Observation.query
        
        if status:
            query = query.filter_by(status=status)
        if category:
            query = query.filter_by(category=category)
        if severity:
            query = query.filter_by(severity=severity)
        
        observations = query.order_by(Observation.created_at.desc()).all()
        
        result = []
        for obs in observations:
            observer = User.query.get(obs.created_by)
            result.append({
                "id": obs.id,
                "title": obs.title,
                "description": obs.description,
                "category": obs.category,
                "location": obs.location,
                "severity": obs.severity,
                "status": obs.status,
                "image_url": obs.image_url,
                "created_by": {
                    "id": observer.id,
                    "full_name": observer.full_name
                },
                "created_at": obs.created_at.isoformat() if obs.created_at else None,
                "updated_at": obs.updated_at.isoformat() if obs.updated_at else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/observations', methods=['POST'])
@jwt_required()
def create_observation():
    try:
        data = request.get_json()
        current_user_id = int(get_jwt_identity())
        
        required_fields = ['title', 'description', 'category', 'location', 'severity']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Field {field} is required"}), 400
        
        new_observation = Observation(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            location=data['location'],
            severity=data['severity'],
            status=data.get('status', 'open'),
            image_url=data.get('image_url'),
            created_by=current_user_id
        )
        
        db.session.add(new_observation)
        db.session.commit()
        
        return jsonify({
            "message": "Observation created successfully",
            "observation": {
                "id": new_observation.id,
                "title": new_observation.title,
                "category": new_observation.category
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/stats', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    try:
        total_observations = Observation.query.count()
        
        open_count = Observation.query.filter_by(status='open').count()
        in_progress_count = Observation.query.filter_by(status='in_progress').count()
        closed_count = Observation.query.filter_by(status='closed').count()
        
        unsafe_act_count = Observation.query.filter_by(category='unsafe_act').count()
        unsafe_condition_count = Observation.query.filter_by(category='unsafe_condition').count()
        positive_count = Observation.query.filter_by(category='positive').count()
        
        low_count = Observation.query.filter_by(severity='low').count()
        medium_count = Observation.query.filter_by(severity='medium').count()
        high_count = Observation.query.filter_by(severity='high').count()
        
        recent = Observation.query.order_by(Observation.created_at.desc()).limit(5).all()
        recent_list = []
        for obs in recent:
            observer = User.query.get(obs.created_by)
            recent_list.append({
                "id": obs.id,
                "title": obs.title,
                "category": obs.category,
                "status": obs.status,
                "created_by": observer.full_name if observer else "Unknown",
                "created_at": obs.created_at.isoformat() if obs.created_at else None
            })
        
        return jsonify({
            "total_observations": total_observations,
            "by_status": {
                "open": open_count,
                "in_progress": in_progress_count,
                "closed": closed_count
            },
            "by_category": {
                "unsafe_act": unsafe_act_count,
                "unsafe_condition": unsafe_condition_count,
                "positive": positive_count
            },
            "by_severity": {
                "low": low_count,
                "medium": medium_count,
                "high": high_count
            },
            "recent_observations": recent_list
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)