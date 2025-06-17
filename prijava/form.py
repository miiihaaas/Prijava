from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, FileField, BooleanField, MultipleFileField, PasswordField, DateField, DateTimeField, HiddenField
from wtforms.validators import DataRequired, Regexp, Email, Length, EqualTo, ValidationError #, FileRequired
from flask_wtf.file import FileAllowed


class LoginForm(FlaskForm):
    email = StringField('Email adresa', validators=[DataRequired(), Email()])
    password = PasswordField('Lozinka', validators=[DataRequired()])
    submit = SubmitField('Prijavi se')

class RequestResetForm(FlaskForm):
    email = StringField('Email adresa', validators=[DataRequired(), Email()])
    submit = SubmitField('Pošalji zahtev za reset lozinke')
    
class ResetPasswordForm(FlaskForm):
    password = PasswordField('Nova lozinka', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Potvrdite lozinku', validators=[DataRequired(), EqualTo('password', message='Lozinke se moraju podudarati.')])
    submit = SubmitField('Promeni lozinku')

class ApplicationForm(FlaskForm):
    form_id = HiddenField()
    children_name = StringField('Ime deteta', validators=[DataRequired()])
    children_surname = StringField('Prezime deteta', validators=[DataRequired()])
    mother_name = StringField('Ime majke', validators=[DataRequired()])
    mother_surname = StringField('Prezime majke', validators=[DataRequired()])
    father_name = StringField('Ime oca', validators=[DataRequired()])
    father_surname = StringField('Prezime oca', validators=[DataRequired()])
    
    grade = SelectField('Razred', 
                        choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')],
                        validators=[DataRequired()])
    class_number = SelectField('Odeljenje', 
                                choices=[(str(i), str(i)) for i in range(1, 11)],
                                validators=[DataRequired()])
    
    documents = MultipleFileField ('Priložite dokumente (po potrebi, priložite više fajlova odjednom)', validators=[])
    
    consent = BooleanField('Saglasan sam da škola za svoje potrebe obrađuje podatke iz dostavljene dokumentacije',
                            validators=[DataRequired()])
    
    submit = SubmitField('Pošalji')

class SearchForm(FlaskForm):
    search_term = StringField('Pretraga', validators=[])
    date_from = DateTimeField('Od datuma i vremena', validators=[], format='%Y-%m-%dT%H:%M')
    date_to = DateTimeField('Do datuma i vremena', validators=[], format='%Y-%m-%dT%H:%M')
    grade_filter = SelectField('Razred', 
                           choices=[('', 'Svi'), ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')],
                           validators=[])
    submit = SubmitField('Pretraži')
