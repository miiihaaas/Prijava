import sys

from werkzeug.security import generate_password_hash

from prijava import create_app, db
from prijava.models import User


def create_admin_user(email, password):
    app = create_app()
    with app.app_context():
        db.create_all()

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"Korisnik '{email}' već postoji.")
            return

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, is_active=True)

        db.session.add(new_user)
        db.session.commit()
        print(f"Administrator '{email}' je uspešno kreiran.")


if __name__ == '__main__':
    default_email = 'admin'
    default_password = 'admin123'

    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        email = default_email
        password = default_password

    create_admin_user(email, password)
