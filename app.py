from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database
def init_db():
    with sqlite3.connect("database.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                image_path TEXT,
               
                brand TEXT,
                price INTEGER,
                details TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                products TEXT,
                total_amount INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

# Seed admin credentials
def seed_admin():
    with sqlite3.connect("database.db") as conn:
        try:
            conn.execute("INSERT INTO users (name, username, password, role) VALUES (?, ?, ?, ?)",
                         ("Admin", "admin", "admin123", "admin"))
            conn.commit()
        except sqlite3.IntegrityError:
            pass

@app.route('/')
def home():
    return redirect(url_for('login'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("database.db") as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        if user:
            session['user_id'] = user[0]
            session['role'] = user[4]
            session['name'] = user[1]
            if user[4] == 'admin':
                return redirect(url_for('add_product'))
            else:
                return redirect(url_for('products'))
        else:
            flash("Invalid username or password", "danger")
    return render_template('login.html')

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect("database.db") as conn:
            try:
                conn.execute("INSERT INTO users (name, username, password, role) VALUES (?, ?, ?, ?)",
                             (name, username, password, "user"))
                conn.commit()
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Username already exists.", "danger")
    return render_template('register.html')

# Add Product (Admin Only)
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['name']
     
        brand = request.form['brand']
        price = int(request.form['price'])
        details = request.form['details']
        image = request.files['image']

        # Ensure the upload folder exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
        image.save(image_path)

        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO products (name, image_path,  brand, price, details) VALUES (?, ?, ?, ?, ?)",
                         (name, image_path,  brand, price, details))
            conn.commit()
        flash("Product added successfully!", "success")
    return render_template('add_product.html')


# View Products (User Only)
@app.route('/products', methods=['GET', 'POST'])
def products():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    selected_products = []
    total_cost = 0
    if request.method == 'POST':
        budget = int(request.form['budget'])
        with sqlite3.connect("database.db") as conn:
            products = conn.execute("SELECT * FROM products ORDER BY price ASC").fetchall()
        for product in products:
            if total_cost + product[4] <= budget:  # product[5] is price
                selected_products.append(product)
                total_cost += product[4]
        # Store payment details in the database
        with sqlite3.connect("database.db") as conn:
            conn.execute("INSERT INTO payments (user_id, products, total_amount) VALUES (?, ?, ?)",
                         (session['user_id'], ", ".join([p[1] for p in selected_products]), total_cost))
            conn.commit()
        flash("Payment successful!", "success")
    with sqlite3.connect("database.db") as conn:
        products = conn.execute("SELECT * FROM products").fetchall()
    return render_template('products.html', products=products, selected_products=selected_products, total=total_cost)


@app.route('/buy_product/<int:product_id>', methods=['POST'])
def buy_product(product_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))

    # Fetch the selected product from the database
    with sqlite3.connect("database.db") as conn:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    # Store the selected product in the session to display on the payment page
    if 'selected_products' not in session:
        session['selected_products'] = []
    session['selected_products'].append(product)
    session.modified = True

    # Redirect to the payment page
    return redirect(url_for('payment'))

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if session.get('role') != 'user':
        return redirect(url_for('login'))

    selected_products = session.get('selected_products', [])
    total_cost = sum(product[4] for product in selected_products)

    if request.method == 'POST':
        # Store payment details in the database
        with sqlite3.connect("database.db") as conn:
            products_names = ", ".join([p[1] for p in selected_products])
            conn.execute("INSERT INTO payments (user_id, products, total_amount) VALUES (?, ?, ?)",
                         (session['user_id'], products_names, total_cost))
            conn.commit()

        # Clear the session after payment
        session.pop('selected_products', None)
        flash("Payment successful! Thank you for your purchase.", "success")
        return redirect(url_for('products'))

    return render_template('payment.html', selected_products=selected_products, total_cost=total_cost)


# Logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    seed_admin()
    app.run(debug=True)
