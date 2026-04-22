import os

from flask import current_app

from prijava import mail
from prijava.celery_app import celery
from prijava.services.email import build_application_message


@celery.task
def send_email_task(form_data):
    """Asinhroni zadatak za slanje email-a sa prilozima sačuvanim na disku.

    ContextTask (postavljen u ``init_celery``) već pokreće svaki task u
    ``app.app_context()``, pa nije potrebno ručno kreirati Flask app ovde.
    """
    try:
        msg = build_application_message(form_data)

        if form_data.get('saved_files'):
            for file_info in form_data['saved_files']:
                try:
                    if os.path.exists(file_info['path']):
                        with open(file_info['path'], 'rb') as fh:
                            msg.attach(
                                filename=file_info['filename'],
                                content_type=file_info['mimetype'],
                                data=fh.read(),
                            )
                        current_app.logger.info(
                            f"Prilog {file_info['filename']} uspešno pridružen mejlu."
                        )
                    else:
                        current_app.logger.warning(
                            f"Fajl {file_info['path']} nije pronađen."
                        )
                except Exception as exc:
                    current_app.logger.error(
                        f"Greška pri pridruživanju priloga {file_info['filename']}: {exc}"
                    )
                    continue

        mail.send(msg)

        current_app.logger.info(f'Email uspešno poslat na adrese: {msg.recipients}')
        return True

    except Exception as exc:
        current_app.logger.error(f"Greška pri slanju email-a: {exc}")
        raise
