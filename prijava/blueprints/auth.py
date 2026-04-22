from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from prijava import db
from prijava.form import LoginForm, RequestResetForm, ResetPasswordForm
from prijava.models import User
from prijava.services.email import send_reset_email


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password, form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                flash('Uspešno ste se prijavili.', 'success')
                return redirect(next_page if next_page else url_for('admin.dashboard'))
            flash('Prijavljivanje nije uspelo. Proverite email i lozinku.', 'danger')
        except SQLAlchemyError as exc:
            current_app.logger.error(f"Greška pri pristupu bazi podataka tokom prijave: {exc}")
            flash('Došlo je do problema sa pristupom sistemu. Molimo pokušajte kasnije.', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/reset_password_request', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    form = RequestResetForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                try:
                    send_reset_email(user)
                    flash('Poslat je email sa uputstvima za resetovanje lozinke.', 'info')
                    return redirect(url_for('auth.login'))
                except Exception as exc:
                    current_app.logger.error(f"Greška pri slanju email-a za reset lozinke: {exc}")
                    flash('Došlo je do problema pri slanju email-a. Molimo pokušajte ponovo kasnije.', 'danger')
            else:
                flash('Nije pronađen nalog sa tim email-om.', 'danger')
        except SQLAlchemyError as exc:
            current_app.logger.error(f"Greška pri pristupu bazi podataka: {exc}")
            flash('Došlo je do problema sa bazom podataka. Molimo pokušajte kasnije.', 'danger')

    return render_template('reset_request.html', form=form)


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    try:
        user = User.query.filter_by(reset_token=token).first()

        if not user or not user.is_reset_token_valid(token):
            flash('Neispravan ili istekao token za resetovanje lozinke.', 'danger')
            return redirect(url_for('auth.reset_request'))

        form = ResetPasswordForm()
        if form.validate_on_submit():
            try:
                user.password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
                user.clear_reset_token()
                db.session.commit()

                flash('Vaša lozinka je uspešno promenjena. Sada se možete prijaviti.', 'success')
                return redirect(url_for('auth.login'))
            except SQLAlchemyError as exc:
                db.session.rollback()
                current_app.logger.error(f"Greška pri ažuriranju lozinke u bazi: {exc}")
                flash('Došlo je do greške pri ažuriranju lozinke. Molimo pokušajte ponovo kasnije.', 'danger')

        return render_template('reset_password.html', form=form)
    except SQLAlchemyError as exc:
        current_app.logger.error(f"Greška pri pristupu bazi podataka pri resetovanju lozinke: {exc}")
        flash('Došlo je do problema sa pristupom bazi. Molimo pokušajte ponovo kasnije.', 'danger')
        return redirect(url_for('auth.reset_request'))


@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('Uspešno ste se odjavili.', 'success')
    return redirect(url_for('auth.login'))
