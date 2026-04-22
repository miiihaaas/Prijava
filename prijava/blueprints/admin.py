from datetime import datetime, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required
from sqlalchemy import asc, desc
from sqlalchemy.exc import SQLAlchemyError
import io

from prijava.form import SearchForm
from prijava.models import Application
from prijava.services.filters import apply_application_filters, parse_datetime_local
from prijava.services.pdf import render_applications_pdf


admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@login_required
def dashboard():
    return redirect(url_for('admin.applications_list'))


@admin_bp.route('/admin/applications', methods=['GET', 'POST'])
@login_required
def applications_list():
    try:
        form = SearchForm()

        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        grade_filter = request.args.get('grade_filter', '')

        if request.method == 'GET' and (date_from or date_to or grade_filter):
            form.date_from.data = parse_datetime_local(date_from) if date_from else form.date_from.data
            form.date_to.data = parse_datetime_local(date_to) if date_to else form.date_to.data
            form.grade_filter.data = grade_filter

        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = datetime(now.year, now.month, 1)
        stats = {
            'total': Application.query.count(),
            'month': Application.query.filter(Application.date_submitted >= month_start).count(),
            'week': Application.query.filter(Application.date_submitted >= week_start).count(),
            'today': Application.query.filter(Application.date_submitted >= today_start).count(),
        }

        return render_template('applications_list.html', applications=[], form=form, stats=stats)
    except SQLAlchemyError as exc:
        current_app.logger.error(f"SQLAlchemy greška pri pristupu listi prijava: {exc}")
        flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/application/<int:application_id>')
@login_required
def application_detail(application_id):
    try:
        application_row = Application.query.get_or_404(application_id)
    except SQLAlchemyError as exc:
        current_app.logger.error(f"Greška pri pristupu podacima o prijavi {application_id}: {exc}")
        flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('admin.applications_list'))

    return render_template('application_detail.html', application=application_row)


@admin_bp.route('/admin/export_applications')
@login_required
def export_applications():
    try:
        search_term = request.args.get('search_term')
        date_from_raw = request.args.get('date_from')
        date_to_raw = request.args.get('date_to')
        grade_filter = request.args.get('grade_filter')
        sort = request.args.get('sort', 'date_desc')

        query = apply_application_filters(
            Application.query,
            search=search_term,
            date_from=date_from_raw,
            date_to=date_to_raw,
            grade=grade_filter or None,
        )

        sort_map = {
            'date_asc': [asc(Application.date_submitted)],
            'date_desc': [desc(Application.date_submitted)],
            'name_asc': [asc(Application.children_surname), asc(Application.children_name)],
            'name_desc': [desc(Application.children_surname), desc(Application.children_name)],
            'grade_asc': [asc(Application.grade), asc(Application.class_number)],
            'grade_desc': [desc(Application.grade), desc(Application.class_number)],
        }
        if sort in sort_map:
            query = query.order_by(*sort_map[sort])

        applications = query.all()

        pdf_bytes = render_applications_pdf(
            applications,
            filters={
                'search': search_term,
                'date_from': parse_datetime_local(date_from_raw) if date_from_raw else None,
                'date_to': parse_datetime_local(date_to_raw) if date_to_raw else None,
                'grade': grade_filter,
            },
            title='Pregled prijava dnevnog boravka',
            show_school_name=False,
            title_size=15,
            body_size=10,
            row_height=10,
            filter_date_format='%d.%m.%Y.',
            show_total=True,
        )

        filename = f"prijave_dnevni_boravak_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf',
        )
    except SQLAlchemyError as exc:
        current_app.logger.error(f"SQLAlchemy greška pri eksportovanju prijava: {exc}")
        flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('admin.applications_list'))


@admin_bp.route('/admin/applications_to_pdf')
@login_required
def applications_to_pdf():
    try:
        date_from_raw = request.args.get('date_from', '')
        date_to_raw = request.args.get('date_to', '')
        grade_filter = request.args.get('grade_filter', '')
        search = request.args.get('search', '')

        query = apply_application_filters(
            Application.query,
            search=search,
            date_from=date_from_raw,
            date_to=date_to_raw,
            grade=grade_filter or None,
        )

        applications = query.order_by(asc(Application.date_submitted)).all()

        pdf_bytes = render_applications_pdf(
            applications,
            filters={
                'search': search,
                'date_from': parse_datetime_local(date_from_raw) if date_from_raw else None,
                'date_to': parse_datetime_local(date_to_raw) if date_to_raw else None,
                'grade': grade_filter,
            },
            title='Spisak prijava za upis',
            show_school_name=True,
            title_size=12,
            body_size=8,
            row_height=8,
            filter_date_format='%d.%m.%Y. %H:%M',
            header_fill_rgb=(200, 200, 200),
            show_total=False,
        )

        response = make_response(pdf_bytes)
        response.headers.set(
            'Content-Disposition',
            'inline',
            filename=f'prijave-{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf',
        )
        response.headers.set('Content-Type', 'application/pdf')
        return response
    except SQLAlchemyError as exc:
        current_app.logger.error(f"SQLAlchemy greška pri generisanju PDF-a sa prijavama: {exc}")
        flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('admin.applications_list'))
