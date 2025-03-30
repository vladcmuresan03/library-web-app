import sqlite3

def add_books():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    books = [
        ('The Great Gatsby', 'F. Scott Fitzgerald', 'Novel', 5, 'default_book.png'),
        ('1984', 'George Orwell', 'Dystopian', 3, 'default_book.png'),
        ('To Kill a Mockingbird', 'Harper Lee', 'Fiction', 0, 'default_book.png'),
        ('The Catcher in the Rye', 'J.D. Salinger', 'Classic', 2, 'default_book.png'),
        ('Pride and Prejudice', 'Jane Austen', 'Romance', 7, 'default_book.png'),
        ('The Hobbit', 'J.R.R. Tolkien', 'Fantasy', 10, 'default_book.png'),
        ('Moby Dick', 'Herman Melville', 'Adventure', 0, 'default_book.png')
    ]

    cursor.executemany('''
        INSERT INTO books (title, author, genre, quantity, image)
        VALUES (?, ?, ?, ?, ?)
    ''', books)

    conn.commit()
    conn.close()
    print("Books added successfully with default image!")

if __name__ == '__main__':
    add_books()
