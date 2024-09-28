"""Feedback application."""


from flask import Flask, g, request, render_template, redirect, session, flash, send_from_directory
from socketio import Server, WSGIApp
from flask_debugtoolbar import DebugToolbarExtension
from google.cloud import translate_v2 as translate
from sqlalchemy import desc, asc, or_
from sqlalchemy.exc import IntegrityError

from models import db, connect_db, User, Thread, Message, UserThread, Call, UserCall, Contact, Country, Language, UserLanguages
from forms import LoginForm, RegisterForm, AccountForm, PasswordForm, TargetLanguageForm
from dateutil import relativedelta
from datetime import datetime, timedelta
import html2text
import json, os
import uuid

CURR_USER_KEY = 'CURR_USER_KEY'

async_mode = None

instrument = False
admin_login = {
    'username': 'USERNAME',
    'password': 'PASSWORD', 
}

sio = Server(
    async_mode=async_mode,
    cors_allowed_origins=None)
if instrument:
    sio.instrument(auth=admin_login)

app = Flask(__name__)
app.wsgi_app = WSGIApp(sio, app.wsgi_app)

app.url_map.strict_slashes = False
app.config['SECRET_KEY'] = 'SECRET_KEY'
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

debug = DebugToolbarExtension(app)

app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgresql:///feedback'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r'GOOGLE_CLOUD_KEY'

connect_db(app)
db.create_all()


##############################################################################
# Google Cloud Translation
# https://cloud.google.com/translate/docs/basic/translating-text

def translate_text(target: str, text: str) -> dict:
    """Translates text into the target language."""
    
    translate_client = translate.Client()

    if isinstance(text, bytes):
        text = text.decode("utf-8")

    result = translate_client.translate(text, target_language=target)
    return result

def detect_language(text: str) -> dict:
    """Detects the text's language."""
    from google.cloud import translate_v2 as translate

    translate_client = translate.Client()

    result = translate_client.detect_language(text)
    return result


##############################################################################
# Homepage, error pages and misc.

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.errorhandler(404) 
def not_found(e): 
    return render_template('error.html', e=e)

@app.before_request
def add_user_to_g():
    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])
        db.session.query(User).filter_by(id=g.user.id).update({'is_online':True})
        db.session.commit()
    else:
        g.user = None

def do_login(user):
    session[CURR_USER_KEY] = user.id

def do_logout():
    if CURR_USER_KEY in session:
        db.session.query(User).filter_by(id=g.user.id).update({'is_online':False})
        db.session.commit()
        del session[CURR_USER_KEY]

@app.route('/')
def home():
    """Show homepage"""
    if g.user:
        return redirect('/chats')
    else:
        return redirect("/login")


##############################################################################
# User signup/login/logout

@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Register new user"""

    languages = Language.query.all()
    countries = Country.query.all()

    form = RegisterForm()
    form.location.choices = [(c.iso, c.name) for c in countries]
    form.languages.choices = [(l.code, l.name) for l in languages]

    if form.validate_on_submit():
        try:
            user = User.signup(
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                username=form.username.data,
                email=form.email.data,
                city=form.city.data,
                country_iso=form.location.data,
                password=form.password.data
            )
            db.session.commit()

            for language in form.languages.data:
                lang = UserLanguages(user_id=user.id, language_code=language)
                db.session.add(lang)

            user.target_language = form.languages.data[0]
            db.session.commit()
            
        except IntegrityError:
            flash('Error: Username already taken', 'success')
            return render_template('users/register.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/register.html', form=form)

@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)
        if user:
            do_login(user)
            flash(f'Hello, {user.first_name}!', 'success')
            return redirect("/")

        flash('Error: Invalid credentials.', 'success')

    return render_template('users/login.html', form=form)

@app.route('/logout')
def logout():
    """Handle logout of user."""
    do_logout()
    flash('You are currently logged out.', 'success')
    return redirect('/')


##############################################################################
# User routes:
@app.route('/users')
def list_users():
    """Listing of users"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")

    search = request.args.get('q')

    contact_ids = [contacts.id for contacts in g.user.contacts]

    if not search:
        users = User.query.filter(User.id != g.user.id, User.id.notin_(contact_ids)).all()
    else:
        users = User.query.filter(
            User.id != g.user.id, 
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%")),
            User.id.notin_(contact_ids)).all()

    return render_template('users/list.html', users=users, current_user=g.user)

@app.route('/users/<int:user_id>')
def show_user(user_id):
    """Show user profiles."""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")

    search = request.args.get('q')

    contact_ids = [contacts.id for contacts in g.user.contacts]

    if not search:
        users = User.query.filter(User.id != g.user.id, User.id.notin_(contact_ids)).all()
    else:
        users = User.query.filter(
            User.id != g.user.id, 
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%")),
            User.id.notin_(contact_ids)).all()

    main_user = User.query.get_or_404(user_id)
    
    return render_template('users/show-user.html', 
        users=users, main_user=main_user, current_user=g.user)

@app.route('/users/<int:user_id>', methods=['POST'])
def add_user_contact(user_id):
    """Add user to contacts."""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/")

    contact = User.query.get_or_404(user_id)
    g.user.contacts.append(contact)
    contact.contacts.append(g.user)

    db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=contact.id).update({'is_pending':False})
    
    db.session.commit()

    flash(f'User ({contact.username}) added to contacts (pending).', 'success')
    return redirect(f"/users/contacts/{contact.id}")


@app.route('/users/profile', methods=["GET", "POST"])
def user_profile():
    """Show / Update current user profile info."""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    user = User.query.get_or_404(g.user.id)

    languages = Language.query.all()
    countries = Country.query.all()

    form_password = PasswordForm()
    form_account = AccountForm(obj=user)
    form_account.location.choices = [(c.iso, c.name) for c in countries]
    form_account.languages.choices = [(l.code, l.name) for l in languages]
    
    if request.method == 'GET':
        form_account.username.data = user.username
        form_account.first_name.data = user.first_name
        form_account.last_name.data = user.last_name
        form_account.email.data = user.email
        form_account.city.data = user.city
        form_account.location.data = user.country_iso   
        form_account.languages.data = [language.code for language in user.languages]

        return render_template('users/profile.html', 
            user=g.user, languages=languages, countries=countries, 
            form_account=form_account, form_password=form_password)
    else:
        if form_account.validate_on_submit():
            data = {
                'first_name':form_account.first_name.data,
                'last_name':form_account.last_name.data,
                'email': form_account.email.data,
                'city': form_account.city.data,
                'country_iso': form_account.location.data
            }
            db.session.query(User).filter_by(id=g.user.id).update(data)
            db.session.query(UserLanguages).filter(
                UserLanguages.user_id==g.user.id).delete()
            
            for language in form_account.languages.data:
                lang = UserLanguages(user_id=g.user.id, language_code=language)
                db.session.add(lang)
            
            db.session.commit()
            flash('Profile updated.', 'success')
            return redirect('/users/profile')

    return render_template('users/profile.html', 
        user=g.user, languages=languages, countries=countries, 
        form=form_account, form_password=form_password)

@app.route('/users/profile/password', methods=["POST"])
def update_user_password():
    """Update user password."""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    user = User.query.get_or_404(g.user.id)
    form = PasswordForm()

    if form.validate_on_submit():
        user = User.authenticate(user.username,
                                form.current_password.data)
        if not user:
            flash('Error: Invalid password', 'success')
            return redirect('/users/profile')
        
        if form.new_password.data != form.confirm_password.data:
            flash('Error: Passwords do not match', 'success')
            return redirect('/users/profile')
        
        new_password = User.new_password(form.new_password.data)
        db.session.query(User).filter_by(
            id=g.user.id).update({'password':new_password})
        db.session.commit()
        flash('Password updated.', 'success')
        return redirect('/users/profile')
                
    return redirect('/users/profile')


##############################################################################
# Contacts routes:

@app.route('/users/contacts')
def list_contacts():
    """Show list of current user contacts"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")

    search = request.args.get('q')

    users = []

    if not search:
        _users = g.user.contacts
    else:
        _users = g.user.contacts.filter(
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%"))
        )

    for user in _users:
        if g.user in user.contacts:
            users.append({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'city': user.city,
                'country_iso': user.country_iso,
                'country': user.country,
                'class_color': user.class_color,
                'is_online': user.is_online,
                'is_pending': Contact.contact_is_pending(g.user, user)
            })
        else:
            users.append(user)

    return render_template('users/contacts.html', contacts=users, user_id=g.user.id)

@app.route('/users/contacts/<int:contact_id>')
def show_contact(contact_id):
    """Show contact profile"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")

    search = request.args.get('q')

    main_contact = User.query.get_or_404(contact_id)
    is_contact_in_call = False
    users = []

    if main_contact not in g.user.contacts:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/users/contacts")

    if not search:
        _users = g.user.contacts
    else:
        _users = g.user.contacts.filter(
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%"))
        )

    for user in _users:
        if g.user in user.contacts:
            users.append({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'city': user.city,
                'country_iso': user.country_iso,
                'country': user.country,
                'class_color': user.class_color,
                'is_online': user.is_online,
                'is_pending': Contact.contact_is_pending(g.user, user)
            })
        else:
            users.append(user)

    is_pending = Contact.contact_is_pending(g.user, main_contact)
    is_chatting = Contact.contact_is_chatting(g.user, main_contact)
    is_calling = Contact.contact_is_calling(g.user, main_contact)

    contact_contacts = db.session.query(Contact).\
    filter(or_(Contact.user_id == main_contact.id, 
        Contact.contact_id == main_contact.id)).all()
    
    for co in contact_contacts:
        if co.is_calling:
            is_contact_in_call = True

    return render_template('users/show-contact.html', 
        contacts=users, user_id=g.user.id, main_contact=main_contact, 
        is_pending=is_pending, is_chatting=is_chatting, is_calling=is_calling,
        is_contact_in_call=is_contact_in_call)

@app.route('/users/contacts/<int:contact_id>/update', methods=['POST'])
def update_contact(contact_id):
    """Update contact"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/")

    main_contact = User.query.get_or_404(contact_id)

    if main_contact not in g.user.contacts:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/users/contacts")

    # Set contact pending to false
    db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=main_contact.id).update({'is_pending': False})
    db.session.query(Contact).filter_by(user_id=main_contact.id, 
        contact_id=g.user.id).update({'is_pending': False})

    db.session.commit()
    
    flash(f'User ({main_contact.username}) contact is no longer pending.', 'success')
    return redirect(f"/users/contacts")

@app.route('/users/contacts/<int:contact_id>/delete', methods=['POST'])
def delete_contact(contact_id):
    """Delete contact"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/")

    main_contact = User.query.get_or_404(contact_id)

    if main_contact not in g.user.contacts:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/users/contacts")

    # Delete contacts
    user_contact_contact = db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=main_contact.id).first()
    contact_user_contact = db.session.query(Contact).filter_by(user_id=main_contact.id, 
        contact_id=g.user.id).first()
    
    db.session.delete(user_contact_contact)
    db.session.delete(contact_user_contact)

    # Delete chat threads if any
    users_in_threads = [{'id':thread.id, 'users':thread.users} for thread in main_contact.threads]
    existing_thread = next((item for item in users_in_threads if g.user in item['users']), None)

    if existing_thread:
        user_thread = db.session.query(UserThread).filter_by(user_id=g.user.id, 
            thread_id=existing_thread['id']).first()
        contact_thread = db.session.query(UserThread).filter_by(user_id=main_contact.id, 
            thread_id=existing_thread['id']).first()
        
        db.session.delete(user_thread)
        db.session.delete(contact_thread)

    # Delete calls if any
    users_in_calls = [{'id':call.id, 'users':call.users} for call in main_contact.calls]
    existing_call = next((item for item in users_in_calls if g.user in item['users']), None)

    if existing_call:
        user_call = db.session.query(UserCall).filter_by(user_id=g.user.id, 
            call_id=existing_call['id']).first()
        contact_call = db.session.query(UserCall).filter_by(user_id=main_contact.id, 
            call_id=existing_call['id']).first()
        
        db.session.delete(user_call)
        db.session.delete(contact_call)
    
    db.session.commit()
    
    flash(f'User ({main_contact.username}) was removed from contacts.', 'success')
    return redirect(f"/users/contacts")


##############################################################################
# Chat routes:

@app.route('/chats', methods=["GET", "POST"])
def chats():
    """Show list of current user chats"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    thread_ids = db.session.query(UserThread.thread_id).filter_by(user_id=g.user.id).all()

    search = request.args.get('q')

    if not search:
        threads = db.session.query(Thread).filter(Thread.id.in_(thread_ids)).all()
    else:
        _t = db.session.query(Thread).filter(Thread.id.in_(thread_ids)).all()
        threads = [thread for thread in _t if thread.users.filter(
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%"))
        ).all()]

    return render_template('index.html', threads=threads, current_user=g.user)

@app.route('/chats/<int:thread_id>/language', methods=["POST"])
def chats_language(thread_id):
    """Change user target langauge"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    user = User.query.get_or_404(g.user.id)
    thread = Thread.query.get_or_404(thread_id)
    
    # validation
    user_threads = db.session.query(UserThread).filter_by(user_id=g.user.id).all()
    thread_ids = [thread.thread_id for thread in user_threads]
    threads = db.session.query(Thread).filter(Thread.id.in_(thread_ids)).all()

    if not threads or thread.id not in thread_ids:
        flash('Error: Access unauthorized.', 'success')    
        return redirect("/chats")

    form = TargetLanguageForm()
    form.target_language.choices = [(l.code, l.name) for l in user.languages]

    if form.validate_on_submit():  
        db.session.query(User).filter_by(
            id=user.id).update({'target_language':form.target_language.data})
        db.session.commit()
        return redirect(f'/chats/{thread_id}')

    flash('Error: Unable to update target language.', 'success')           
    return redirect(f'/chats/{thread_id}')

@app.route('/chats/new/<int:contact_id>', methods=["POST"])
def chats_new(contact_id):
    """Create a new chat thread"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    contact = User.query.get_or_404(contact_id)
    users_in_threads = [{'id':thread.id, 'users':thread.users} for thread in contact.threads]
    existing_thread = next((item for item in users_in_threads if g.user in item['users']), None)

    if existing_thread:
        return redirect(f'/chats/{existing_thread["id"]}')

    # #validation
    is_contacts = contact in g.user.contacts
    is_pending = Contact.contact_is_pending(g.user, contact)
    contact_pending = is_pending['user_pending'] or is_pending['contact_pending']

    if not is_contacts or contact_pending:
        flash(f'Error: Unable to chat with user ({contact.username}).', 'success')
        return redirect("/chats")
    
    #Create new chat
    new_thread = Thread(name=uuid.uuid4())
    new_thread.users.append(g.user)
    new_thread.users.append(contact)
    db.session.add(new_thread)

    db.session.commit()

    #Update chatting attr
    db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=contact.id).update({'is_chatting': True})
    db.session.query(Contact).filter_by(user_id=contact.id, 
        contact_id=g.user.id).update({'is_chatting': True})
    
    db.session.commit()

    return redirect(f"/chats/{new_thread.id}")

@app.route('/chats/<int:thread_id>', methods=["GET"])
def chats_join(thread_id):
    """Reeenter a chat thread"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
        
    thread = Thread.query.get_or_404(thread_id)
    is_contact_in_call = False
    contact = None

    user_threads = db.session.query(UserThread).filter_by(user_id=g.user.id).all()
    thread_ids = [thread.thread_id for thread in user_threads]
    threads = db.session.query(Thread).filter(Thread.id.in_(thread_ids)).all()

    if not threads:
        return redirect("/chats")

    for t in threads:
        for user in t.users:
            if user.id != g.user.id and t.id == thread_id:
                contact = User.query.get_or_404(user.id)

    if not contact:
        flash(f'Error: Unable to chat with user ({contact.username}).', 'success')
        return redirect("/chats")

    #validation
    in_contacts = contact in g.user.contacts
    is_chatting = Contact.contact_is_chatting(g.user, contact)
    is_pending = Contact.contact_is_pending(g.user, contact)
    contact_pending = is_pending['user_pending'] or is_pending['contact_pending']

    if not is_chatting or not in_contacts or contact_pending:
        return redirect("/chats")
    
    is_calling_user = Contact.contact_is_calling(g.user, contact)

    contact_threads = db.session.query(UserThread).filter_by(user_id=contact.id).all()

    contact_contacts = db.session.query(Contact).\
        filter(or_(Contact.user_id == contact.id, 
            Contact.contact_id == contact.id)).all()
    
    for co in contact_contacts:
        if co.is_calling:
            is_contact_in_call = True

    user = User.query.get_or_404(g.user.id)
    form = TargetLanguageForm(obj=user)

    form.target_language.choices = [(l.code, l.name) for l in user.languages]
    form.target_language.data = user.target_language

    for user_thread in user_threads:
        for contact_thread in contact_threads:
            if user_thread.thread_id == contact_thread.thread_id:
                return render_template('chats/new.html', 
                    thread=thread, thread_id=thread.id, threads=threads, 
                        current_user=g.user, contact=contact, form=form, 
                            is_contact_in_call=is_contact_in_call, 
                                is_calling_user=is_calling_user)
            
    return redirect("/chats")
        

##############################################################################
# Call routes:

@app.route('/calls', methods=["GET", "POST"])
def calls():
    """Show list of current user calls"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    search = request.args.get('q')
    
    _calls = []

    users_calls_ids = db.session.query(UserCall.call_id).filter_by(user_id=g.user.id).all()
    contact_ids = db.session.query(Contact.contact_id).filter_by(user_id=g.user.id).all()

    call_ids = db.session.query(Call.id).filter(Call.id.in_(users_calls_ids)).\
        order_by(asc('end_timestamp')).all()
    
    for id in contact_ids:
        _calls.append(db.session.query(Call).join(Call.users).filter(
            Call.id.in_(call_ids), User.id == id).order_by(desc('end_timestamp')).first())

    if not search:
        calls = _calls
    else:
        calls = [call for call in _calls if call.users.filter(
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%"))
        ).all()]

    return render_template('calls/list.html', datetime=datetime, 
        relativedelta=relativedelta, timedelta=timedelta, calls=calls, 
        current_user=g.user)

@app.route('/calls/new/<int:contact_id>', methods=["POST"])
def call_new(contact_id):
    """Create a new call room"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    contact = User.query.get_or_404(contact_id)
    is_pending = Contact.contact_is_pending(g.user, contact)
    contact_pending = is_pending['user_pending'] or is_pending['contact_pending']

    if contact not in g.user.contacts or contact_pending:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/calls")

    is_calling = Contact.contact_is_calling(g.user, contact)

    if is_calling:
        user_in_calls = [{'id':call.id, 'users':call.users} for call in contact.calls]
        existing_call = next((item for item in user_in_calls if g.user in item['users']), None)

        if existing_call:
            _call = Call.query.get_or_404(existing_call['id'])

            if g.user in _call.users and _call.end_timestamp == None:
                return redirect(f"/calls/{existing_call['id']}")
        
    contact_calls = db.session.query(UserCall).filter_by(user_id=contact.id).all()
    call_ids = [call.call_id for call in contact_calls]
    calls = db.session.query(Call).filter(Call.id.in_(call_ids)).all()

    for call in calls:
        if g.user in call.users and call.end_timestamp == None:
            return redirect(f"/calls/{call.id}")
        if call.in_call:
            flash(f'Error: User ({contact.username}) is currently in call.', 'success')
            return redirect("/calls")
        
    #Create new call
    call = Call(room_id=uuid.uuid4(), author_id=g.user.id)
    call.users.append(g.user)
    call.users.append(contact)
    db.session.add(call)

    db.session.commit()

    #Update calling attr
    db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=contact.id).update({'is_calling': True})

    db.session.commit()

    return redirect(f"/calls/{call.id}")

@app.route('/calls/info/<int:user_id>', methods=["GET", "POST"])
def call_info(user_id):
    """Video calls details/history"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    contact = User.query.get_or_404(user_id)

    if contact not in g.user.contacts:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/calls")
    
    _calls = []
    in_calls = False
    is_contact_in_call = False

    search = request.args.get('q')

    users_calls = db.session.query(UserCall).filter_by(user_id=g.user.id).all()
    users_calls_ids = [call.call_id for call in users_calls]
    contact_ids = db.session.query(Contact.contact_id).filter_by(user_id=g.user.id).all()

    all_calls = db.session.query(Call).filter(Call.id.in_(users_calls_ids)).all()
    call_ids = db.session.query(Call.id).filter(Call.id.in_(users_calls_ids)).\
        order_by(asc('end_timestamp')).all()
    
    for call in all_calls:
        if contact in call.users:
            in_calls = True

    if not in_calls:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/calls")
    
    for id in contact_ids:
        _calls.append(db.session.query(Call).join(Call.users).filter(
            Call.id.in_(call_ids), User.id == id).order_by(desc('end_timestamp')).first())

    if not search:
        calls = _calls
    else:
        calls = [call for call in _calls if call.users.filter(
            User.username.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%") |
            User.country.has(
                Country.name.ilike(f"%{search}%"))
        ).all()]


    is_calling_user = Contact.contact_is_calling(g.user, contact)

    contact_calls = db.session.query(Call).join(Call.users).filter(
        Call.id.in_(users_calls_ids), User.id == contact.id).\
            order_by(desc('end_timestamp')).all()
    
    contact_contacts = db.session.query(Contact).\
        filter(or_(Contact.user_id == contact.id, 
            Contact.contact_id == contact.id)).all()
    
    for co in contact_contacts:
        if co.is_calling:
            is_contact_in_call = True
    
    return render_template('calls/show-caller.html', datetime=datetime, 
        relativedelta=relativedelta, timedelta=timedelta, calls=calls, 
        current_user=g.user, contact=contact, contact_calls=contact_calls, 
        is_contact_in_call=is_contact_in_call, is_calling_user=is_calling_user)

@app.route('/calls/<int:call_id>', methods=["GET", "POST"])
def call_join(call_id):
    """Join video call"""

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")
    
    call = Call.query.get_or_404(call_id)

    if g.user not in call.users:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/calls")

    if call.end_timestamp:
        contact = [user for user in call.users if user.id != g.user.id]
        flash(f'Error: Unable to reconnect this call.\
            Please request a new call from user ({contact[0].username})', 'success')
        return redirect("/calls")

    user_calls = db.session.query(UserCall).filter_by(user_id=g.user.id).all()
    call_ids = [call.call_id for call in user_calls]
    calls = db.session.query(Call).filter(Call.id.in_(call_ids)).all()

    if not calls:
        return redirect("/calls")

    for c in calls:
        for user in c.users:
            if user.id != g.user.id and c.id == call_id:
                contact = User.query.get_or_404(user.id)

    #Update calling attr
    db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=contact.id).update({'is_calling': True})
    
    db.session.commit()

    return render_template('calls/new.html', 
        calls=calls, call=call, current_user=g.user, contact=contact)

@app.route('/calls/<int:call_id>/close', methods=["POST"])
def call_close(call_id):

    if not g.user:
        flash('Error: Access unauthorized.', 'success')
        return redirect("/login")

    call = Call.query.get_or_404(call_id)

    if not call:
        return redirect("/calls")
    
    if g.user not in call.users:
        flash('Error: Access unauthorized.', 'success')
        return redirect(f"/calls")

    user_calls = db.session.query(UserCall).filter_by(user_id=g.user.id).all()
    call_ids = [call.call_id for call in user_calls]
    calls = db.session.query(Call).filter(Call.id.in_(call_ids)).all()

    for c in calls:
        for user in c.users:
            if user.id != g.user.id and c.id == call_id:
                contact = User.query.get_or_404(user.id)

    if contact not in g.user.contacts:
        return redirect("/calls")

    db.session.query(Contact).filter_by(user_id=g.user.id, 
        contact_id=contact.id).update({'is_calling': False})
    db.session.commit()
    
    contact_calling = db.session.query(Contact).\
        filter_by(user_id=contact.id, contact_id=g.user.id).\
        first()
    
    if not contact_calling.is_calling:
        call.in_call = False
        call.end_timestamp = datetime.now()
        db.session.commit()

    return redirect("/calls")


##############################################################################
# Socketio

@sio.event
def connect(sid, environ):
    print('Client connected', sid)

@sio.event
def chat_message(sid, data):
    """Join thread and create new message"""

    sio.enter_room(sid, 'chat_users')

    data = json.loads(data)
    thread = Thread.query.get(data['thread_id'])
    room = data['thread_room']
    message = data['message']
    current_user = User.query.get_or_404(data['current_user_id'])
    user = User.query.get_or_404(data['user_id'])

    result = translate_text(user.target_language, message)
    translated_language = Language.query.get(user.target_language)
    current_user_language = Language.query.get(current_user.target_language)

    message = Message(
        thread_id=thread.id, 
        author_id=current_user.id,
        recipient_id=user.id,
        message_language=current_user_language.name,
        message_text=data['message'],
        translated_language=translated_language.name,
        translated_text=html2text.html2text(result['translatedText']),
        timestamp=datetime.now()
    )

    if not thread or thread.name != room:
        return

    thread.messages.append(message)
    db.session.commit()

    chat_data = {
        'thread_id': thread.id,
        'message_language': message.message_language,
        'message_text': message.message_text,
        'translated_language': message.translated_language,
        'translated_text': message.translated_text,
        'message_time': message.timestamp.strftime("%m/%d/%Y, %H:%M:%S"),
        'message_author_id': current_user.id,
        'user_class_color': current_user.class_color,
        'user_first_name': current_user.first_name,
        'user_last_name': current_user.last_name,
    }

    sio.emit('chat', chat_data)

@sio.event
def message(sid, message):

    data_type = message['type']

    if data_type == 'candidate':

        data = message['data']
        sio.save_session(sid, {
            'call_id': data['call_id'],
            'room_id': data['room_id'],
            'contact_id': data['contact_id'],
            'current_user_id': data['current_user_id']
        })
        Call.update_call(data_type, data)

    if data_type == 'close':
        data = message['data']
        Call.update_call(data_type, data)
        sio.disconnect(sid)
        pass
        
    sio.emit('message', message, skip_sid=sid)

@sio.on('disconnect')
def disconnect(sid):

    sio_session = sio.get_session(sid)

    if(sio_session):

        call_id = sio_session['call_id']
        room_id = sio_session['room_id']
        contact_id = sio_session['contact_id']
        current_user_id = sio_session['current_user_id']

        call = Call.query.get_or_404(call_id)

        if call.in_call:
            data = {
                'call_id': call_id,
                'room_id': room_id,
                'contact_id': contact_id,
                'current_user_id': current_user_id
            }
            Call.update_call('close', data)
        
    print('Client diconnected')
    sio.disconnect(sid)


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req


##############################################################################
# Run application / server

# python-socketio server example
# https://github.com/miguelgrinberg/python-socketio

if __name__ == '__main__':
    if sio.async_mode == 'threading':
        # deploy with Werkzeug
        app.run(threaded=True)
    elif sio.async_mode == 'eventlet':
        # deploy with eventlet
        import eventlet
        import eventlet.wsgi
        eventlet.wsgi.server(eventlet.listen(('', 80)), app)
    elif sio.async_mode == 'gevent':
        # deploy with gevent
        from gevent import pywsgi
        try:
            from geventwebsocket.handler import WebSocketHandler
            websocket = True
        except ImportError:
            websocket = False
        if websocket:
            pywsgi.WSGIServer(('', 80), app,
                              handler_class=WebSocketHandler).serve_forever()
        else:
            pywsgi.WSGIServer(('', 80), app).serve_forever()
    else:
        print('Unknown async_mode: ' + sio.async_mode)
