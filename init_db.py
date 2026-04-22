from prijava import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    print("Baza podataka je uspešno inicijalizovana.")
