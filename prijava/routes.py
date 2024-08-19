import os
from flask_mail import Message
from prijava import app, mail
from flask import render_template, request, redirect, url_for, flash
from prijava.form import ApplicationForm

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
        send_email(form_data)
        flash('Form submitted successfully!', 'success')
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
