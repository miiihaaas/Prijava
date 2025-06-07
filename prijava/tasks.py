import os
import pathlib
from flask_mail import Message
from flask import current_app
from prijava.celery_app import make_celery

# Kreiramo Celery instancu
celery = make_celery()

@celery.task
def send_email_task(form_data):
    """
    Asinhroni zadatak za slanje email-a sa prilozima koji su sačuvani na disku
    """
    # Importujemo ovde kako bismo izbegli cirkularni import
    from prijava import mail
    
    try:
        subject = f"Prijava dnevnog boravka za dete: {form_data['children_name']} {form_data['children_surname']}"
        recipients = [os.getenv('SCHOOL_EMAIL')]
        
        if not recipients[0]:
            current_app.logger.error("SCHOOL_EMAIL environment variable nije postavljena.")
            raise ValueError("Email adresa škole nije konfigurisana.")
            
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
        
        # Pridruži sačuvane fajlove mejlu ako postoje
        if 'saved_files' in form_data and form_data['saved_files']:
            for file_info in form_data['saved_files']:
                try:
                    # Proveri da li fajl postoji
                    if os.path.exists(file_info['path']):
                        with open(file_info['path'], 'rb') as f:
                            file_data = f.read()
                            msg.attach(
                                filename=file_info['filename'],
                                content_type=file_info['mimetype'],
                                data=file_data
                            )
                        current_app.logger.info(f"Prilog {file_info['filename']} uspešno pridružen mejlu.")
                    else:
                        current_app.logger.warning(f"Fajl {file_info['path']} nije pronađen.")
                except Exception as e:
                    current_app.logger.error(f"Greška pri pridruživanju priloga {file_info['filename']}: {str(e)}")
                    continue
        
        # Slanje mejla sa prilozima
        mail.send(msg)
        
        # Brisanje privremenih fajlova nakon slanja
        if 'saved_files' in form_data and form_data['saved_files']:
            for file_info in form_data['saved_files']:
                try:
                    if os.path.exists(file_info['path']):
                        os.remove(file_info['path'])
                        current_app.logger.info(f"Privremeni fajl {file_info['path']} uspešno obrisan.")
                except Exception as e:
                    current_app.logger.error(f"Greška pri brisanju privremenog fajla {file_info['path']}: {str(e)}")
        
        current_app.logger.info(f'Email uspešno poslat na adrese: {recipients}')
        return True
        
    except Exception as e:
        current_app.logger.error(f"Greška pri slanju email-a: {str(e)}")
        raise
