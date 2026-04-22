import os

from flask import current_app, url_for
from flask_mail import Message
from sqlalchemy.exc import SQLAlchemyError

from prijava import db, mail


def build_application_message(form_data):
    """Build the :class:`flask_mail.Message` announcing a new application.

    The recipient is read from the ``SCHOOL_EMAIL`` environment variable.
    """
    recipients = [os.getenv('SCHOOL_EMAIL')]
    if not recipients[0]:
        current_app.logger.error("SCHOOL_EMAIL environment variable nije postavljena.")
        raise ValueError("Email adresa škole nije konfigurisana.")

    subject = (
        f"Prijava dnevnog boravka za dete: "
        f"{form_data['children_name']} {form_data['children_surname']}"
    )
    body = (
        f"Ime deteta: {form_data['children_name']}\n"
        f"Prezime deteta: {form_data['children_surname']}\n"
        f"Razred: {form_data['grade']}\n"
        f"Odeljenje: {form_data['class_number']}\n"
        f"Ime majke: {form_data['mother_name']}\n"
        f"Prezime majke: {form_data['mother_surname']}\n"
        f"Ime oca: {form_data['father_name']}\n"
        f"Prezime oca: {form_data['father_surname']}\n"
    )

    msg = Message(subject, recipients=recipients)
    msg.body = body
    return msg


def send_reset_email(user):
    try:
        token = user.generate_reset_token()
        db.session.commit()

        reset_url = url_for('auth.reset_password', token=token, _external=True)
        subject = 'Zahtev za resetovanje lozinke'
        body = (
            'Da biste resetovali svoju lozinku, posetite sledeći link:\n\n'
            f'{reset_url}\n\n'
            'Ako niste zahtevali resetovanje lozinke, ignorišite ovaj email i '
            'lozinka neće biti promenjena.'
        )

        msg = Message(subject, recipients=[user.email])
        msg.body = body
        mail.send(msg)

        current_app.logger.info(f'Email za resetovanje lozinke poslat na adresu: {user.email}')
        return True
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f'Greška pri čuvanju reset tokena u bazi: {exc}')
        raise
    except Exception as exc:
        current_app.logger.error(f'Greška pri slanju email-a za resetovanje lozinke: {exc}')
        raise
