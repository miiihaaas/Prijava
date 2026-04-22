import os

from flask import current_app

from prijava.celery_app import celery


@celery.task
def send_email_task(form_data):
    """Asinhroni zadatak za slanje email-a sa prilozima koji su sačuvani na disku."""
    from prijava import create_app, mail
    from prijava.services.email import build_application_message

    app = create_app()
    with app.app_context():
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

            if form_data.get('saved_files'):
                for file_info in form_data['saved_files']:
                    try:
                        if os.path.exists(file_info['path']):
                            current_app.logger.info(
                                f"Fajl {file_info['path']} zadržan za kasniju upotrebu."
                            )
                    except Exception as exc:
                        current_app.logger.error(
                            f"Greška pri proveri fajla {file_info['path']}: {exc}"
                        )

            current_app.logger.info(f'Email uspešno poslat na adrese: {msg.recipients}')
            return True

        except Exception as exc:
            current_app.logger.error(f"Greška pri slanju email-a: {exc}")
            raise
