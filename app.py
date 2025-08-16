from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Upload configuration
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Predefined Vendor Login
VENDOR_EMAIL = "vendor@kushwahastore.com"
VENDOR_PASSWORD = "vendor123"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database helper function
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_user_id(email):
    conn = get_db_connection()
    if email == VENDOR_EMAIL:
        # For vendor, we'll use a fixed ID of 1
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            # Create vendor user if doesn't exist
            conn.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                        ("Kushwaha Store", email, VENDOR_PASSWORD, "vendor"))
            conn.commit()
            user_id = conn.lastrowid
        else:
            user_id = user['id']
    else:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        user_id = user['id'] if user else None
    conn.close()
    return user_id

@app.route('/')
def home():
    return render_template('home.html')

# ---------------- Register Route ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template('register.html')
        
        # Save to database (role = buyer by default)
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                         (name, email, password, "buyer"))
            conn.commit()
            flash("Registration successful! Please login.", "success")
        except sqlite3.IntegrityError:
            flash("Email already registered", "error")
        finally:
            conn.close()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

# ---------------- Login Route ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        # Vendor check
        if email == VENDOR_EMAIL and password == VENDOR_PASSWORD:
            session['role'] = 'vendor'
            session['email'] = email
            session['user_id'] = get_user_id(email)
            return redirect(url_for('vendor_dashboard'))
        
        # Buyer check from DB
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ? AND role = 'buyer'",
                            (email, password)).fetchone()
        conn.close()
        
        if user:
            session['role'] = 'buyer'
            session['email'] = email
            session['user_id'] = user['id']
            return redirect(url_for('buyer_dashboard'))
        
        flash("Invalid email or password!", "error")
    
    return render_template("login.html")

# ---------------- Buyer Dashboard ----------------
@app.route('/buyer_dashboard')
def buyer_dashboard():
    if 'role' in session and session['role'] == 'buyer':
        # Get all products to display
        conn = get_db_connection()
        products = conn.execute("""
            SELECT p.*, u.name as vendor_name 
            FROM products p 
            JOIN users u ON p.vendor_id = u.id 
            ORDER BY p.created_at DESC
        """).fetchall()
        conn.close()
        
        return render_template('buyer_dashboard.html', email=session['email'], products=products)
    return redirect(url_for('login'))

# ---------------- Vendor Dashboard ----------------
@app.route('/vendor_dashboard')
def vendor_dashboard():
    if 'role' in session and session['role'] == 'vendor':
        conn = get_db_connection()
        
        # Get vendor's products
        vendor_id = get_user_id(session['email'])
        products = conn.execute("SELECT * FROM products WHERE vendor_id = ?", (vendor_id,)).fetchall()
        
        # Get order statistics
        orders_stats = conn.execute("""
            SELECT status, COUNT(*) as count 
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE p.vendor_id = ?
            GROUP BY status
        """, (vendor_id,)).fetchall()
        
        conn.close()
        
        return render_template('vendor_dashboard.html', 
                             email=session['email'], 
                             products=products,
                             orders_stats=orders_stats)
    return redirect(url_for('login'))

# ---------------- Products Routes ----------------
@app.route('/products')
def products():
    conn = get_db_connection()
    products = conn.execute("""
        SELECT p.*, u.name as vendor_name 
        FROM products p 
        JOIN users u ON p.vendor_id = u.id 
        ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    
    return render_template('products.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()
    product = conn.execute("""
        SELECT p.*, u.name as vendor_name 
        FROM products p 
        JOIN users u ON p.vendor_id = u.id 
        WHERE p.id = ?
    """, (product_id,)).fetchone()
    conn.close()
    
    if not product:
        flash("Product not found", "error")
        return redirect(url_for('products'))
    
    return render_template('product_detail.html', product=product)

# ---------------- Add Product (Vendor) ----------------
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'role' not in session or session['role'] != 'vendor':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        
        # Handle file upload
        image_filename = 'default_product.jpg'
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        # Save to database
        vendor_id = get_user_id(session['email'])
        conn = get_db_connection()
        conn.execute("INSERT INTO products (vendor_id, name, description, price, image) VALUES (?, ?, ?, ?, ?)",
                     (vendor_id, name, description, price, image_filename))
        conn.commit()
        conn.close()
        
        flash("Product added successfully!", "success")
        return redirect(url_for('vendor_dashboard'))
    
    return render_template('add_product.html')

# ---------------- Edit Product (Vendor) ----------------
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'role' not in session or session['role'] != 'vendor':
        return redirect(url_for('login'))
    
    vendor_id = get_user_id(session['email'])
    conn = get_db_connection()
    
    # Check if product belongs to this vendor
    product = conn.execute("SELECT * FROM products WHERE id = ? AND vendor_id = ?", 
                          (product_id, vendor_id)).fetchone()
    
    if not product:
        flash("Product not found or unauthorized", "error")
        conn.close()
        return redirect(url_for('vendor_dashboard'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        
        # Handle file upload
        image_filename = product['image']
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        
        # Update product
        conn.execute("UPDATE products SET name = ?, description = ?, price = ?, image = ? WHERE id = ?",
                     (name, description, price, image_filename, product_id))
        conn.commit()
        conn.close()
        
        flash("Product updated successfully!", "success")
        return redirect(url_for('vendor_dashboard'))
    
    conn.close()
    return render_template('edit_product.html', product=product)

# ---------------- Cart Routes ----------------
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    buyer_id = session['user_id']
    conn = get_db_connection()
    
    # Check if item already in cart
    existing = conn.execute("SELECT * FROM cart WHERE buyer_id = ? AND product_id = ?", 
                           (buyer_id, product_id)).fetchone()
    
    if existing:
        # Update quantity
        conn.execute("UPDATE cart SET quantity = quantity + 1 WHERE buyer_id = ? AND product_id = ?",
                     (buyer_id, product_id))
    else:
        # Add new item
        conn.execute("INSERT INTO cart (buyer_id, product_id, quantity) VALUES (?, ?, ?)",
                     (buyer_id, product_id, 1))
    
    conn.commit()
    conn.close()
    
    flash("Item added to cart!", "success")
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/cart')
def cart():
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    buyer_id = session['user_id']
    conn = get_db_connection()
    
    cart_items = conn.execute("""
        SELECT c.*, p.name, p.price, p.image, (c.quantity * p.price) as total
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.buyer_id = ?
    """, (buyer_id,)).fetchall()
    
    conn.close()
    
    total_amount = sum([item['total'] for item in cart_items])
    
    return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    buyer_id = session['user_id']
    conn = get_db_connection()
    conn.execute("DELETE FROM cart WHERE buyer_id = ? AND product_id = ?", (buyer_id, product_id))
    conn.commit()
    conn.close()
    
    flash("Item removed from cart!", "success")
    return redirect(url_for('cart'))

# ---------------- Order Routes ----------------
@app.route('/place_order')
def place_order():
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    buyer_id = session['user_id']
    conn = get_db_connection()
    
    # Get cart items
    cart_items = conn.execute("""
        SELECT c.*, p.price
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.buyer_id = ?
    """, (buyer_id,)).fetchall()
    
    if not cart_items:
        flash("Your cart is empty!", "error")
        return redirect(url_for('cart'))
    
    # Create orders from cart items
    for item in cart_items:
        total_price = item['quantity'] * item['price']
        conn.execute("""
            INSERT INTO orders (buyer_id, product_id, quantity, total_price, status) 
            VALUES (?, ?, ?, ?, 'pending')
        """, (buyer_id, item['product_id'], item['quantity'], total_price))
    
    # Clear cart
    conn.execute("DELETE FROM cart WHERE buyer_id = ?", (buyer_id,))
    
    conn.commit()
    conn.close()
    
    flash("Order placed successfully!", "success")
    return redirect(url_for('orders'))

@app.route('/buy_now/<int:product_id>')
def buy_now(product_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    buyer_id = session['user_id']
    conn = get_db_connection()
    
    # Get product details
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    
    if not product:
        flash("Product not found!", "error")
        return redirect(url_for('products'))
    
    # Create order directly
    conn.execute("""
        INSERT INTO orders (buyer_id, product_id, quantity, total_price, status) 
        VALUES (?, ?, 1, ?, 'pending')
    """, (buyer_id, product_id, product['price']))
    
    conn.commit()
    conn.close()
    
    flash("Order placed successfully!", "success")
    return redirect(url_for('orders'))

@app.route('/orders')
def orders():
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    buyer_id = session['user_id']
    conn = get_db_connection()
    
    orders = conn.execute("""
        SELECT o.*, p.name, p.image
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.buyer_id = ?
        ORDER BY o.ordered_at DESC
    """, (buyer_id,)).fetchall()
    
    conn.close()
    
    return render_template('orders.html', orders=orders)

# ---------------- Vendor Order Management ----------------
@app.route('/view_orders')
def view_orders():
    if 'role' not in session or session['role'] != 'vendor':
        return redirect(url_for('login'))
    
    vendor_id = get_user_id(session['email'])
    conn = get_db_connection()
    
    orders = conn.execute("""
        SELECT o.*, p.name as product_name, u.name as buyer_name, u.email as buyer_email
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.buyer_id = u.id
        WHERE p.vendor_id = ?
        ORDER BY o.ordered_at DESC
    """, (vendor_id,)).fetchall()
    
    conn.close()
    
    return render_template('view_orders.html', orders=orders)

@app.route('/update_order_status/<int:order_id>/<new_status>')
def update_order_status(order_id, new_status):
    if 'role' not in session or session['role'] != 'vendor':
        return redirect(url_for('login'))
    
    valid_statuses = ['pending', 'shipped', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        flash("Invalid status!", "error")
        return redirect(url_for('view_orders'))
    
    conn = get_db_connection()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    
    flash(f"Order status updated to {new_status}!", "success")
    return redirect(url_for('view_orders'))

# ---------------- Logout ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)