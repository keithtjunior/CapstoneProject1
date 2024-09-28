"""Models for Feedback"""

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

from datetime import datetime
import random

bcrypt = Bcrypt()
db = SQLAlchemy()


def connect_db(app):
    """Connect to database"""
    db.app = app
    db.init_app(app)

def randcls():
    """Random class selector for user avatar"""
    cls = [
        'bg-primary text-white',
        'bg-secondary text-white',
        'bg-success text-white',
        'bg-danger text-white',
        'bg-warning text-dark',
        'bg-info text-white',
        'bg-light text-dark',
        'bg-dark text-white',
        'bg-white text-dark',
    ]
    return random.choice(cls)
	

class User(db.Model):
    """User"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(320), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    city = db.Column(db.String(50))
    class_color = db.Column(db.Text, nullable=False)
    is_online = db.Column(db.Boolean, default=False)
    city = db.Column(db.String(50), default='N/A')
    country_iso = db.Column(db.String(2), db.ForeignKey('countries.iso'), nullable=False)
    country = db.relationship('Country')
    target_language = db.Column(db.Text)
    languages = db.relationship('Language', 
        secondary='users_languages', 
        backref='users',
        lazy='dynamic'
    )
    contacts = db.relationship('User', 
        secondary = 'contacts', 
        primaryjoin = ('contacts.c.user_id == users.c.id'),
        secondaryjoin = ('contacts.c.contact_id == users.c.id'),
        backref = 'user_contacts',
        lazy='dynamic'
    )

    def __repr__(self):
        u = self
        return f'<User id={u.id} username={u.username} password={u.password} email={u.email} first_name={u.first_name} last_name={u.last_name} city={u.city} country={u.country} target_language={u.target_language} class_color={u.class_color} is_online={u.is_online}>'
    
    def get_full_name(self):
        """Return full name"""
        u = self
        return f"{u.first_name} {u.last_name}"
    
    full_name = property(fget=get_full_name)

    @classmethod
    def new_password(cls, password):
        return bcrypt.generate_password_hash(password).decode('UTF-8')
    
    @classmethod
    def signup(cls, first_name, last_name, username, email, city, country_iso, password):
        """Register new user"""

        hashed_pwd = bcrypt.generate_password_hash(password).decode('UTF-8')

        user = User(
            first_name=first_name.title(),
            last_name=last_name.title(),
            username=username,
            email=email,
            city=city,
            country_iso=country_iso,
            password=hashed_pwd,
            class_color=randcls()
        )

        db.session.add(user)
        return user

    @classmethod
    def authenticate(cls, username, password):
        """Authenticate user with `username` and `password`"""

        user = cls.query.filter_by(username=username).first()

        if user:
            is_auth = bcrypt.check_password_hash(user.password, password)
            if is_auth:
                return user

        return False

class Contact(db.Model):
    """Contact"""
    __tablename__ = 'contacts'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="cascade"), primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="cascade"), primary_key=True)
    is_pending = db.Column(db.Boolean, default=True)
    is_chatting = db.Column(db.Boolean, default=False)
    is_calling = db.Column(db.Boolean, default=False)

    def __repr__(self):
        c = self
        return f'<Contact user_id={c.user_id} contact_id={c.contact_id} is_pending={c.is_pending} is_chatting={c.is_chatting}>'
    
    @classmethod
    def contact_is_pending(cls, user, contact):
        """Confirm if user contact is pending"""

        user_pending = db.session.query(Contact).filter_by(
                        user_id=user.id, contact_id=contact.id).first()
        contact_pending = db.session.query(Contact).filter_by(
                        user_id=contact.id, contact_id=user.id).first()
        return {
            'user_pending': user_pending.is_pending, 
            'contact_pending': contact_pending.is_pending
        }
    
    @classmethod
    def contact_is_chatting(cls, user, contact):
        """Confirm if user contact is chatting"""

        user_chatting = db.session.query(Contact).filter_by(
            user_id=user.id, contact_id=contact.id).first()
        contact_chatting = db.session.query(Contact).filter_by(
            user_id=contact.id, contact_id=user.id).first()
        return user_chatting.is_chatting and contact_chatting.is_chatting
    
    @classmethod
    def contact_is_calling(cls, user, contact):
        """Confirm if user contact is video calling"""

        user_calling = db.session.query(Contact).filter_by(
            user_id=user.id, contact_id=contact.id).first()
        contact_calling = db.session.query(Contact).filter_by(
            user_id=contact.id, contact_id=user.id).first()
        return user_calling.is_calling or contact_calling.is_calling
    
class UserThread(db.Model):
    """UserThread"""
    __tablename__ = 'users_threads'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="cascade"), primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id', ondelete="cascade"), primary_key=True)
    
class Thread(db.Model):
    """Thread"""
    __tablename__ = "threads"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False)
    messages = db.relationship('Message', backref='thread', lazy=True)
    users = db.relationship('User', secondary='users_threads', lazy='dynamic',
        backref=db.backref('threads', lazy='dynamic'))
    
    def __repr__(self):
        t = self
        return f'<Thread id={t.id} name={t.name}>'

class Message(db.Model):
    """Message"""
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('threads.id'))
    author_id = db.Column(db.Integer)
    recipient_id = db.Column(db.Integer)
    message_text = db.Column(db.String(2048))
    message_language = db.Column(db.String(64))
    translated_text = db.Column(db.String(2048))
    translated_language = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, default=datetime.now())
    
    def __repr__(self):
        m = self
        return f'<Message id={m.id} thread_id={m.thread_id} author_id={m.author_id} recipient_id={m.recipient_id} message_text={m.message_text} translated_text={m.translated_text} timestamp={m.timestamp}>'
    
class UserCall(db.Model):
    """UserCall"""
    __tablename__ = 'users_calls'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="cascade"), primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('calls.id', ondelete="cascade"), primary_key=True)
    
class Call(db.Model):
    """Call"""
    __tablename__ = "calls"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(db.String(64), nullable=False)
    author_id = db.Column(db.Integer, default=None)
    recipient_id = db.Column(db.Integer, default=None)
    lobby_timestamp = db.Column(db.DateTime, default=datetime.now())
    start_timestamp = db.Column(db.DateTime, default=None, nullable=True)
    end_timestamp = db.Column(db.DateTime, default=None, nullable=True)
    in_call = db.Column(db.Boolean, default=True)
    users = db.relationship('User', secondary='users_calls', lazy='dynamic',
        backref=db.backref('calls', lazy='dynamic'))
    
    def __repr__(self):
        c = self
        return f'<Call id={c.id} room_id={c.room_id} author_id={c.author_id} recipient_id={c.recipient_id} lobby_timestamp={c.lobby_timestamp} start_timestamp={c.start_timestamp} end_timestamp={c.end_timestamp} in_call={c.in_call}>'
    
    @classmethod
    def update_call(cls, data_type, data):

        if data:
            call_id = data['call_id']
            room_id = data['room_id']
            contact_id = data['contact_id']
            current_user_id = data['current_user_id']

            if data_type == 'candidate':

                user = User.query.get_or_404(current_user_id)
                call = Call.query.get_or_404(call_id)

                db.session.query(Contact).filter_by(user_id=user.id, 
                    contact_id=contact_id).update({'is_calling': True})

                if not call.start_timestamp:
                    call.start_timestamp = datetime.now()
                    
                db.session.commit()

            if data_type == 'close':
                
                call = Call.query.get_or_404(call_id)

                db.session.query(Contact).filter_by(user_id=current_user_id, 
                    contact_id=contact_id).update({'is_calling': False})

                if not call.start_timestamp:
                    db.session.query(Contact).filter_by(user_id=contact_id, 
                    contact_id=current_user_id).update({'is_calling': False})

                if not call.end_timestamp:
                    call.end_timestamp = datetime.now()
                    call.in_call = False

                db.session.commit()

        return
    
class Country(db.Model):
    """Country"""
    __tablename__ = "countries"

    iso = db.Column(db.String(2), primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    users = db.relationship('User')

class Language(db.Model):
    """Language"""
    __tablename__ = "languages"

    code = db.Column(db.String(8), primary_key=True)
    name = db.Column(db.String(64), nullable=False)

class UserLanguages(db.Model):
    """UserLanguages"""
    __tablename__ = 'users_languages'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="cascade"), primary_key=True)
    language_code = db.Column(db.String(8), db.ForeignKey('languages.code', ondelete="cascade"), primary_key=True)