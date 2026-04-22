import json
import os
import pathlib
from datetime import datetime

from flask import current_app, session
from sqlalchemy.exc import SQLAlchemyError

from prijava import db
from prijava.models import Application


def ensure_attachments_dir():
    """Proverava i kreira direktorijum za priloge ako ne postoji"""
    attachments_dir = os.path.join(current_app.root_path, 'static', 'attachments')
    pathlib.Path(attachments_dir).mkdir(parents=True, exist_ok=True)
    return attachments_dir


def save_application(form_data):
    """Persist a new :class:`Application`, detecting duplicates.

    Returns ``(application, is_duplicate)``.
    """
    try:
        existing = Application.query.filter(
            Application.children_name == form_data['children_name'].capitalize(),
            Application.children_surname == form_data['children_surname'].capitalize(),
            Application.mother_name == form_data['mother_name'].capitalize(),
            Application.mother_surname == form_data['mother_surname'].capitalize(),
            Application.father_name == form_data['father_name'].capitalize(),
            Application.father_surname == form_data['father_surname'].capitalize(),
            Application.grade == form_data['grade'],
            Application.class_number == form_data['class_number'],
        ).first()

        if existing:
            session['duplicate_application'] = True
            return existing, True

        document_count = 0
        has_documents = False
        if form_data.get('documents'):
            for document in form_data['documents']:
                if document and document.filename.strip():
                    document_count += 1
                    has_documents = True

        import pytz
        serbia_tz = pytz.timezone('Europe/Belgrade')

        application = Application(
            children_name=form_data['children_name'].capitalize(),
            children_surname=form_data['children_surname'].capitalize(),
            mother_name=form_data['mother_name'].capitalize(),
            mother_surname=form_data['mother_surname'].capitalize(),
            father_name=form_data['father_name'].capitalize(),
            father_surname=form_data['father_surname'].capitalize(),
            grade=form_data['grade'],
            class_number=form_data['class_number'],
            has_documents=has_documents,
            document_count=document_count,
            attachment_paths='{}',
            consent=form_data['consent'],
            date_submitted=datetime.now(serbia_tz),
        )

        db.session.add(application)
        db.session.commit()

        session['duplicate_application'] = False
        return application, False

    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f'Greška pri čuvanju aplikacije u bazi: {exc}')
        raise


def persist_attachments(application, documents):
    """Save uploaded documents to disk and record them on ``application``.

    Returns ``(saved_files, attachment_data)`` where ``saved_files`` contains
    absolute paths (used later by the async email task) and ``attachment_data``
    contains relative paths that are JSON-persisted on the application row.
    """
    saved_files = []
    attachment_data = []

    if not documents or not any(documents):
        return saved_files, attachment_data

    attachments_dir = ensure_attachments_dir()
    logger = current_app.logger

    for index, document in enumerate(documents):
        if not document:
            continue

        file_name = f"{application.id}-{index}{os.path.splitext(document.filename)[1]}"
        file_path = os.path.join(attachments_dir, file_name)
        rel_path = os.path.join('static', 'attachments', file_name)

        document.save(file_path)
        logger.info(f"Fajl sačuvan na putanji: {file_path}")

        saved_files.append({
            'path': file_path,
            'filename': document.filename,
            'mimetype': document.mimetype,
        })
        attachment_data.append({
            'path': rel_path,
            'filename': document.filename,
            'mimetype': document.mimetype,
        })
        logger.info(f"Podaci o fajlu dodati za bazu: {file_path}")
        logger.info(f"Apsolutna putanja: {file_path}")
        logger.info(f"Provera postojanja fajla: {os.path.exists(file_path)}")
        logger.info(
            f"Veličina fajla: "
            f"{os.path.getsize(file_path) if os.path.exists(file_path) else 'Fajl ne postoji'}"
        )

    application.attachment_paths = json.dumps(attachment_data)
    db.session.commit()

    return saved_files, attachment_data
