import os
from flask_mail import Message
from datetime import datetime
from prijava import app, mail, db
from flask import render_template, request, redirect, url_for, flash, jsonify, abort, session
from sqlalchemy.exc import SQLAlchemyError
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from prijava.form import ApplicationForm, LoginForm, SearchForm, RequestResetForm, ResetPasswordForm
from prijava.models import User, Application
from sqlalchemy import or_, and_, desc, asc

def save_application_to_db(form_data):
    try:
        # Provera da li već postoji ista prijava u sistemu
        existing_application = Application.query.filter(
            Application.children_name == form_data['children_name'],
            Application.children_surname == form_data['children_surname'],
            Application.mother_name == form_data['mother_name'],
            Application.mother_surname == form_data['mother_surname'],
            Application.father_name == form_data['father_name'],
            Application.father_surname == form_data['father_surname'],
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
                    # Pošalji email
                    send_email(form_data)
                except Exception as e:
                    # Logiraj grešku, ali ne prikazuj korisniku tehničke detalje
                    app.logger.error(f"Email error: {str(e)}")
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
        form = SearchForm()
        sort = request.args.get('sort', 'date_desc')  # Podrazumevano sortiraj po datumu opadajuće
        
        # Inicijalizuj upit za filtriranje
        query = Application.query
        
        try:
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
                    try:
                        if isinstance(date_from, str):
                            date_from = datetime.strptime(date_from, '%Y-%m-%d')
                        query = query.filter(Application.date_submitted >= date_from)
                    except ValueError as e:
                        app.logger.error(f"Greška pri parsiranju početnog datuma: {str(e)}")
                        flash('Format datuma za početni datum nije validan. Koristite format YYYY-MM-DD.', 'danger')
                    
                # Filtriranje po datumu do
                if date_to:
                    try:
                        if isinstance(date_to, str):
                            date_to = datetime.strptime(date_to, '%Y-%m-%d')
                        # Postavi kraj dana za završni datum
                        date_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59)
                        query = query.filter(Application.date_submitted <= date_to)
                    except ValueError as e:
                        app.logger.error(f"Greška pri parsiranju krajnjeg datuma: {str(e)}")
                        flash('Format datuma za krajnji datum nije validan. Koristite format YYYY-MM-DD.', 'danger')
                    
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
