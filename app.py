from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            file_link TEXT,
            media_link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Главная страница
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Получаем последние 5 новостей
    cursor.execute('SELECT title, content, created_at, file_link, media_link FROM news ORDER BY created_at DESC LIMIT 5')
    raw_news = cursor.fetchall()
    conn.close()

    # Преобразуем время с учетом смещения
    news = []
    for title, content, created_at, file_link, media_link in raw_news:
        created_at_utc = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        created_at_local = created_at_utc + timedelta(hours=5)  # +5 здесь добавил для окт времени
        news.append((title, content, created_at_local.strftime('%Y-%m-%d %H:%M'), file_link, media_link))

    return render_template('index.html', news=news)

# Режим работы
@app.route('/schedule')
def schedule():
    return render_template('schedule.html')

# Жилой фонд
@app.route('/housing')
def housing():
    # Список домов
    houses = [
        "21-й мкр д.1", "21-й мкр д.2", "21-й мкр д.3", "21-й мкр д.4/5", "21-й мкр д.6",
        "21-й мкр д.7", "21-й мкр д.8", "21-й мкр д.9", "21-й мкр д.10"
    ]
    return render_template('housing.html', houses=houses)

# Контакты
@app.route('/contacts')
def contacts():
    return render_template('contacts.html')


# Тарифы
@app.route('/tariffs')
def tariffs():
    return render_template('tariffs.html')

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']  # Получаем email из формы
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                           (username, email, hashed_password))
            conn.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.email" in str(e):
                flash('Пользователь с таким email уже существует.', 'danger')
            elif "UNIQUE constraint failed: users.username" in str(e):
                flash('Пользователь с таким именем уже существует.', 'danger')
            else:
                flash('Произошла ошибка при регистрации.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

# Авторизация
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):  # Убедитесь, что индекс правильный
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')

    return render_template('login.html')

# Выход
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('home'))


# Папка для загрузки файлов
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return filename  # Возвращаем имя файла для использования в базе данных

@app.route('/add_news', methods=['GET', 'POST'])
def add_news():
    if 'username' not in session or session['username'] != 'Admin':
        flash('У вас нет прав для доступа к этой странице.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        media_link = request.form.get('media_link')  # Получаем ссылку на медиафайл

        # Загрузка файла
        file_link = None
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                file_link = f"/{app.config['UPLOAD_FOLDER']}/{filename}"

        # Сохраняем новость в базе данных
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO news (title, content, file_link, media_link) VALUES (?, ?, ?, ?)',
                       (title, content, file_link, media_link))
        conn.commit()
        conn.close()

        flash('Новость успешно добавлена!', 'success')
        return redirect(url_for('home'))

    return render_template('add_news.html')
if __name__ == '__main__':
    app.run(debug=True)