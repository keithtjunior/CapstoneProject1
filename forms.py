from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SelectMultipleField, validators

class LoginForm(FlaskForm):
    """Login form"""
    username    = StringField('Username', [validators.Length(min=1, max=64), validators.DataRequired()])
    password    = PasswordField('Password', [validators.Length(min=8, max=256), validators.DataRequired()])

class RegisterForm(FlaskForm):
    """Registration Form"""
    username    = StringField('Username', [validators.Length(min=1, max=64), validators.DataRequired()])
    password    = PasswordField('Password', [validators.Length(min=8, max=256), validators.DataRequired()])
    first_name  = StringField('First Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    last_name   = StringField('Last Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    city        = StringField('City', [validators.Length(min=1, max=50), validators.DataRequired()])
    location    = SelectField('Country / Region', [validators.DataRequired()])
    languages   = SelectMultipleField('Languages', [validators.DataRequired()])
    email       = StringField('E-mail', [validators.Length(min=3, max=320), validators.Email(), validators.DataRequired()])


class AccountForm(FlaskForm):
    """Account Form"""
    username    = StringField('Username', [validators.Length(min=1, max=64), validators.DataRequired()])
    first_name  = StringField('First Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    last_name   = StringField('Last Name', [validators.Length(min=1, max=50), validators.DataRequired()])
    city        = StringField('City', [validators.Length(min=1, max=50), validators.DataRequired()])
    location    = SelectField('Country / Region', [validators.DataRequired()])
    languages   = SelectMultipleField('Languages', [validators.DataRequired()])
    email       = StringField('E-mail', [validators.Length(min=3, max=320), validators.Email(), validators.DataRequired()])

class PasswordForm(FlaskForm):
    """Password Form"""
    current_password    = PasswordField('Current Password', [validators.Length(min=8, max=256), validators.DataRequired()])
    new_password        = PasswordField('New Password', [validators.Length(min=8, max=256), validators.DataRequired()])
    confirm_password    = PasswordField('Repeat Password', [validators.Length(min=8, max=256), validators.DataRequired()])

class TargetLanguageForm(FlaskForm):
    """Target Language Form"""
    target_language = SelectField('Target Language', [validators.DataRequired()])


