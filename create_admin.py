from prijava import db, app
from prijava.models import User
from werkzeug.security import generate_password_hash
import sys

def create_admin_user(email, password):
    with app.app_context():
        # Kreiraj tabele ako ne postoje
        db.create_all()
        
        # Proveri da li korisnik već postoji
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"Korisnik '{email}' već postoji.")
            return
        
        # Kreiraj novog admin korisnika
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, is_active=True)
        
        # Sačuvaj u bazi
        db.session.add(new_user)
        db.session.commit()
        print(f"Administrator '{email}' je uspešno kreiran.")

if __name__ == '__main__':
    # Podrazumevane vrednosti
    default_email = 'admin'
    default_password = 'admin123'
    
    # Ako su argumenti prosleđeni kroz komandnu liniju, koristi njih
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        email = default_email
        password = default_password
    
    # Kreiraj admin korisnika
    create_admin_user(email, password)
