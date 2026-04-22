from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import login_required
from sqlalchemy import asc, desc

from prijava.models import Application
from prijava.services.filters import apply_application_filters


api_bp = Blueprint('api', __name__)


@api_bp.route('/api/applications', methods=['GET', 'POST'])
@login_required
def applications():
    try:
        base_query = Application.query
        total_records = base_query.count()

        draw = request.form.get('draw', type=int)
        start = request.form.get('start', type=int, default=0)
        length = request.form.get('length', type=int, default=20)
        search_value = request.form.get('search[value]', '')

        date_from = request.form.get('date_from', '')
        date_to = request.form.get('date_to', '')
        grade_filter = request.form.get('grade_filter', '')

        query = apply_application_filters(
            base_query,
            search=search_value,
            date_from=date_from,
            date_to=date_to,
            grade=grade_filter or None,
        )

        filtered_records_count = query.count()

        column_index = request.form.get('order[0][column]', type=int, default=5)
        column_name = request.form.get(f'columns[{column_index}][data]', 'date_submitted')
        direction = request.form.get('order[0][dir]', 'desc')

        column_mapping = {
            'id': Application.id,
            'children_full_name': Application.children_surname,
            'grade_class': Application.grade,
            'date_submitted': Application.date_submitted,
        }

        if column_name in column_mapping:
            column = column_mapping[column_name]
            query = query.order_by(asc(column) if direction == 'asc' else desc(column))
        else:
            query = query.order_by(desc(Application.date_submitted))

        rows = query.offset(start).limit(length).all()

        data = []
        for app_row in rows:
            data.append({
                'id': app_row.id,
                'children_full_name': f"{app_row.children_name} {app_row.children_surname}",
                'grade_class': f"{app_row.grade} / {app_row.class_number}",
                'parents_info': (
                    f'<span class="parents-line"><span class="parents-label">M</span> {app_row.mother_name} {app_row.mother_surname}</span><br>'
                    f'<span class="parents-line"><span class="parents-label">O</span> {app_row.father_name} {app_row.father_surname}</span>'
                ),
                'documents_info': (
                    f'<span class="chip chip--ok"><i class="fas fa-check"></i> {app_row.document_count}</span>'
                    if app_row.has_documents
                    else '<span class="chip chip--muted">Nema</span>'
                ),
                'date_submitted': app_row.date_submitted.strftime('%d.%m.%Y. %H:%M'),
                'actions': (
                    f'<a href="{url_for("admin.application_detail", application_id=app_row.id)}" '
                    f'class="btn btn-outline-primary btn-sm">Detalji</a>'
                ),
            })

        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records_count,
            'data': data,
        })
    except Exception as exc:
        current_app.logger.error(f"Greška pri obradi DataTables zahteva: {exc}")
        return jsonify({
            'error': f'Došlo je do problema pri obradi zahteva: {exc}',
            'status': 'error',
        }), 500
