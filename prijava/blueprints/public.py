import threading
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError

from prijava.form import ApplicationForm
from prijava.models import AppConfig, Application
from prijava.services.applications import persist_attachments, save_application
from prijava.tasks import send_email_task


def _enqueue_email_async(form_data_copy, application_id, logger):
    """Fire-and-forget Celery enqueue u pozadinskom thread-u.

    Request thread se ne blokira ako je Redis broker spor ili nedostupan —
    prijava je već zapisana u bazu i fajlovi na disk. Ako enqueue padne,
    samo se loguje greška.
    """
    def _run():
        try:
            task_result = send_email_task.delay(form_data_copy)
            logger.info(
                f"Email za prijavu {application_id} poslat asinhrono sa task ID: {task_result.id}"
            )
        except Exception as exc:
            logger.error(
                f"Celery broker nedostupan pri slanju emaila za prijavu {application_id}: {exc}"
            )
    threading.Thread(target=_run, daemon=True).start()


public_bp = Blueprint('public', __name__)


@public_bp.route('/', methods=['GET'])
@public_bp.route('/application_form', methods=['GET'])
def index():
    config = AppConfig.get()
    open_date = config.application_open_date
    is_open = config.is_application_open()
    return render_template(
        'index.html',
        open_date=open_date,
        is_open=is_open,
        open_date_iso=open_date.isoformat() if open_date else None,
    )


@public_bp.route('/application', methods=['GET', 'POST'])
def application():
    config = AppConfig.get()
    if not config.is_application_open():
        return redirect(url_for('public.index'))

    if request.method == 'GET':
        session['form_id'] = str(datetime.utcnow().timestamp())

    form = ApplicationForm()
    if 'form_id' in session:
        form.form_id.data = session['form_id']

    if form.validate_on_submit():
        if 'submitted_form_id' in session and session['submitted_form_id'] == request.form.get('form_id'):
            flash('Ova prijava je već poslata. Molimo sačekajte.', 'info')
            if 'application_id' in session:
                return redirect(url_for('public.submission_details', application_id=session['application_id']))
            return redirect(url_for('public.confirmation'))

        form_data = {
            'children_name': form.children_name.data.strip().capitalize(),
            'children_surname': form.children_surname.data.strip().capitalize(),
            'mother_name': form.mother_name.data.strip().capitalize(),
            'mother_surname': form.mother_surname.data.strip().capitalize(),
            'father_name': form.father_name.data.strip().capitalize(),
            'father_surname': form.father_surname.data.strip().capitalize(),
            'grade': form.grade.data,
            'class_number': form.class_number.data,
            'documents': form.documents.data,
            'consent': form.consent.data,
        }

        try:
            application_row, duplicate = save_application(form_data)

            session['application_id'] = application_row.id
            session['submitted_form_id'] = request.form.get('form_id')

            if duplicate:
                flash('Vaša prijava je duplikat. Molimo proverite podatke i pokušajte ponovo.', 'warning')
                return redirect(url_for('public.application'))

            try:
                saved_files, _ = persist_attachments(application_row, form_data.get('documents'))

                form_data_copy = {k: v for k, v in form_data.items() if k != 'documents'}
                form_data_copy['saved_files'] = saved_files

                _enqueue_email_async(
                    form_data_copy,
                    application_row.id,
                    current_app._get_current_object().logger,
                )
            except Exception as exc:
                current_app.logger.error(f"Greška pri obradi priloga: {exc}")
                flash('Vaša prijava je sačuvana, ali postoji problem sa obradom priloga.', 'warning')

            flash('Prijava je uspešno poslata.', 'success')
            return redirect(url_for('public.submission_details', application_id=application_row.id))
        except SQLAlchemyError as exc:
            current_app.logger.error(f"Greška pri čuvanju prijave u bazi: {exc}")
            flash('Došlo je do problema pri čuvanju vaše prijave. Molimo pokušajte ponovo kasnije.', 'danger')

    return render_template('application_form.html', form=form)


@public_bp.route('/confirmation')
def confirmation():
    return render_template('confirmation.html')


@public_bp.route('/submission_details/<int:application_id>')
def submission_details(application_id):
    session_app_id = session.get('application_id')
    if not session_app_id or int(session_app_id) != application_id:
        flash('Nemate pristup ovim podacima.', 'danger')
        return redirect(url_for('public.application'))

    try:
        application_row = Application.query.get_or_404(application_id)
    except SQLAlchemyError as exc:
        current_app.logger.error(f"Greška pri pristupu podacima o prijavi {application_id}: {exc}")
        flash('Došlo je do problema pri pristupanju podacima o vašoj prijavi.', 'danger')
        return redirect(url_for('public.application'))

    is_duplicate = session.get('duplicate_application', False)
    return render_template(
        'submission_details.html',
        application=application_row,
        is_duplicate=is_duplicate,
    )
