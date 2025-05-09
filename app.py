import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change_this_secret')

DATABASE_URL = os.getenv('DATABASE_URL') or (
    "postgresql://neondb_owner:npg_PLc2emlNfvD0@"
    "ep-jolly-tooth-a2raqljd-pooler.eu-central-1.aws.neon.tech/"
    "neondb?sslmode=require"
)

# Инициализация схемы БД
def init_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS site_users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            file_link TEXT,
            media_link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/')
def home():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute(
        "SELECT title, content, created_at, file_link, media_link "
        "FROM news ORDER BY created_at DESC LIMIT 5"
    )
    raw_news = cur.fetchall()
    cur.close(); conn.close()

    news = []
    for title, content, created_at, file_link, media_link in raw_news:
        local_dt = created_at + timedelta(hours=5)
        news.append((title, content, local_dt.strftime('%Y-%m-%d %H:%M'), file_link, media_link))

    return render_template('index.html', news=news)

@app.route('/schedule')
def schedule():
    return render_template('schedule.html')

@app.route('/housing')
def housing():
    houses = [
        "21-й мкр д.1", "21-й мкр д.2", "21-й мкр д.3", "21-й мкр д.4/5",
        "21-й мкр д.6", "21-й мкр д.7", "21-й мкр д.8", "21-й мкр д.9",
        "21-й мкр д.10"
    ]
    return render_template('housing.html', houses=houses)

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/tariffs')
def tariffs():
    return render_template('tariffs.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed = generate_password_hash(password)

        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO site_users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed)
            )
            conn.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError as e:
            conn.rollback()
            if 'site_users_email_key' in str(e):
                flash('Пользователь с таким email уже существует.', 'danger')
            elif 'site_users_username_key' in str(e):
                flash('Пользователь с таким именем уже существует.', 'danger')
            else:
                flash('Ошибка при регистрации.', 'danger')
        finally:
            cur.close(); conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password FROM site_users WHERE username=%s", (username,)
        )
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли.', 'info')
    return redirect(url_for('home'))

UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if not file or file.filename == '': return 'No file', 400
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    return filename

@app.route('/add_news', methods=['GET', 'POST'])
def add_news():
    if 'username' not in session or session['username'] != 'Admin':
        flash('Нет прав доступа.', 'danger')
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        file_link = None
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            file_link = f"/{path}"
        media_link = request.form.get('media_link')

        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO news (title, content, file_link, media_link) VALUES (%s, %s, %s, %s)",
            (title, content, file_link, media_link)
        )
        conn.commit(); cur.close(); conn.close()
        flash('Новость добавлена!', 'success')
        return redirect(url_for('home'))
    return render_template('add_news.html')

if __name__ == '__main__': app.run(debug=True)
