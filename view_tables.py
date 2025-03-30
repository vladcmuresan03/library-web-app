import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

def view_table_data(table_name):
    print(f"Contents of table: {table_name}")
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

view_table_data("users")
view_table_data("books")
view_table_data("reservations")

conn.close()