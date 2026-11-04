import hashlib
import sqlite3
from datetime import datetime, timedelta

# ---------- DATABASE ----------

DB = ":memory:"
current_user = None
current_student_id = None
db_connection = None


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def setup():
    global db_connection

    # Close existing connection if re-initializing
    if db_connection is not None:
        db_connection.close()

    # Keep one connection open for the in-memory database
    db_connection = sqlite3.connect(DB)

    # Create users table with student_id column
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Create books table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            genre TEXT NOT NULL,
            quantity INTEGER NOT NULL
        )
    """)

    # Create borrowings table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS borrowings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower TEXT NOT NULL,
            book_id INTEGER NOT NULL,
            borrow_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            returned INTEGER DEFAULT 0
        )
    """)

    # Create audit table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT,
            details TEXT,
            time TEXT
        )
    """)

    # Create suggestions table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            suggestion TEXT,
            time TEXT
        )
    """)

    # Create default admin account if it doesn't exist
    user = db_connection.execute(
        "SELECT username FROM users WHERE username = ?", ("admin",)
    ).fetchone()

    if user is None:
        db_connection.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            ("admin", "00-0000-000000", hash_password("admin123")),
        )

    # Insert sample books if the inventory is empty
    count = db_connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    if count == 0:
        db_connection.executemany(
            """
            INSERT INTO books (title, author, genre, quantity)
            VALUES (?, ?, ?, ?)
        """,
            [
                ("Noli Me Tangere", "Jose Rizal", "Classic", 5),
                ("El Filibusterismo", "Jose Rizal", "Classic", 4),
                ("Python Basics", "John Smith", "Technology", 3),
                ("Harry Potter", "J.K. Rowling", "Fantasy", 4),
                ("Atomic Habits", "James Clear", "Self-help", 2),
            ],
        )

    db_connection.commit()


# ---------- AUDIT LOG ----------


def log_action(action, details=""):
    db_connection.execute(
        """
        INSERT INTO audit (username, action, details, time)
        VALUES (?, ?, ?, ?)
    """,
        (
            current_user or "SYSTEM",
            action,
            details,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    db_connection.commit()


# ---------- LOGIN AND LOGOUT ----------


def login():
    global current_user, current_student_id

    print("\n===== LIBRARY LOGIN =====")

    username = input("Username: ").strip()
    student_id = input("Student ID (e.g., 02-2627-013673): ").strip()
    password = input("Password: ")

    user = db_connection.execute(
        "SELECT password, student_id FROM users WHERE username = ?", (username,)
    ).fetchone()

    # Verify both the hashed password and the Student ID
    if user and user[0] == hash_password(password) and user[1] == student_id:
        current_user = username
        current_student_id = student_id

        log_action("LOGIN", f"Successful login (ID: {student_id})")

        print("\nLogin successful! Welcome,", username)
        return True

    log_action("FAILED LOGIN", f"Username: {username} | ID: {student_id}")

    print("Incorrect username, Student ID, or password.")
    return False


def logout():
    global current_user, current_student_id

    log_action("LOGOUT", "User logged out")

    print("Logged out successfully!")

    current_user = None
    current_student_id = None


# ---------- ABOUT LIBRARY ----------


def about_library():
    print("""
========================================
          ABOUT THE LIBRARY
========================================

Library Name: Community Learning Library

Mission:
To promote reading, education, and lifelong
learning through accessible books and
learning resources.

Services:
- Book borrowing and returning
- Book searching
- Library inventory management
- Reading recommendations
- User suggestions
- Activity monitoring

========================================
""")


# ---------- BOOK MANAGEMENT ----------


def view_books():
    books = db_connection.execute("SELECT * FROM books ORDER BY id").fetchall()

    print("\n========== BOOK INVENTORY ==========")

    if not books:
        print("No books available.")
        return

    for b in books:
        print(
            f"ID: {b[0]} | Title: {b[1]} | "
            f"Author: {b[2]} | Genre: {b[3]} | "
            f"Available: {b[4]}"
        )


def add_book():
    title = input("Book title: ").strip()
    author = input("Author: ").strip()
    genre = input("Genre: ").strip()

    if not title or not author or not genre:
        print("All fields are required.")
        return

    try:
        quantity = int(input("Quantity: "))

        if quantity < 1:
            print("Quantity must be at least 1.")
            return

    except ValueError:
        print("Please enter a valid number.")
        return

    db_connection.execute(
        """
        INSERT INTO books (title, author, genre, quantity)
        VALUES (?, ?, ?, ?)
    """,
        (title, author, genre, quantity),
    )

    db_connection.commit()

    log_action("ADD BOOK", title)

    print("Book added successfully!")


def search_books():
    keyword = input("Search title, author, or genre: ").strip()

    if not keyword:
        print("Please enter a search term.")
        return

    pattern = "%" + keyword + "%"

    books = db_connection.execute(
        """
        SELECT * FROM books
        WHERE title LIKE ?
           OR author LIKE ?
           OR genre LIKE ?
    """,
        (pattern, pattern, pattern),
    ).fetchall()

    if books:
        print("\n========== SEARCH RESULTS ==========")

        for b in books:
            print(
                f"ID: {b[0]} | Title: {b[1]} | "
                f"Author: {b[2]} | Genre: {b[3]} | "
                f"Available: {b[4]}"
            )
    else:
        print("No matching books found.")


# ---------- BORROW BOOK ----------


def borrow_book():
    borrower = input("Borrower's name: ").strip()

    if not borrower:
        print("Borrower's name is required.")
        return

    try:
        book_id = int(input("Enter book ID: "))

    except ValueError:
        print("Invalid book ID.")
        return

    book = db_connection.execute(
        "SELECT title, quantity FROM books WHERE id = ?", (book_id,)
    ).fetchone()

    if book is None:
        print("Book not found.")
        return

    if book[1] <= 0:
        print("Sorry, this book is unavailable.")
        return

    today = datetime.now()
    due = today + timedelta(days=14)

    # Decrease available book quantity
    db_connection.execute(
        "UPDATE books SET quantity = quantity - 1 WHERE id = ?", (book_id,)
    )

    # Save borrowing record
    db_connection.execute(
        """
        INSERT INTO borrowings
        (borrower, book_id, borrow_date, due_date)
        VALUES (?, ?, ?, ?)
    """,
        (
            borrower,
            book_id,
            today.strftime("%Y-%m-%d"),
            due.strftime("%Y-%m-%d"),
        ),
    )

    db_connection.commit()

    log_action("BORROW BOOK", f"{borrower}: {book[0]}")

    print("Book borrowed successfully!")
    print("Due date:", due.strftime("%Y-%m-%d"))


# ---------- RETURN BOOK ----------


def return_book():
    print("\n========== RETURN A BOOK ==========")
    username = input("Enter Username: ").strip()
    student_id = input("Enter Student ID Number: ").strip()

    # Verify identity against the users table
    user = db_connection.execute(
        "SELECT username FROM users WHERE username = ? AND student_id = ?",
        (username, student_id),
    ).fetchone()

    if not user:
        print("Invalid Username or Student ID Number. Authentication failed.")
        return

    # Fetch active (unreturned) borrowings matching the borrower's username
    active_borrowings = db_connection.execute(
        """
        SELECT br.id, b.title, br.borrow_date, br.due_date, br.book_id
        FROM borrowings br
        JOIN books b ON b.id = br.book_id
        WHERE br.borrower = ? AND br.returned = 0
    """,
        (username,),
    ).fetchall()

    if not active_borrowings:
        print(f"No active unreturned books found for user '{username}'.")
        return

    print("\n--- Active Borrowing Records ---")
    for rec in active_borrowings:
        print(
            f"Record ID: {rec[0]} | Title: {rec[1]} | "
            f"Borrowed: {rec[2]} | Due: {rec[3]}"
        )

    try:
        record_id = int(
            input("\nEnter the Record ID of the book you want to return: ")
        )
    except ValueError:
        print("Invalid record ID.")
        return

    # Locate record matching record ID and user
    record = next((r for r in active_borrowings if r[0] == record_id), None)

    if record is None:
        print("Selected Record ID does not match any active borrowing records.")
        return

    rec_id, title, _, _, book_id = record

    # Mark borrowing record as returned
    db_connection.execute(
        "UPDATE borrowings SET returned = 1 WHERE id = ?", (rec_id,)
    )

    # Increase available book quantity
    db_connection.execute(
        "UPDATE books SET quantity = quantity + 1 WHERE id = ?", (book_id,)
    )

    db_connection.commit()

    log_action("RETURN BOOK", f"{username} (ID: {student_id}): {title}")

    print(f"\nSuccess! '{title}' has been returned successfully.")


# ---------- VIEW BORROWING RECORDS ----------


def view_borrowings():
    records = db_connection.execute("""
        SELECT br.id, br.borrower, b.title,
               br.borrow_date, br.due_date, br.returned
        FROM borrowings br
        JOIN books b ON b.id = br.book_id
        ORDER BY br.id DESC
    """).fetchall()

    print("\n========== BORROWING RECORDS ==========")

    if not records:
        print("No borrowing records.")
        return

    for r in records:
        status = "Returned" if r[5] else "Not returned"

        print(
            f"Record ID: {r[0]} | Borrower: {r[1]} | "
            f"Book: {r[2]} | Borrowed: {r[3]} | "
            f"Due: {r[4]} | Status: {status}"
        )


# ---------- AUDIT LOG ----------


def view_audit():
    records = db_connection.execute("""
        SELECT * FROM audit
        ORDER BY id DESC
        LIMIT 100
    """).fetchall()

    print("\n========== AUDIT LOG ==========")

    if not records:
        print("No activity recorded.")
        return

    for r in records:
        print(
            f"ID: {r[0]} | User: {r[1]} | "
            f"Action: {r[2]} | Details: {r[3]} | "
            f"Time: {r[4]}"
        )


# ---------- SUGGESTIONS ----------


def submit_suggestion():
    suggestion = input("Enter your suggestion: ").strip()

    if not suggestion:
        print("Suggestion cannot be empty.")
        return

    db_connection.execute(
        """
        INSERT INTO suggestions (username, suggestion, time)
        VALUES (?, ?, ?)
    """,
        (
            current_user,
            suggestion,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    db_connection.commit()

    log_action("SUBMIT SUGGESTION", suggestion)

    print("Thank you! Your suggestion has been saved.")


def view_suggestions():
    records = db_connection.execute("""
        SELECT * FROM suggestions
        ORDER BY id DESC
    """).fetchall()

    print("\n========== SUGGESTIONS ==========")

    if not records:
        print("No suggestions submitted.")
        return

    for r in records:
        print(
            f"ID: {r[0]} | User: {r[1]} | "
            f"Suggestion: {r[2]} | Time: {r[3]}"
        )


# ---------- RECOMMENDATIONS ----------


def recommend_books():
    genre = input("Enter a genre you like: ").strip()

    if not genre:
        print("Please enter a genre.")
        return

    books = db_connection.execute(
        """
        SELECT title, author, quantity
        FROM books
        WHERE genre LIKE ? AND quantity > 0
        ORDER BY title
    """,
        ("%" + genre + "%",),
    ).fetchall()

    print("\n========== BOOK RECOMMENDATIONS ==========")

    if books:
        for b in books:
            print(f"{b[0]} by {b[1]} | Available: {b[2]}")
    else:
        print("No available books found for that genre.")

    log_action("BOOK RECOMMENDATIONS", genre)


# ---------- MAIN MENU ----------


def main_menu():
    while True:
        print("""
========================================
       LIBRARY MANAGEMENT SYSTEM
========================================

1. About the Library
2. View All Books
3. Search Books
4. Add a Book
5. Borrow a Book
6. Return a Book
7. View Borrowing Records
8. View Audit Logs
9. Submit a Suggestion
10. View Suggestions
11. Recommend Books
12. Logout

========================================
""")

        choice = input("Choose an option (1-12): ").strip()

        if choice == "1":
            about_library()

        elif choice == "2":
            view_books()

        elif choice == "3":
            search_books()

        elif choice == "4":
            add_book()

        elif choice == "5":
            borrow_book()

        elif choice == "6":
            return_book()

        elif choice == "7":
            view_borrowings()

        elif choice == "8":
            view_audit()

        elif choice == "9":
            submit_suggestion()

        elif choice == "10":
            view_suggestions()

        elif choice == "11":
            recommend_books()

        elif choice == "12":
            logout()
            break

        else:
            print("Invalid choice. Please choose 1-12.")


# ---------- RUN PROGRAM ----------


def main():
    setup()

    print("\nWELCOME TO THE LIBRARY SYSTEM")

    while True:
        print("\n1. Login")
        print("2. Exit")

        choice = input("Choose an option: ").strip()

        if choice == "1":
            if login():
                main_menu()

        elif choice == "2":
            print("Thank you for using the system!")
            break

        else:
            print("Invalid choice.")


# Correct entry point guard
if __name__ == "__main__":
    main()