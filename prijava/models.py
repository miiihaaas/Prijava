from datetime import datetime, timedelta
import secrets
from flask_login import UserMixin
from prijava import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f"User('{self.email}')"
    
    def generate_reset_token(self):
        # Generiši nasumični token za reset lozinke
        self.reset_token = secrets.token_urlsafe(32)
        # Postavi istek tokena na 24 sata od sada
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
        return self.reset_token
    
    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expiry = None
    
    def is_reset_token_valid(self, token):
        # Proveri da li je token validan i nije istekao
        return (self.reset_token == token and
                self.reset_token_expiry is not None and
                self.reset_token_expiry > datetime.utcnow())

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    children_name = db.Column(db.String(100), nullable=False)
    children_surname = db.Column(db.String(100), nullable=False)
    mother_name = db.Column(db.String(100), nullable=False)
    mother_surname = db.Column(db.String(100), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    father_surname = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    class_number = db.Column(db.String(10), nullable=False)
    has_documents = db.Column(db.Boolean, default=False)
    document_count = db.Column(db.Integer, default=0)
    consent = db.Column(db.Boolean, nullable=False, default=False)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"Application('{self.children_name} {self.children_surname}', '{self.date_submitted}')"
    
    def to_dict(self):
        return {
            'id': self.id,
            'children_name': self.children_name,
            'children_surname': self.children_surname,
            'mother_name': self.mother_name,
            'mother_surname': self.mother_surname,
            'father_name': self.father_name,
            'father_surname': self.father_surname,
            'grade': self.grade,
            'class_number': self.class_number,
            'has_documents': self.has_documents,
            'document_count': self.document_count,
            'consent': self.consent,
            'date_submitted': self.date_submitted.strftime('%Y-%m-%d %H:%M:%S')
        }
