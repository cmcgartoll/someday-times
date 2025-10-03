import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, login_required, logout_user,
    current_user, UserMixin
)
from sqlalchemy import case, desc
from werkzeug.security import generate_password_hash, check_password_hash

from utils.metadata_utils import fetch_metadata

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'someday_times.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    url = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=True)
    publisher = db.Column(db.String(255), nullable=True)
    favicon_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    date_read = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('articles', lazy='dynamic'))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        url = request.form.get('url', '').strip()
        if not url:
            return redirect(url_for('index'))
        title, publisher, favicon = fetch_metadata(url)
        article = Article(
            user_id=current_user.id,
            url=url,
            title=title or url,
            publisher=publisher or '—',
            favicon_url=favicon,
        )
        db.session.add(article)
        db.session.commit()
        return redirect(url_for('index'))

    view = request.args.get('view', 'all')
    q = Article.query.filter_by(user_id=current_user.id)
    if view == 'unread':
        q = q.filter(Article.date_read.is_(None)).order_by(desc(Article.created_at))
    elif view == 'read':
        q = q.filter(Article.date_read.is_not(None)).order_by(desc(Article.date_read))
    else:
        q = q.order_by(
            case((Article.date_read.is_(None), 0), else_=1),
            desc(Article.date_read),
            desc(Article.created_at),
        )
    items = q.all()
    return render_template('index.html', items=items, view=view)


@app.post('/toggle/<int:article_id>')
@login_required
def toggle(article_id):
    a = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()
    if a.date_read is None:
        a.date_read = datetime.utcnow()
    else:
        a.date_read = None
    db.session.commit()
    return redirect(url_for('index', view=request.args.get('view', 'all')))


@app.post('/delete/<int:article_id>')
@login_required
def delete(article_id):
    a = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    return redirect(url_for('index', view=request.args.get('view', 'all')))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials', 'error')
    return render_template('auth.html', mode='login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password required', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('auth.html', mode='register')


@app.get('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.before_request
def ensure_db():
    with app.app_context():
        db.create_all()


if __name__ == '__main__':
    app.run(debug=True)
