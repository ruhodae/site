import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'change_this_secret')

DATABASE_URL = "postgresql://neondb_owner:npg_PLc2emlNfvD0@ep-jolly-tooth-a2raqljd-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"

@app.context_processor
def inject_user():
    return {
        'logged_in': 'user_id' in session,
        'username': session.get('username', '')
    }
    
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES site_users(id) ON DELETE CASCADE,
            full_name TEXT,
            address TEXT,
            passport_file TEXT,
            verification_status TEXT NOT NULL DEFAULT 'pending'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES site_users(id) ON DELETE CASCADE,
            name TEXT,
            address TEXT,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'Новое',
            date DATE DEFAULT CURRENT_DATE,
            priority TEXT DEFAULT 'Нормальный',
            tags TEXT DEFAULT ''
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS housing_stock (
            id SERIAL PRIMARY KEY,
            address TEXT NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/')
def home():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, content, created_at, file_link, media_link "
        "FROM news ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    news = [(n_id,title,content,(created_at + timedelta(hours=5)).strftime('%Y-%m-%d %H:%M'),file_link,media_link)
        for n_id, title, content, created_at, file_link, media_link in rows
    ]
    return render_template('index.html', news=news)
@app.route('/schedule')
def schedule(): return render_template('schedule.html')
@app.route('/housing')
def housing():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT address FROM housing_stock ORDER BY id")
    houses = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return render_template('housing.html', houses=houses)
@app.route('/contacts')
def contacts(): return render_template('contacts.html')
@app.route('/tariffs')
def tariffs(): return render_template('tariffs.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']; email = request.form['email']
        pwd = generate_password_hash(request.form['password'])
        conn = get_conn(); cur = conn.cursor()
        try:
            cur.execute("INSERT INTO site_users (username, email, password) VALUES (%s, %s, %s)", (uname, email, pwd))
            conn.commit(); flash('Регистрация прошла успешно!', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback(); flash('Пользователь уже существует.', 'danger')
        finally:
            cur.close(); conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']; pwd = request.form['password']
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id, password FROM site_users WHERE username=%s", (uname,))
        user = cur.fetchone(); cur.close(); conn.close()
        if user and check_password_hash(user[1], pwd):
            session['user_id'], session['username'] = user[0], uname
            flash('Вы вошли!', 'success'); return redirect(url_for('home'))
        flash('Неверный логин или пароль.', 'danger')
    return render_template('login.html')

@app.route('/login_gosuslugi')
def login_gosuslugi():
    return redirect('https://www.gosuslugi.ru')

@app.route('/logout')
def logout():
    session.clear(); flash('Вы вышли.', 'info'); return redirect(url_for('home'))

@app.route('/send_request', methods=['GET', 'POST'])
def send_request():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите.', 'danger')
        return redirect(url_for('login'))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT verification_status FROM user_profiles WHERE user_id = %s",(session['user_id'],))
    row = cur.fetchone()
    cur.close()
    conn.close()

    status = row[0] if row else None
    if status != 'verified':
        flash('Отправка обращений доступна только верифицированным пользователям.', 'danger')
        return redirect(url_for('account'))

    if request.method == 'POST':
        msg = request.form['message']
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT full_name, address FROM user_profiles WHERE user_id=%s",(session['user_id'],))
        name, addr = cur.fetchone() or ('', '')
        cur.execute("INSERT INTO requests (user_id, name, address, message, date) ""VALUES (%s, %s, %s, %s, CURRENT_DATE)",(session['user_id'], name, addr, msg))
        conn.commit()
        cur.close()
        conn.close()
        
        flash('Ваше обращение отправлено.', 'success')
        return redirect(url_for('account'))
        
    return render_template('send_request.html')

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' not in session:
        flash('Сначала войдите в систему.', 'warning')
        return redirect(url_for('login'))

    uid = session['user_id']
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""SELECT full_name, address, passport_file, verification_status FROM user_profiles WHERE user_id = %s""", (uid,))
    profile = cur.fetchone() or ('', '', None, 'pending')

    if request.method == 'POST' and request.form.get('action') == 'update_profile':
        full_name = request.form['full_name'].strip()
        address   = request.form['address'].strip()
        file      = request.files.get('passport_file')
        filename  = None

        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_dir = os.path.join('static', 'uploads', str(uid))
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))

        if any(profile[:2]):
            cur.execute("""UPDATE user_profiles SET full_name=%s, address=%s,passport_file=%s,verification_status='pending'WHERE user_id=%s""", (full_name, address, filename or profile[2], uid))
        else:
            cur.execute("""INSERT INTO user_profiles(user_id, full_name, address, passport_file)VALUES (%s, %s, %s, %s)""", (uid, full_name, address, filename))
        conn.commit()
        flash('Данные сохранены и отправлены на проверку.', 'success')
        return redirect(url_for('account'))

    cur.execute("""SELECT name, address, message, status, date FROM requests WHERE user_id = %s ORDER BY date DESC""", (uid,))
    user_requests = cur.fetchall()

    pending_users = []
    if session.get('username') == 'Admin':
        cur.execute("""SELECT up.id AS profile_id,up.user_id AS uid,su.username,up.full_name,up.passport_file FROM user_profiles up JOIN site_users su ON up.user_id = su.id WHERE up.verification_status = 'pending' AND up.passport_file IS NOT NULL""")
        pending_users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
      'account.html',
      profile=profile,
      user_requests=user_requests,
      pending_users=pending_users
    )

@app.route('/verify_user/<int:pid>', methods=['POST'])
def verify_user(pid):
    if session.get('username') != 'Admin':
        flash('Нет прав доступа.', 'danger')
        return redirect(url_for('home'))

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("UPDATE user_profiles SET verification_status='verified' WHERE id = %s",(pid,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Пользователь верифицирован.', 'info')
    return redirect(url_for('account'))

@app.route('/reject_user/<int:pid>', methods=['POST'])
def reject_user(pid):
    if session.get('username') != 'Admin':
        flash('Нет прав доступа.', 'danger')
        return redirect(url_for('home'))

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("UPDATE user_profiles SET verification_status='rejected', passport_file = NULL WHERE id = %s",(pid,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Заявка отклонена. Пользователь может загрузить документы повторно.', 'danger')
    return redirect(url_for('account'))

@app.route('/add_news', methods=['GET', 'POST'])
def add_news():
    if session.get('username') != 'Admin':
        flash('Нет прав доступа.', 'danger')
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        file_link = None
        if 'file' in request.files and request.files['file'].filename:
            f = request.files['file']
            fn = secure_filename(f.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            f.save(path)
            file_link = path
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

@app.route('/edit_news/<int:nid>', methods=['GET','POST'])
def edit_news(nid):
    if session.get('username') != 'Admin':
        return redirect(url_for('home'))
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    if request.method == 'POST':
        title      = request.form.get('title')
        content    = request.form.get('content')
        media_link = request.form.get('media_link') or None

        if request.form.get('remove_file'):
            file_link = None
        else:
            f = request.files.get('file')
            if f and f.filename:
                fn   = secure_filename(f.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
                f.save(path)
                file_link = path
            else:
                cur.execute("SELECT file_link FROM news WHERE id = %s",(nid,))
                file_link = cur.fetchone()[0]

        cur.execute("""UPDATE news SET title = %s, content = %s, file_link  = %s, media_link = %s WHERE id = %s""",(title, content, file_link, media_link, nid))
        conn.commit()
        cur.close()
        conn.close()

        flash('Новость обновлена.', 'success')
        return redirect(url_for('home'))

    cur.execute("SELECT title, content, file_link, media_link " "FROM news WHERE id = %s",(nid,))
    news_item = cur.fetchone()
    cur.close()
    conn.close()

    return render_template('edit_news.html',news=news_item,nid=nid)

@app.route('/delete_news/<int:nid>', methods=['POST'])
def delete_news(nid):
    if session.get('username') != 'Admin':
        flash('Нет прав доступа.', 'danger')
        return redirect(url_for('home'))
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("DELETE FROM news WHERE id=%s", (nid,))
    conn.commit(); cur.close(); conn.close()
    flash('Новость удалена.', 'info')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)