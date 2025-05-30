from prijava import db, app

# Kreiraj sve tabele definisane u modelima
with app.app_context():
    db.create_all()
    print("Baza podataka je uspešno inicijalizovana.")
