from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, FileField, BooleanField, MultipleFileField 
from wtforms.validators import DataRequired, Regexp #, FileRequired


class ApplicationForm(FlaskForm):
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
