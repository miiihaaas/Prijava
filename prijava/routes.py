import os
import pathlib
import json
import io
from flask_mail import Message
from datetime import datetime
from prijava import app, mail, db
from flask import render_template, request, redirect, url_for, flash, jsonify, abort, session, send_file
from sqlalchemy.exc import SQLAlchemyError
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from prijava.form import ApplicationForm, LoginForm, SearchForm, RequestResetForm, ResetPasswordForm
from prijava.models import User, Application
from sqlalchemy import or_, and_, desc, asc
from prijava.tasks import send_email_task
from fpdf import FPDF

# Dodajemo filter za pretvaranje JSON stringa u Python objekat
@app.template_filter('from_json')
def from_json(value):
    try:
        if value:
            return json.loads(value)
        return []
    except Exception as e:
        app.logger.error(f"Greška pri pretvaranju JSON-a: {str(e)}")
        return []

# Funkcija za kreiranje direktorijuma za priloge ako ne postoji
def ensure_attachments_dir_exists():
    """Proverava i kreira direktorijum za priloge ako ne postoji"""
    attachments_dir = os.path.join(app.root_path, 'static', 'attachments')
    pathlib.Path(attachments_dir).mkdir(parents=True, exist_ok=True)
    return attachments_dir

def save_application_to_db(form_data):
    try:
        # Provera da li već postoji ista prijava u sistemu
        existing_application = Application.query.filter(
            Application.children_name == form_data['children_name'].capitalize(),
            Application.children_surname == form_data['children_surname'].capitalize(),
            Application.mother_name == form_data['mother_name'].capitalize(),
            Application.mother_surname == form_data['mother_surname'].capitalize(),
            Application.father_name == form_data['father_name'].capitalize(),
            Application.father_surname == form_data['father_surname'].capitalize(),
            Application.grade == form_data['grade'],
            Application.class_number == form_data['class_number']
        ).first()
        
        # Ako postoji, dodaj informaciju o duplikatu i vrati postojeću prijavu
        if existing_application:
            # Označavamo u sesiji da je prijava duplikat
            session['duplicate_application'] = True
            return existing_application, True
        
        # Nastavljamo sa kreiranjem nove prijave ako nema duplikata
        document_count = 0
        has_documents = False
        
        if form_data['documents']:
            for document in form_data['documents']:
                if document and document.filename.strip():
                    document_count += 1
                    has_documents = True
        
        import pytz
        # Definiši vremensku zonu za Srbiju
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
            attachment_paths='{}',  # Inicijalno prazan JSON
            consent=form_data['consent'],
            date_submitted=datetime.now(serbia_tz)
        )
        
        # Sačuvaj u bazi
        db.session.add(application)
        db.session.commit()
        
        # Označavamo u sesiji da nije duplikat
        session['duplicate_application'] = False
        
        return application, False
    
    except SQLAlchemyError as e:
        # Ponisti transakciju u slučaju greške
        db.session.rollback()
        app.logger.error(f'Greška pri čuvanju aplikacije u bazi: {str(e)}')
        raise

def send_email(form_data):
    try:
        subject = f"Prijava dnevnog boravka za dete: {form_data['children_name']} {form_data['children_surname']}"
        recipients = [os.getenv('SCHOOL_EMAIL')]
        
        if not recipients[0]:
            app.logger.error("SCHOOL_EMAIL environment variable nije postavljena.")
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
        # msg.html = body
        msg.body = body
        
        if form_data['documents']:
            for document in form_data['documents']:
                if document:
                    try:
                        msg.attach(
                            document.filename,
                            document.mimetype,
                            document.read()  # Pročitaj sadržaj dokumenta iz stream-a
                        )
                    except Exception as e:
                        app.logger.error(f"Greška pri dodavanju priloga {document.filename}: {str(e)}")
                        # Nastavljamo sa sledećim dokumentom ako ovaj ne može da se priloži
                        continue
        
        # Slanje mejla
        mail.send(msg)
        
        app.logger.info(f'Email uspešno poslat na adrese: {recipients}')
        return True
        
    except Exception as e:
        app.logger.error(f"Greška pri slanju email-a: {str(e)}")
        raise

# Rute za autentikaciju
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                flash('Uspešno ste se prijavili.', 'success')
                return redirect(next_page if next_page else url_for('admin_dashboard'))
            else:
                flash('Prijavljivanje nije uspelo. Proverite email i lozinku.', 'danger')
        except SQLAlchemyError as e:
            app.logger.error(f"Greška pri pristupu bazi podataka tokom prijave: {str(e)}")
            flash('Došlo je do problema sa pristupom sistemu. Molimo pokušajte kasnije.', 'danger')
    
    try:
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
    except Exception as e:
        app.logger.error(f"Greška pri renderovanju login stranice: {str(e)}")
        abort(500)

def send_reset_email(user):
    try:
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
        
        app.logger.info(f'Email za resetovanje lozinke poslat na adresu: {user.email}')
        return True
    except SQLAlchemyError as e:
        db.session.rollback()  # Poništi transakciju u slučaju greške sa bazom
        app.logger.error(f'Greška pri čuvanju reset tokena u bazi: {str(e)}')
        raise
    except Exception as e:
        app.logger.error(f'Greška pri slanju email-a za resetovanje lozinke: {str(e)}')
        raise
    
@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                try:
                    send_reset_email(user)
                    flash('Poslat je email sa uputstvima za resetovanje lozinke.', 'info')
                    return redirect(url_for('login'))
                except Exception as e:
                    app.logger.error(f"Greška pri slanju email-a za reset lozinke: {str(e)}")
                    flash('Došlo je do problema pri slanju email-a. Molimo pokušajte ponovo kasnije.', 'danger')
            else:
                flash('Nije pronađen nalog sa tim email-om.', 'danger')
        except SQLAlchemyError as e:
            app.logger.error(f"Greška pri pristupu bazi podataka: {str(e)}")
            flash('Došlo je do problema sa bazom podataka. Molimo pokušajte kasnije.', 'danger')
    
    try:
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
    except Exception as e:
        app.logger.error(f"Greška pri renderovanju stranice za reset lozinke: {str(e)}")
        abort(500)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    try:
        # Pronađi korisnika sa datim tokenom
        user = User.query.filter_by(reset_token=token).first()
        
        # Proveri da li token postoji i da nije istekao
        if not user or not user.is_reset_token_valid(token):
            flash('Neispravan ili istekao token za resetovanje lozinke.', 'danger')
            return redirect(url_for('reset_request'))
        
        form = ResetPasswordForm()
        if form.validate_on_submit():
            try:
                # Postavi novu lozinku
                hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
                user.password = hashed_password
                # Očisti token za reset
                user.clear_reset_token()
                # Sačuvaj izmene
                db.session.commit()
                
                flash('Vaša lozinka je uspešno promenjena. Sada se možete prijaviti.', 'success')
                return redirect(url_for('login'))
            except SQLAlchemyError as e:
                db.session.rollback()
                app.logger.error(f"Greška pri ažuriranju lozinke u bazi: {str(e)}")
                flash('Došlo je do greške pri ažuriranju lozinke. Molimo pokušajte ponovo kasnije.', 'danger')
        
        try:
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
        except Exception as e:
            app.logger.error(f"Greška pri renderovanju stranice za resetovanje lozinke: {str(e)}")
            abort(500)
    except SQLAlchemyError as e:
        app.logger.error(f"Greška pri pristupu bazi podataka pri resetovanju lozinke: {str(e)}")
        flash('Došlo je do problema sa pristupom bazi. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('reset_request'))

@app.route('/logout')
def logout():
    logout_user()
    flash('Uspešno ste se odjavili.', 'success')
    return redirect(url_for('login'))

# Glavne rute aplikacije
@app.route('/', methods=['GET', 'POST'])
@app.route('/application_form', methods=['GET', 'POST'])
def index():
    return "Forma za aplikaciju je privremeno nedostupna."

@app.route('/application', methods=['GET', 'POST'])
def application():
    try:
        # Generišemo jedinstveni formular ID pri svakom GET zahtevu
        if request.method == 'GET':
            session['form_id'] = str(datetime.utcnow().timestamp())
        
        form = ApplicationForm()
        
        # Postavimo vrednost skrivenog polja form_id iz sesije
        if 'form_id' in session:
            form.form_id.data = session['form_id']
        if form.validate_on_submit():
            # Provera da li je formular već poslat (zaštita od dupliranja)
            if 'submitted_form_id' in session and session['submitted_form_id'] == request.form.get('form_id'):
                flash('Ova prijava je već poslata. Molimo sačekajte.', 'info')
                if 'application_id' in session:
                    return redirect(url_for('submission_details', application_id=session['application_id']))
                else:
                    return redirect(url_for('confirmation'))
            
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
                'consent': form.consent.data
            }
            
            try:
                # Sačuvaj podatke u bazi
                application, duplicate = save_application_to_db(form_data)
                
                # Sačuvaj ID aplikacije u sesiju za prikaz detalja
                session['application_id'] = application.id
                # Označi obrazac kao poslat
                session['submitted_form_id'] = request.form.get('form_id')
                
                if duplicate:
                    flash('Vaša prijava je duplikat. Molimo proverite podatke i pokušajte ponovo.', 'warning')
                    return redirect(url_for('application'))
                
                try:
                    # Proveri i kreiraj direktorijum za priloge ako ne postoji
                    attachments_dir = ensure_attachments_dir_exists()
                    
                    # Sačuvaj dokumente u fajl sistem
                    saved_files = []
                    attachment_data = []
                    if 'documents' in form_data and any(form_data['documents']):
                        for index, document in enumerate(form_data['documents']):
                            if document:
                                # Kreiramo ime fajla u formatu application.id-index
                                file_name = f"{application.id}-{index}{os.path.splitext(document.filename)[1]}"
                                file_path = os.path.join(attachments_dir, file_name)
                                rel_path = os.path.join('static', 'attachments', file_name)
                                
                                # Sačuvaj fajl
                                document.save(file_path)
                                app.logger.info(f"Fajl sačuvan na putanji: {file_path}")
                                
                                # Dodaj informacije o fajlu u listu sačuvanih fajlova
                                saved_files.append({
                                    'path': file_path,
                                    'filename': document.filename,
                                    'mimetype': document.mimetype
                                })
                                
                                # Dodaj informacije za bazu podataka - koristimo samo ime fajla za kasnije dobijanje putanje
                                attachment_data.append({
                                    'path': rel_path,
                                    'filename': document.filename,
                                    'mimetype': document.mimetype
                                })
                                app.logger.info(f"Podaci o fajlu dodati za bazu: {file_path}")
                                app.logger.info(f"Apsolutna putanja: {file_path}")
                                app.logger.info(f"Provera postojanja fajla: {os.path.exists(file_path)}")
                                app.logger.info(f"Veličina fajla: {os.path.getsize(file_path) if os.path.exists(file_path) else 'Fajl ne postoji'}")
                                
                        
                        # Sačuvaj podatke o prilozima u bazi
                        import json
                        application.attachment_paths = json.dumps(attachment_data)
                        db.session.commit()
                    
                    # Kopiraj form_data i dodaj putanje do sačuvanih fajlova
                    form_data_copy = form_data.copy()
                    # Ukloni documents jer ne mogu da se serializuju
                    if 'documents' in form_data_copy:
                        form_data_copy.pop('documents')
                    
                    # Dodaj informacije o sačuvanim fajlovima
                    form_data_copy['saved_files'] = saved_files
                    
                    # Pošalji email asinhrono sa informacijama o fajlovima
                    task_result = send_email_task.delay(form_data_copy)
                    app.logger.info(f"Email za prijavu {application.id} poslat asinhrono sa task ID: {task_result.id}")
                except Exception as e:
                    # Logiraj grešku, ali ne prikazuj korisniku tehničke detalje
                    app.logger.error(f"Greška pri slanju asinhronog email-a: {str(e)}")
                    flash('Vaša prijava je sačuvana, ali postoji problem sa slanjem email obaveštenja.', 'warning')
                
                flash('Prijava je uspešno poslata.', 'success')
                return redirect(url_for('submission_details', application_id=application.id))
            except SQLAlchemyError as e:
                app.logger.error(f"Greška pri čuvanju prijave u bazi: {str(e)}")
                flash('Došlo je do problema pri čuvanju vaše prijave. Molimo pokušajte ponovo kasnije.', 'danger')
        
        try:
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
        except Exception as e:
            app.logger.error(f"Greška pri renderovanju forme za prijavu: {str(e)}")
            abort(500)
    except Exception as e:
        app.logger.error(f"Neočekivana greška u application ruti: {str(e)}")
        flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('index'))

@app.route('/confirmation')
def confirmation():
    try:
        school_name = os.getenv('SCHOOL_NAME')
        school_phone = os.getenv('SCHOOL_PHONE')
        school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
        school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
        return render_template('confirmation.html',
                                school_name=school_name, 
                                school_phone=school_phone, 
                                school_email=school_email,
                                school_web_address=school_web_address)
    except Exception as e:
        app.logger.error(f"Greška pri prikazu stranice za potvrdu: {str(e)}")
        flash('Došlo je do greške pri prikazivanju stranice za potvrdu.', 'danger')
        return redirect(url_for('index'))

@app.route('/submission_details/<int:application_id>')
def submission_details(application_id):
    try:
        # Proveri da li je ID aplikacije u sesiji isti kao traženi
        session_app_id = session.get('application_id')
        
        # Zaštita - samo dozvoli pristup aplikaciji koja je u sesiji
        if not session_app_id or int(session_app_id) != application_id:
            flash('Nemate pristup ovim podacima.', 'danger')
            return redirect(url_for('application'))
        
        try:
            # Pronađi aplikaciju u bazi
            application = Application.query.get_or_404(application_id)
            
            # Proveri da li je aplikacija duplikat
            is_duplicate = session.get('duplicate_application', False)
            
            try:
                school_name = os.getenv('SCHOOL_NAME')
                school_phone = os.getenv('SCHOOL_PHONE')
                school_email = os.getenv('SCHOOL_EMAIL_GENERAL')
                school_web_address = os.getenv('SCHOOL_WEB_ADDRESS')
                
                return render_template('submission_details.html',
                                    application=application,
                                    is_duplicate=is_duplicate,
                                    school_name=school_name,
                                    school_phone=school_phone,
                                    school_email=school_email,
                                    school_web_address=school_web_address)
            except Exception as e:
                app.logger.error(f"Greška pri renderovanju stranice sa detaljima prijave: {str(e)}")
                abort(500)
        except SQLAlchemyError as e:
            app.logger.error(f"Greška pri pristupu podacima o prijavi {application_id}: {str(e)}")
            flash('Došlo je do problema pri pristupanju podacima o vašoj prijavi.', 'danger')
            return redirect(url_for('application'))
    except Exception as e:
        app.logger.error(f"Neočekivana greška u submission_details ruti: {str(e)}")
        flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('index'))

# Admin rute
@app.route('/admin')
@login_required
def admin_dashboard():
    return redirect(url_for('applications_list'))

@app.route('/admin/applications', methods=['GET', 'POST'])
@login_required
def applications_list():
    try:
        # Form i filtri
        sort = request.args.get('sort', 'date_asc')  # Promena podrazumevanog sortiranja na najstarije → najnovije
        query = Application.query
        
        # Popunjavamo inicijalne vrednosti forme iz URL parametara ako je u pitanju GET zahtev
        search_term = request.args.get('search_term', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        grade_filter = request.args.get('grade_filter', '')
        
        form = SearchForm()
        
        # Ako je u pitanju GET zahtev sa parametrima, inicijalizujemo formu sa tim vrednostima
        if request.method == 'GET' and (search_term or date_from or date_to or grade_filter):
            form.search_term.data = search_term
            
            # Parsiramo i inicijalizujemo date_from iz URL parametra
            if date_from:
                try:
                    if 'T' in date_from:  # Format sa vremenom
                        form.date_from.data = datetime.strptime(date_from, '%Y-%m-%dT%H:%M')
                    else:  # Samo datum
                        form.date_from.data = datetime.strptime(date_from, '%Y-%m-%d')
                except ValueError:
                    app.logger.error(f"Greška pri parsiranju date_from iz URL: {date_from}")
            
            # Parsiramo i inicijalizujemo date_to iz URL parametra
            if date_to:
                try:
                    if 'T' in date_to:  # Format sa vremenom
                        form.date_to.data = datetime.strptime(date_to, '%Y-%m-%dT%H:%M')
                    else:  # Samo datum
                        form.date_to.data = datetime.strptime(date_to, '%Y-%m-%d')
                except ValueError:
                    app.logger.error(f"Greška pri parsiranju date_to iz URL: {date_to}")
            
            # Inicijalizujemo grade_filter
            form.grade_filter.data = grade_filter
        
        try:
            # Primeni filtere ako postoje
            if form.validate_on_submit() or any([search_term, date_from, date_to, grade_filter]):
                # Ako je forma validna, koristimo vrednosti iz forme
                if form.validate_on_submit():
                    search_term = form.search_term.data
                    date_from = form.date_from.data
                    date_to = form.date_to.data
                    grade_filter = form.grade_filter.data
                    
                    # Redirektujemo na istu stranicu sa GET parametrima da bi se vrednosti sačuvale
                    # i da bi se mogle ponovo koristiti pri paginaciji
                    return redirect(url_for('applications_list', 
                        search_term=search_term,
                        date_from=date_from.strftime('%Y-%m-%dT%H:%M') if date_from else '',
                        date_to=date_to.strftime('%Y-%m-%dT%H:%M') if date_to else '',
                        grade_filter=grade_filter,
                        sort=sort))
                # Inače, koristimo vrednosti iz URL-a ako postoje
                
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
                
                # Filtriranje po datumu i vremenu od
                if date_from:
                    try:
                        if isinstance(date_from, str):
                            # Proveravamo format datuma sa vremenom
                            if 'T' in date_from:  # Format iz datetime-local inputa
                                date_from = datetime.strptime(date_from, '%Y-%m-%dT%H:%M')
                            else:  # Stariji format za kompatibilnost
                                date_from = datetime.strptime(date_from, '%Y-%m-%d')
                        query = query.filter(Application.date_submitted >= date_from)
                    except ValueError as e:
                        app.logger.error(f"Greška pri parsiranju početnog datuma: {str(e)}")
                        flash('Format datuma za početni datum nije validan. Koristite format YYYY-MM-DDThh:mm.', 'danger')
                    
                # Filtriranje po datumu i vremenu do
                if date_to:
                    try:
                        if isinstance(date_to, str):
                            if 'T' in date_to:  # Format iz datetime-local inputa
                                date_to = datetime.strptime(date_to, '%Y-%m-%dT%H:%M')
                                # Ne dodajemo krajnje vreme dana jer je vreme već specificirano
                            else:  # Stariji format za kompatibilnost
                                date_to = datetime.strptime(date_to, '%Y-%m-%d')
                                # Postavi kraj dana za završni datum ako je samo datum specificiran
                                date_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59)
                        elif not isinstance(date_to, datetime):  # Ako je samo datum bez vremena
                            # Postavi kraj dana za završni datum
                            date_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59)
                        query = query.filter(Application.date_submitted <= date_to)
                    except ValueError as e:
                        app.logger.error(f"Greška pri parsiranju krajnjeg datuma: {str(e)}")
                        flash('Format datuma za krajnji datum nije validan. Koristite format YYYY-MM-DDThh:mm.', 'danger')
                    
                # Filtriranje po razredu
                if grade_filter and grade_filter != '':
                    # Debug poruka za pomoć u praćenju problema
                    app.logger.info(f"Filtriranje po razredu: {grade_filter}, tip: {type(grade_filter)}")
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
            try:
                page = request.args.get('page', 1, type=int)
                per_page = 20  # Broj stavki po stranici
                applications = query.paginate(page=page, per_page=per_page)
                
                school_name = os.getenv('SCHOOL_NAME')
                return render_template('applications_list.html',
                                        school_name=school_name,
                                        applications=applications,
                                        form=form,
                                        current_sort=sort)
            except Exception as e:
                app.logger.error(f"Greška pri paginaciji ili renderovanju liste prijava: {str(e)}")
                flash('Došlo je do greške pri pripremi prikaza podataka. Molimo pokušajte ponovo.', 'danger')
                return redirect(url_for('admin_dashboard'))
        except SQLAlchemyError as e:
            app.logger.error(f"SQLAlchemy greška pri pristupu listi prijava: {str(e)}")
            flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
            return redirect(url_for('admin_dashboard'))
    except Exception as e:
        app.logger.error(f"Neočekivana greška u applications_list ruti: {str(e)}")
        flash('Došlo je do neočekivane greške. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/application/<int:application_id>')
@login_required
def application_detail(application_id):
    try:
        # Pronađi aplikaciju u bazi
        application = Application.query.get_or_404(application_id)
        
        try:
            school_name = os.getenv('SCHOOL_NAME')
            return render_template('application_detail.html',
                                   school_name=school_name,
                                   application=application)
        except Exception as e:
            app.logger.error(f"Greška pri renderovanju stranice sa detaljima prijave: {str(e)}")
            abort(500)
    except SQLAlchemyError as e:
        app.logger.error(f"Greška pri pristupu podacima o prijavi {application_id}: {str(e)}")
        flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('applications_list'))

# API ruta za JSON podatke
@app.route('/api/applications')
@login_required
def api_applications():
    try:
        applications = Application.query.all()
        try:
            return jsonify([app.to_dict() for app in applications])
        except Exception as e:
            app.logger.error(f"Greška pri serijalizaciji podataka u JSON: {str(e)}")
            return jsonify({
                'greška': 'Došlo je do greške pri pripremi JSON odgovora',
                'status': 'error'
            }), 500
    except SQLAlchemyError as e:
        app.logger.error(f"Greška pri pristupu bazi podataka za API: {str(e)}")
        return jsonify({
            'greška': 'Došlo je do problema pri pristupanju bazi podataka',
            'status': 'error'
        }), 500
            
# Ruta za eksport podataka u PDF formatu
@app.route('/admin/export_applications')
@login_required
def export_applications():
    try:
        # Preuzimanje parametara za filtriranje
        search_term = request.args.get('search_term')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        grade_filter = request.args.get('grade_filter')
        sort = request.args.get('sort', 'date_desc')  # Podrazumevano sortiraj po datumu opadajuće
        
        # Inicijalizuj upit za filtriranje
        query = Application.query
        
        # Primeni filtere ako postoje
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
        
        # Filtriranje po datumu i vremenu od
        if date_from:
            try:
                if isinstance(date_from, str):
                    # Proveravamo format datuma sa vremenom
                    if 'T' in date_from:  # Format iz datetime-local inputa
                        date_from = datetime.strptime(date_from, '%Y-%m-%dT%H:%M')
                    else:  # Stariji format za kompatibilnost
                        date_from = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Application.date_submitted >= date_from)
            except ValueError as e:
                app.logger.error(f"Greška pri parsiranju početnog datuma: {str(e)}")
                flash('Format datuma za početni datum nije validan. Koristite format YYYY-MM-DDThh:mm.', 'danger')
            
        # Filtriranje po datumu i vremenu do
        if date_to:
            try:
                if isinstance(date_to, str):
                    if 'T' in date_to:  # Format iz datetime-local inputa
                        date_to = datetime.strptime(date_to, '%Y-%m-%dT%H:%M')
                        # Ne dodajemo kraj dana ako je vreme već specificirano
                    else:  # Stariji format za kompatibilnost
                        date_to = datetime.strptime(date_to, '%Y-%m-%d')
                        # Postavi kraj dana ako je samo datum specificiran
                        date_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59)
                elif not isinstance(date_to, datetime):  # Ako je samo datum bez vremena
                    # Postavi kraj dana za završni datum
                    date_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59)
                query = query.filter(Application.date_submitted <= date_to)
            except ValueError as e:
                app.logger.error(f"Greška pri parsiranju krajnjeg datuma: {str(e)}")
                flash('Format datuma za krajnji datum nije validan. Koristite format YYYY-MM-DDThh:mm.', 'danger')
            
        # Filtriranje po razredu
        if grade_filter and grade_filter != '':
            app.logger.info(f"PDF export - filtriranje po razredu: {grade_filter}, tip: {type(grade_filter)}")
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
        
        # Izvršavanje upita
        applications = query.all()
        
        # Kreiranje PDF dokumenta
        class PDF(FPDF):
            def __init__(self):
                super().__init__()
                # Putanje do fontova
                font_path = os.path.join(app.root_path, 'static', 'fonts')
                self.add_font('DejaVu', '', os.path.join(font_path, 'DejaVuSansCondensed.ttf'), uni=True)
                self.add_font('DejaVu', 'B', os.path.join(font_path, 'DejaVuSansCondensed-Bold.ttf'), uni=True)
            
            def header(self):
                # Naslov
                self.set_font('DejaVu', 'B', 15)
                self.cell(0, 10, 'Pregled prijava dnevnog boravka', 0, new_x="LMARGIN", new_y="NEXT", align='C')
                
                # Datum i vreme generisanja
                self.set_font('DejaVu', '', 10)
                self.cell(0, 10, f'Generisano: {datetime.now().strftime("%d.%m.%Y. %H:%M")}', 0, new_x="LMARGIN", new_y="NEXT", align='R')
                
                # Prikazivanje filtera ako postoje
                filter_text = "Primenjeni filteri: "
                has_filters = False
                
                if search_term:
                    filter_text += f"Pretraga: '{search_term}', "
                    has_filters = True
                    
                if date_from:
                    filter_date = date_from.strftime("%d.%m.%Y.") if isinstance(date_from, datetime) else date_from
                    filter_text += f"Od datuma: {filter_date}, "
                    has_filters = True
                    
                if date_to:
                    filter_date = date_to.strftime("%d.%m.%Y.") if isinstance(date_to, datetime) else date_to
                    filter_text += f"Do datuma: {filter_date}, "
                    has_filters = True
                    
                if grade_filter:
                    filter_text += f"Razred: {grade_filter}, "
                    has_filters = True
                
                if has_filters:
                    # Ukloni poslednji zarez i razmak
                    filter_text = filter_text[:-2]
                    self.cell(0, 10, filter_text, 0, new_x="LMARGIN", new_y="NEXT", align='L')
                
                # Linija ispod zaglavlja
                self.line(10, self.get_y(), self.w - 10, self.get_y())
                self.set_y(self.get_y() + 5)  # Razmak nakon linije
                
                # Definisanje širine kolona za konzistentnost kroz ceo dokument
                col_width_1 = 50  # Ime i prezime deteta - sužena kolona
                col_width_2 = 20   # Razred
                col_width_3 = 90   # Roditelji - dodatno proširena kolona za roditelje
                col_width_4 = 30   # Datum prijave
                
                # Zaglavlje tabele
                self.set_font('DejaVu', 'B', 11)
                self.cell(col_width_1, 10, 'Ime i prezime deteta', 1, align='C')
                self.cell(col_width_2, 10, 'Razred', 1, align='C')
                self.cell(col_width_3, 10, 'Roditelji', 1, align='C')
                self.cell(col_width_4, 10, 'Datum prijave', 1, new_x="LMARGIN", new_y="NEXT", align='C')
                
                # Čuvamo širine kolona kao atribute klase
                self.col_width_1 = col_width_1
                self.col_width_2 = col_width_2
                self.col_width_3 = col_width_3
                self.col_width_4 = col_width_4
            
            def footer(self):
                # Pozicioniranje na 1.5 cm od dna
                self.set_y(-15)
                self.set_font('DejaVu', '', 8)  # Koristimo regularan font umesto italic
                # Broj stranice
                self.cell(0, 10, f'Strana {self.page_no()}/{{nb}}', 0, new_x="LMARGIN", new_y="NEXT", align='C')
        
        # Kreiranje PDF-a
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Sadržaj tabele
        pdf.set_font('DejaVu', '', 10)
        
        # Jednostavniji pristup generisanju tabele - jedna ćelija po redu za roditelje
        for application in applications:
            # Provera da li je potrebna nova stranica zbog visine reda
            if pdf.get_y() > pdf.h - 30:
                pdf.add_page()
            
            # Ime i prezime deteta
            pdf.cell(pdf.col_width_1, 10, f"{application.children_name} {application.children_surname}", 1, align='L')
            
            # Razred / Odeljenje
            pdf.cell(pdf.col_width_2, 10, f"{application.grade}/{application.class_number}", 1, align='C')
            
            # Ime i prezime roditelja - u jednom redu sa skraćenim oznakama M: i O:
            parent_info = f"M: {application.mother_name} {application.mother_surname}, O: {application.father_name} {application.father_surname}"
            pdf.cell(pdf.col_width_3, 10, parent_info, 1, align='L')
            
            # Datum i vreme prijave
            pdf.cell(pdf.col_width_4, 10, application.date_submitted.strftime('%d.%m.%Y. %H:%M'), 1, new_x="LMARGIN", new_y="NEXT", align='C')
        
        # Dodavanje ukupnog broja prijava na kraju
        pdf.set_font('DejaVu', 'B', 11)
        ukupna_sirina = pdf.col_width_1 + pdf.col_width_2 + pdf.col_width_3 + pdf.col_width_4
        pdf.cell(ukupna_sirina, 10, f"Ukupan broj prijava: {len(applications)}", 0, new_x="LMARGIN", new_y="NEXT", align='R')
        
        # Generisanje PDF-a u memoriji
        pdf_output = io.BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)
        
        # Definisanje imena fajla sa trenutnim datumom i vremenom
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prijave_dnevni_boravak_{current_time}.pdf"
        
        # Slanje PDF-a klijentu
        return send_file(
            pdf_output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    
    except SQLAlchemyError as e:
        app.logger.error(f"SQLAlchemy greška pri eksportovanju prijava: {str(e)}")
        flash('Došlo je do problema pri pristupu bazi podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('applications_list'))
    except Exception as e:
        app.logger.error(f"Neočekivana greška pri eksportovanju prijava: {str(e)}")
        flash('Došlo je do neočekivane greške pri eksportovanju podataka. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('applications_list'))
