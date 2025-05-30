import os
from flask_mail import Message
from datetime import datetime
from prijava import app, mail, db
from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from prijava.form import ApplicationForm, LoginForm, SearchForm, RequestResetForm, ResetPasswordForm
from prijava.models import User, Application
from sqlalchemy import or_, and_, desc, asc

def save_application_to_db(form_data):
    # Kreiraj novi unos za prijavu
    document_count = 0
    has_documents = False
    
    if form_data['documents']:
        for document in form_data['documents']:
            if document and document.filename.strip():
                document_count += 1
                has_documents = True
    
    application = Application(
        children_name=form_data['children_name'],
        children_surname=form_data['children_surname'],
        mother_name=form_data['mother_name'],
        mother_surname=form_data['mother_surname'],
        father_name=form_data['father_name'],
        father_surname=form_data['father_surname'],
        grade=form_data['grade'],
        class_number=form_data['class_number'],
        has_documents=has_documents,
        document_count=document_count,
        consent=form_data['consent'],
        date_submitted=datetime.utcnow()
    )
    
    # Sačuvaj u bazi
    db.session.add(application)
    db.session.commit()
    
    return application

def send_email(form_data):
    subject = f"Prijava dnevnog boravka za dete: {form_data['children_name']} {form_data['children_surname']}"
    recipients = [os.getenv('SCHOOL_EMAIL')]
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
    # msg.html = body
    msg.body = body
    
    if form_data['documents']:
        for document in form_data['documents']:
            if document:
                print(f'prilog: {document=}')
                msg.attach(
                    document.filename,
                    document.mimetype,
                    document.read()  # Pročitaj sadržaj dokumenta iz stream-a
                )
    
    # Slanje mejla
    mail.send(msg)
    
    print(f'{recipients=}')
    print(f'{body=}')

# Rute za autentikaciju
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Uspešno ste se prijavili.', 'success')
            return redirect(next_page if next_page else url_for('admin_dashboard'))
        else:
            flash('Prijavljivanje nije uspelo. Proverite email i lozinku.', 'danger')
    
    school_name = os.getenv('SCHOOL_NAME')
    school_phone = os.getenv('SCHOOL_PHONE')
    school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
    school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
    return render_template('login.html',
                            school_name=school_name, 
                            school_phone=school_phone, 
                            school_email=school_email,
                            school_web_address=school_web_address,
                            form=form)

def send_reset_email(user):
    token = user.generate_reset_token()
    db.session.commit()  # Sačuvaj token u bazi
    
    reset_url = url_for('reset_password', token=token, _external=True)
    subject = 'Zahtev za resetovanje lozinke'
    recipients = [user.email]
    
    body = f'''Da biste resetovali svoju lozinku, posetite sledeći link:

{reset_url}

Ako niste zahtevali resetovanje lozinke, ignorišite ovaj email i lozinka neće biti promenjena.'''
    
    msg = Message(subject, recipients=recipients)
    msg.body = body
    mail.send(msg)
    
@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
            flash('Poslat je email sa uputstvima za resetovanje lozinke.', 'info')
            return redirect(url_for('login'))
        else:
            flash('Nije pronađen nalog sa tim email-om.', 'danger')
    
    school_name = os.getenv('SCHOOL_NAME')
    school_phone = os.getenv('SCHOOL_PHONE')
    school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
    school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
    return render_template('reset_request.html',
                            school_name=school_name, 
                            school_phone=school_phone, 
                            school_email=school_email,
                            school_web_address=school_web_address,
                            form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    # Pronađi korisnika sa datim tokenom
    user = User.query.filter_by(reset_token=token).first()
    
    # Proveri da li token postoji i da nije istekao
    if not user or not user.is_reset_token_valid(token):
        flash('Neispravan ili istekao token za resetovanje lozinke.', 'danger')
        return redirect(url_for('reset_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Postavi novu lozinku
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user.password = hashed_password
        # Očisti token za reset
        user.clear_reset_token()
        # Sačuvaj izmene
        db.session.commit()
        
        flash('Vaša lozinka je uspešno promenjena. Sada se možete prijaviti.', 'success')
        return redirect(url_for('login'))
    
    school_name = os.getenv('SCHOOL_NAME')
    school_phone = os.getenv('SCHOOL_PHONE')
    school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
    school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
    return render_template('reset_password.html',
                            school_name=school_name, 
                            school_phone=school_phone, 
                            school_email=school_email,
                            school_web_address=school_web_address,
                            form=form)

@app.route('/logout')
def logout():
    logout_user()
    flash('Uspešno ste se odjavili.', 'success')
    return redirect(url_for('login'))

# Glavne rute aplikacije
@app.route('/', methods=['GET', 'POST'])
@app.route('/application_form', methods=['GET', 'POST'])
def application_form():
    form = ApplicationForm()
    if form.validate_on_submit():
        form_data = {
            'children_name': form.children_name.data,
            'children_surname': form.children_surname.data,
            'mother_name': form.mother_name.data,
            'mother_surname': form.mother_surname.data,
            'father_name': form.father_name.data,
            'father_surname': form.father_surname.data,
            'grade': form.grade.data,
            'class_number': form.class_number.data,
            'documents': form.documents.data, 
            'consent': form.consent.data
        }
        # Sačuvaj podatke u bazi
        application = save_application_to_db(form_data)
        # Pošalji email
        send_email(form_data)
        
        flash('Prijava je uspešno poslata.', 'success')
        return redirect(url_for('confirmation'))
    
    school_name = os.getenv('SCHOOL_NAME')
    school_phone = os.getenv('SCHOOL_PHONE')
    school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
    school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
    return render_template('application_form.html', 
                            school_name=school_name, 
                            school_phone=school_phone, 
                            school_email=school_email,
                            school_web_address=school_web_address,
                            form=form)

@app.route('/confirmation')
def confirmation():
    school_name = os.getenv('SCHOOL_NAME')
    school_phone = os.getenv('SCHOOL_PHONE')
    school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
    school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
    return render_template('confirmation.html',
                            school_name=school_name, 
                            school_phone=school_phone, 
                            school_email=school_email,
                            school_web_address=school_web_address)

# Admin rute
@app.route('/admin')
@login_required
def admin_dashboard():
    return redirect(url_for('applications_list'))

@app.route('/admin/applications', methods=['GET', 'POST'])
@login_required
def applications_list():
    form = SearchForm()
    sort = request.args.get('sort', 'date_desc')  # Podrazumevano sortiraj po datumu opadajuće
    
    # Inicijalizuj upit za filtriranje
    query = Application.query
    
    # Primeni filtere ako postoje
    if form.validate_on_submit() or request.args.get('search_term'):
        search_term = form.search_term.data if form.validate_on_submit() else request.args.get('search_term')
        date_from = form.date_from.data if form.validate_on_submit() else request.args.get('date_from')
        date_to = form.date_to.data if form.validate_on_submit() else request.args.get('date_to')
        grade_filter = form.grade_filter.data if form.validate_on_submit() else request.args.get('grade_filter')
        
        # Filtriranje po pojmu za pretragu
        if search_term:
            search_filter = or_(
                Application.children_name.ilike(f'%{search_term}%'),
                Application.children_surname.ilike(f'%{search_term}%'),
                Application.mother_name.ilike(f'%{search_term}%'),
                Application.mother_surname.ilike(f'%{search_term}%'),
                Application.father_name.ilike(f'%{search_term}%'),
                Application.father_surname.ilike(f'%{search_term}%')
            )
            query = query.filter(search_filter)
        
        # Filtriranje po datumu od
        if date_from:
            if isinstance(date_from, str):
                date_from = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Application.date_submitted >= date_from)
            
        # Filtriranje po datumu do
        if date_to:
            if isinstance(date_to, str):
                date_to = datetime.strptime(date_to, '%Y-%m-%d')
            # Postavi kraj dana za završni datum
            date_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59)
            query = query.filter(Application.date_submitted <= date_to)
            
        # Filtriranje po razredu
        if grade_filter:
            query = query.filter(Application.grade == grade_filter)
    
    # Sortiranje
    if sort == 'date_asc':
        query = query.order_by(asc(Application.date_submitted))
    elif sort == 'date_desc':
        query = query.order_by(desc(Application.date_submitted))
    elif sort == 'name_asc':
        query = query.order_by(asc(Application.children_surname), asc(Application.children_name))
    elif sort == 'name_desc':
        query = query.order_by(desc(Application.children_surname), desc(Application.children_name))
    elif sort == 'grade_asc':
        query = query.order_by(asc(Application.grade), asc(Application.class_number))
    elif sort == 'grade_desc':
        query = query.order_by(desc(Application.grade), desc(Application.class_number))
    
    # Paginacija
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Broj stavki po stranici
    applications = query.paginate(page=page, per_page=per_page)
    
    school_name = os.getenv('SCHOOL_NAME')
    return render_template('applications_list.html',
                           school_name=school_name,
                           applications=applications,
                           form=form,
                           current_sort=sort)

@app.route('/admin/application/<int:application_id>')
@login_required
def application_detail(application_id):
    application = Application.query.get_or_404(application_id)
    school_name = os.getenv('SCHOOL_NAME')
    return render_template('application_detail.html',
                           school_name=school_name,
                           application=application)

# API ruta za JSON podatke
@app.route('/api/applications')
@login_required
def api_applications():
    applications = Application.query.all()
    return jsonify([app.to_dict() for app in applications])
