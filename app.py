from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key"  # session management
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# database connection function
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # return rows as dictionaries
    return conn


@app.route('/')
def index():
    if 'user_id' in session:
        # if the user is logged in, redirect to view their profile options
        return redirect(url_for('dashboard'))

    # if not logged in, show options to login or create an account
    return render_template('index.html')


@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)  # hashing the password

        conn = get_db_connection()
        cursor = conn.cursor()
        # insert the new user into the users table
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, hashed_password, 'user')  # default role for new users
        )
        conn.commit()

        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_id = cursor.fetchone()[0]

        conn.close()

        # automatically log the user in after creating the account
        session['user_id'] = user_id
        session['username'] = username
        session['role'] = 'user'  # default role for new users

        return redirect(url_for('view_books'))  # redirect to the books page after login

    return render_template('create_account.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('view_books'))
        else:
            return render_template('login.html', error="Invalid username or password.")

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('dashboard.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/view_books')
def view_books():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # connect to the db
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # check if the user is the librarian
    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    user_role = cursor.fetchone()
    is_librarian = (user_role and user_role['role'] == 'librarian')

    # fetch books
    cursor.execute("SELECT * FROM books ORDER BY is_available DESC")
    books = cursor.fetchall()
    conn.close()

    # path where images are stored
    image_folder = 'static/images/'

    books_with_images = []
    for book in books:
        book_data = dict(book)
        book_id = book_data['id']

        # get the correct image filename
        image_filename = f"{book_id}.jpg"
        if not os.path.exists(os.path.join(image_folder, image_filename)):
            image_filename = f"{book_id}.png"
        if not os.path.exists(os.path.join(image_folder, image_filename)):
            image_filename = 'default_book.png'

        book_data['image_filename'] = image_filename
        books_with_images.append(book_data)

    return render_template('view_books.html', books=books_with_images, is_librarian=is_librarian)


@app.route('/book_details/<int:book_id>')
def book_details(book_id):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # this allows access by column names like a dictionary
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM books WHERE id = ?', (book_id,))
    book = cursor.fetchone()
    conn.close()

    if book is None:
        return "Book not found", 404  # Handle case where the book is not found

    # possible image paths based on book_id
    img_paths = [
        f'static/images/{book_id}.png',
        f'static/images/{book_id}.jpg',
        'static/images/default_book.png'
    ]

    # check if one of the image paths exists
    book_image = None
    for path in img_paths:
        if os.path.exists(path):
            book_image = path
            break

    return render_template('book_details.html', book=book, book_image=book_image)


def parse_reservation_date(date_str):
    try:
        # try 'YYYY-MM-DD HH:MM:SS' format
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        # also try parsing with 'YYYY-MM-DDTHH:MM:SS' format
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M')


@app.route('/your_books', methods=['GET', 'POST'])
def your_books():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # fetch user role (librarian or user)
    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    user_role = cursor.fetchone()['role']

    reservations = []
    reservation_info = []
    selected_reservation = None

    # if librarian, they can see all reservations
    if user_role == 'librarian':
        if request.method == 'POST' and 'search_id' in request.form:
            # search for a reservation by ID
            search_id = request.form.get('search_id')
            cursor.execute("""
                SELECT 
                    r.id AS reservation_id,
                    r.user_id,
                    r.book_id,
                    r.reservation_date,
                    r.return_date,
                    r.is_returned
                FROM reservations r
                WHERE r.id = ?
            """, (search_id,))
            selected_reservation = cursor.fetchone()

        # get all reservations for the librarian
        cursor.execute("""
            SELECT 
                r.id AS reservation_id,
                r.user_id,
                r.book_id,
                r.reservation_date,
                r.return_date,
                r.is_returned,
                u.username AS user_name
            FROM reservations r
            JOIN users u on r.user_id = u.id
        """)
        reservations = cursor.fetchall()

    # if user, only show their own reservations
    else:
        cursor.execute("""
            SELECT 
                r.id AS reservation_id,   -- data from reservations table
                r.user_id,
                r.book_id,
                r.reservation_date,
                r.return_date,
                r.is_returned
            FROM reservations r
            WHERE r.user_id = ?
        """, (user_id,))
        reservations = cursor.fetchall()

    # process reservation data (overdue check, reservation period formatting)
    today = datetime.today()
    for reservation in reservations:
        reservation_date = parse_reservation_date(reservation['reservation_date'])

        # if return_date is not None, use it directly; else, make it two weeks after the reservation date
        if reservation['return_date']:
            reservation_period_end = parse_reservation_date(reservation['return_date'])
        else:
            reservation_period_end = reservation_date + timedelta(weeks=2)

        is_returned = reservation['is_returned'] == 1
        overdue = today > reservation_period_end and not is_returned

        cursor.execute('SELECT title FROM books WHERE id = ?', (reservation['book_id'],))
        book = cursor.fetchone()

        cursor.execute('SELECT username from users where id = ?', (reservation['user_id'],))
        user = cursor.fetchone()

        reservation_info.append({
            'reservation_id': reservation['reservation_id'],
            'book_id': reservation['book_id'],
            'title': book['title'] if book else 'Unknown',
            'reservation_period': f"{reservation_date.strftime('%Y-%m-%d')} - {reservation_period_end.strftime('%Y-%m-%d')}",
            'is_returned': is_returned,
            'overdue': overdue,
            'user_id': reservation['user_id'],
            'username': user['username']
        })

    cursor.close()
    conn.close()

    return render_template(
        'your_books.html',
        reservation_info=reservation_info,
        selected_reservation=selected_reservation,
        is_librarian=(user_role == 'librarian')
    )



@app.route('/search_reservation', methods=['POST'])
def search_reservation():
    if 'user_id' not in session or session['role'] != 'librarian':
        return redirect(url_for('login'))

    reservation_id = request.form.get('search_id')
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            r.id AS reservation_id,
            r.user_id,
            b.title,
            r.reservation_date,
            r.return_date
        FROM reservations r
        JOIN books b ON r.book_id = b.id
        WHERE r.id = ?
    """, (reservation_id,))
    selected_reservation = cursor.fetchone()
    conn.close()
    # error if no reservation found
    if not selected_reservation:
        flash('Reservation not found', 'error')
        return redirect(url_for('your_books'))

    return render_template('your_books.html', selected_reservation=selected_reservation, is_librarian=True)


@app.route('/update_reservation', methods=['POST'])
def update_reservation():
    if 'user_id' not in session or session['role'] != 'librarian':
        return redirect(url_for('login'))

    reservation_id = request.form.get('reservation_id')
    new_start_date = request.form.get('reservation_date')
    new_end_date = request.form.get('return_date')
    returned_status = int(request.form.get('is_returned'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # adding a new reservation to the db
    cursor.execute("""
        UPDATE reservations
        SET reservation_date = ?, return_date = ?, is_returned = ?
        WHERE id = ?
    """, (new_start_date, new_end_date, returned_status, reservation_id))
    conn.commit()
    conn.close()

    flash('Reservation updated successfully!', 'success')
    return redirect(url_for('your_books'))


@app.route('/change_username', methods=['GET', 'POST'])
def change_username():
    if request.method == 'POST':
        new_username = request.form.get('new_username')

        if not new_username:
            flash('Please provide a valid username!', 'error')
            return redirect(url_for('change_username'))

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # check if the username is already taken
            cursor.execute("SELECT id FROM users WHERE username = ?", (new_username,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('This username is already taken. Please choose another one.', 'error')
                return redirect(url_for('change_username'))

            # if username is available, go on
            cursor.execute("UPDATE users SET username = ? WHERE id = ?",
                           (new_username, session['user_id']))
            conn.commit()

        # update session data!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        session['username'] = new_username
        flash('Username changed successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_username.html')


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            # hash the new password
            hashed_password = generate_password_hash(new_password)

            # update the hashed password in the session and in the database
            session['password'] = hashed_password

            # update the database with the hashed password
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, session['user_id']))
            conn.commit()
            conn.close()

            flash('Password changed successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Please provide a valid password!', 'error')
    return render_template('change_password.html')


@app.route('/delete_account', methods=['POST'])
def delete_account():
    # check if the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # delete the user's account from the database
    conn = get_db_connection()
    cursor = conn.cursor()
    print(f"Session user_id before deletion: {session.get('user_id')}")
    print(f"Session username before deletion: {session.get('username')}")
    cursor.execute("DELETE FROM users WHERE id = ?", (session['user_id'],))
    conn.commit()
    conn.close()

    # log the user out by clearing the session
    session.clear()

    flash('Your account has been deleted successfully!', 'success')
    return redirect(url_for('index'))  # redirect to the home page (login)


@app.route('/delete_reservation/<int:reservation_id>', methods=['GET'])
def delete_reservation(reservation_id):
    if 'user_id' not in session or session['role'] != 'librarian':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('your_books'))

    conn = get_db_connection()
    cursor = conn.cursor()
    # delete a reservation by id
    cursor.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
    conn.close()

    flash('Reservation deleted successfully!', 'success')
    return redirect(url_for('your_books'))


@app.route('/create_reservation', methods=['GET', 'POST'])
def create_reservation():
    if 'user_id' not in session or session['role'] != 'librarian':
        flash('Unauthorized access!', 'error')
        return redirect(url_for('your_books'))

    if request.method == 'POST':
        user_id = request.form['user_id']
        book_id = request.form['book_id']
        reservation_date = request.form['reservation_date']
        return_date = request.form.get('return_date', None)  # optional field

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reservations (user_id, book_id, reservation_date, return_date, is_returned)
            VALUES (?, ?, ?, ?, 0)
        """, (user_id, book_id, reservation_date, return_date))

        conn.commit()
        conn.close()

        flash('Reservation created successfully!', 'success')
        return redirect(url_for('your_books'))

    return render_template('create_reservation.html')


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']
        picture = request.files.get('picture')

        if not title or not author or not genre:
            flash('All fields except the picture are required.', 'error')
            return redirect(request.url)

        # insert book into the database
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO books (title, author, genre, is_available)
            VALUES (?, ?, ?, ?)
        ''', (title, author, genre, 1))
        conn.commit()

        # get the book ID (the last inserted row)
        book_id = cursor.lastrowid

        # handle picture upload
        if picture and allowed_file(picture.filename):
            ext = picture.filename.rsplit('.', 1)[1].lower()
            filename = f"{book_id}.{ext}"  # Rename to book_id.jpg/png
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            picture.save(filepath)

        conn.close()

        flash('Book added successfully!', 'success')
        return redirect(url_for('view_books'))

    return render_template('add_book.html')


@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if 'user_id' not in session or session['role'] != 'librarian':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # fetch the book details
    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()
    conn.close()

    if not book:
        flash("Book not found.", "error")
        return redirect(url_for('view_books'))

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        genre = request.form['genre']
        availability = request.form['availability']
        picture = request.files.get('picture')

        # Update book details
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE books SET title = ?, author = ?, genre = ?, is_available = ? WHERE id = ?
        ''', (title, author, genre, availability, book_id))
        conn.commit()

        if picture and allowed_file(picture.filename):
            # delete the old image (it can be only a .jpg or a .png)
            old_image = os.path.join(app.config['UPLOAD_FOLDER'], f"{book_id}.jpg")
            if os.path.exists(old_image):
                os.remove(old_image)
            old_image = os.path.join(app.config['UPLOAD_FOLDER'], f"{book_id}.png")
            if os.path.exists(old_image):
                os.remove(old_image)

            # save the new picture
            ext = picture.filename.rsplit('.', 1)[1].lower()
            filename = f"{book_id}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            picture.save(filepath)

        conn.close()

        flash('Book details updated successfully!', 'success')
        return redirect(url_for('book_details', book_id=book_id))

    return render_template('edit_book.html', book=book)


@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if 'user_id' not in session or session['role'] != 'librarian':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    book = cursor.fetchone()

    if book:
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()

        # delete the old image file (if it exists)
        image_file_jpg = os.path.join(app.config['UPLOAD_FOLDER'], f"{book_id}.jpg")
        image_file_png = os.path.join(app.config['UPLOAD_FOLDER'], f"{book_id}.png")

        if os.path.exists(image_file_jpg):
            print(f"Removing {image_file_jpg}")
            os.remove(image_file_jpg)
        elif os.path.exists(image_file_png):
            print(f"Removing {image_file_png}")
            os.remove(image_file_png)

        flash('Book deleted successfully!', 'success')
    else:
        flash('Book not found.', 'error')

    conn.close()

    return redirect(url_for('view_books'))


if __name__ == '__main__':
    app.run(debug=True)