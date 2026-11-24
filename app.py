import os, io, secrets, hashlib
from datetime import datetime
from functools import wraps
from urllib.parse import urljoin
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import qrcode

load_dotenv()
db = SQLAlchemy()
login_manager = LoginManager()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="employee")
    active = db.Column(db.Boolean, default=True)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(30), default="units")
    quantity_on_hand = db.Column(db.Integer, default=0)
    reorder_level = db.Column(db.Integer, default=5)
    reorder_quantity = db.Column(db.Integer, default=10)
    unit_price = db.Column(db.Float, default=0)
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"))
    supplier = db.relationship("Supplier")
    qr_token = db.Column(db.String(64), unique=True, default=lambda: secrets.token_urlsafe(24))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def low_stock(self): return self.quantity_on_hand <= self.reorder_level

class ReorderRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product = db.relationship("Product")
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    requester = db.relationship("User", foreign_keys=[requester_id])
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)
    status = db.Column(db.String(30), default="pending", nullable=False)
    duplicate_of = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    reviewed_at = db.Column(db.DateTime)
    supplier_email_sent = db.Column(db.Boolean, default=False)

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    is_vercel = bool(os.getenv("VERCEL"))
    secret_key = os.getenv("SECRET_KEY")
    database_url = os.getenv("DATABASE_URL")
    if is_vercel:
        missing = [name for name in ("SECRET_KEY", "DATABASE_URL", "ADMIN_EMAIL", "ADMIN_PASSWORD")
                   if not os.getenv(name)]
        if missing:
            raise RuntimeError("Set these Vercel environment variables: " + ", ".join(missing))
        if not database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("DATABASE_URL must point to a PostgreSQL database on Vercel.")
    database_url = database_url or "sqlite:///supplysnap.db"
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]
    app.config.update(
        SECRET_KEY=secret_key or "dev-only-change-this-secret",
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app); login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User, int(user_id))

    def roles(*allowed):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if not current_user.is_authenticated: return login_manager.unauthorized()
                if current_user.role not in allowed:
                    flash("You do not have permission to access that page.", "danger")
                    return redirect(url_for("dashboard"))
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    def send_supplier_email(order):
        supplier = order.product.supplier
        if not supplier or not supplier.email: return False
        subject = f"SupplySnap reorder request #{order.id} — {order.product.name}"
        body = (f"Hello {supplier.contact_name or supplier.name},\n\n"
                f"Please process this reorder request:\nProduct: {order.product.name}\n"
                f"SKU: {order.product.sku}\nQuantity: {order.quantity} {order.product.unit}\n"
                f"Requested by: {order.requester.name}\nRequest ID: {order.id}\n"
                f"Notes: {order.note or '—'}\n\nThank you,\nSupplySnap")
        host, username, password = os.getenv("MAIL_SERVER"), os.getenv("MAIL_USERNAME"), os.getenv("MAIL_PASSWORD")
        if not (host and username and password):
            app.logger.info("EMAIL NOT CONFIGURED — To: %s | Subject: %s\n%s", supplier.email, subject, body)
            return True
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage(); msg["Subject"] = subject; msg["From"] = os.getenv("DEFAULT_SENDER", username)
        msg["To"] = supplier.email; msg.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("MAIL_PORT", "587"))) as smtp:
            if os.getenv("MAIL_USE_TLS", "true").lower() == "true": smtp.starttls()
            smtp.login(username, password); smtp.send_message(msg)
        return True

    @app.route("/")
    def index():
        return redirect(url_for("dashboard") if current_user.is_authenticated else url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated: return redirect(url_for("dashboard"))
        if request.method == "POST":
            user = User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
            if user and user.active and user.check_password(request.form.get("password","")):
                login_user(user); return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Invalid email or password.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout(): logout_user(); flash("You have been signed out.", "success"); return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        total = Product.query.count()
        low = Product.query.filter(Product.quantity_on_hand <= Product.reorder_level).count()
        pending = ReorderRequest.query.filter_by(status="pending").count()
        approved = ReorderRequest.query.filter_by(status="approved").count()
        recent = ReorderRequest.query.order_by(ReorderRequest.created_at.desc()).limit(7).all()
        spend = db.session.query(db.func.sum(ReorderRequest.quantity * Product.unit_price)).join(Product).filter(ReorderRequest.status=="approved").scalar() or 0
        return render_template("dashboard.html", total=total, low=low, pending=pending, approved=approved, recent=recent, spend=spend)

    @app.route("/products")
    @login_required
    def products():
        items = Product.query.order_by(Product.name).all()
        return render_template("products.html", products=items)

    @app.route("/products/new", methods=["GET","POST"])
    @login_required
    @roles("admin","manager")
    def product_new():
        suppliers = Supplier.query.order_by(Supplier.name).all()
        if request.method == "POST":
            try:
                p = Product(name=request.form["name"].strip(), sku=request.form["sku"].strip().upper(),
                    description=request.form.get("description"), unit=request.form.get("unit") or "units",
                    quantity_on_hand=max(0,int(request.form.get("quantity_on_hand",0))),
                    reorder_level=max(0,int(request.form.get("reorder_level",5))),
                    reorder_quantity=max(1,int(request.form.get("reorder_quantity",10))),
                    unit_price=max(0,float(request.form.get("unit_price",0) or 0)),
                    supplier_id=int(request.form["supplier_id"]) if request.form.get("supplier_id") else None)
                db.session.add(p); db.session.commit(); flash("Product created and QR code is ready.", "success")
                return redirect(url_for("products"))
            except (ValueError, KeyError):
                db.session.rollback(); flash("Please check the product details and numeric fields.", "danger")
        return render_template("product_form.html", suppliers=suppliers, product=None)

    @app.route("/products/<int:product_id>/edit", methods=["GET","POST"])
    @login_required
    @roles("admin","manager")
    def product_edit(product_id):
        p = db.get_or_404(Product, product_id); suppliers = Supplier.query.all()
        if request.method == "POST":
            try:
                p.name=request.form["name"].strip(); p.sku=request.form["sku"].strip().upper()
                p.description=request.form.get("description"); p.unit=request.form.get("unit") or "units"
                p.quantity_on_hand=max(0,int(request.form.get("quantity_on_hand",0)))
                p.reorder_level=max(0,int(request.form.get("reorder_level",5)))
                p.reorder_quantity=max(1,int(request.form.get("reorder_quantity",10)))
                p.unit_price=max(0,float(request.form.get("unit_price",0) or 0))
                p.supplier_id=int(request.form["supplier_id"]) if request.form.get("supplier_id") else None
                db.session.commit(); flash("Product updated.", "success"); return redirect(url_for("products"))
            except (ValueError, KeyError):
                db.session.rollback(); flash("Please check the entered values.", "danger")
        return render_template("product_form.html", suppliers=suppliers, product=p)

    @app.route("/products/<int:product_id>/qr")
    @login_required
    def product_qr(product_id):
        p=db.get_or_404(Product,product_id)
        target=url_for("scan", token=p.qr_token, _external=True)
        img=qrcode.make(target); buf=io.BytesIO(); img.save(buf,format="PNG"); buf.seek(0)
        return send_file(buf,mimetype="image/png",download_name=f"supplysnap-{p.sku}.png")

    @app.route("/scan/<token>", methods=["GET","POST"])
    @login_required
    def scan(token):
        p=Product.query.filter_by(qr_token=token).first_or_404()
        if request.method=="POST":
            try: qty=int(request.form.get("quantity","0"))
            except ValueError: qty=0
            if qty < 1 or qty > 100000:
                flash("Enter a valid reorder quantity.", "danger")
            else:
                duplicate=ReorderRequest.query.filter_by(product_id=p.id,status="pending").first()
                order=ReorderRequest(product=p, requester=current_user, quantity=qty,
                    note=request.form.get("note","").strip(), duplicate_of=duplicate.id if duplicate else None)
                db.session.add(order); db.session.commit()
                if duplicate: flash(f"Request submitted and flagged as a possible duplicate of request #{duplicate.id}.", "warning")
                else: flash("Reorder request submitted to purchasing.", "success")
                return redirect(url_for("requests"))
        return render_template("scan.html", product=p)

    @app.route("/requests")
    @login_required
    def requests():
        q=ReorderRequest.query.order_by(ReorderRequest.created_at.desc())
        if current_user.role=="employee": q=q.filter_by(requester_id=current_user.id)
        return render_template("requests.html", requests=q.all())

    @app.route("/requests/<int:request_id>/<action>", methods=["POST"])
    @login_required
    @roles("admin","manager")
    def review_request(request_id, action):
        order=db.get_or_404(ReorderRequest,request_id)
        if order.status!="pending":
            flash("This request has already been reviewed.", "warning")
        elif action=="approve":
            order.status="approved"; order.reviewed_by=current_user; order.reviewed_at=datetime.utcnow()
            try:
                order.supplier_email_sent=send_supplier_email(order)
                db.session.commit()
                flash("Request approved. Supplier email was sent or logged (check server console if SMTP is not configured).", "success")
            except Exception as exc:
                db.session.rollback(); app.logger.exception("Supplier email failed")
                flash("Approval email failed. Check SMTP settings and try again.", "danger")
        elif action=="reject":
            order.status="rejected"; order.reviewed_by=current_user; order.reviewed_at=datetime.utcnow()
            db.session.commit(); flash("Request rejected.", "success")
        return redirect(url_for("requests"))

    @app.route("/suppliers", methods=["GET","POST"])
    @login_required
    @roles("admin","manager")
    def suppliers():
        if request.method=="POST":
            s=Supplier(name=request.form["name"].strip(),contact_name=request.form.get("contact_name"),
                email=request.form["email"].strip(),phone=request.form.get("phone"))
            db.session.add(s); db.session.commit(); flash("Supplier added.", "success"); return redirect(url_for("suppliers"))
        return render_template("suppliers.html", suppliers=Supplier.query.order_by(Supplier.name).all())

    @app.route("/team", methods=["GET","POST"])
    @login_required
    @roles("admin")
    def team():
        if request.method=="POST":
            email=request.form["email"].strip().lower()
            if User.query.filter_by(email=email).first(): flash("That email already exists.", "danger")
            else:
                u=User(name=request.form["name"].strip(),email=email,role=request.form["role"])
                u.set_password(request.form["password"]); db.session.add(u); db.session.commit()
                flash("Team member created.", "success")
            return redirect(url_for("team"))
        return render_template("team.html", users=User.query.order_by(User.name).all())

    @app.route("/reports")
    @login_required
    @roles("admin","manager")
    def reports():
        rows= db.session.query(Product.name, db.func.sum(ReorderRequest.quantity).label("qty")).join(ReorderRequest).filter(ReorderRequest.status=="approved").group_by(Product.id).order_by(db.desc("qty")).all()
        return render_template("reports.html", rows=rows)

    @app.errorhandler(404)
    def not_found(e): return render_template("404.html"),404

    with app.app_context():
        db.create_all()
        if not User.query.first():
            admin_email = os.getenv("ADMIN_EMAIL")
            admin_password = os.getenv("ADMIN_PASSWORD")
            if is_vercel and not (admin_email and admin_password):
                app.logger.warning("No admin user created. Set ADMIN_EMAIL and ADMIN_PASSWORD in Vercel.")
            else:
                u=User(name=os.getenv("ADMIN_NAME", "SupplySnap Admin"),
                       email=(admin_email or "admin@supplysnap.local").strip().lower(),role="admin")
                u.set_password(admin_password or "Admin123!"); db.session.add(u); db.session.commit()
        if Supplier.query.count()==0:
            s=Supplier(name="Northstar Supplies",contact_name="Purchasing Desk",email="orders@example.com")
            db.session.add(s); db.session.flush()
            if Product.query.count()==0:
                db.session.add_all([
                    Product(name="A4 Copy Paper",sku="PAP-001",description="80 GSM office paper",unit="reams",quantity_on_hand=3,reorder_level=5,reorder_quantity=20,unit_price=245,supplier=s),
                    Product(name="Blue Ballpoint Pens",sku="PEN-002",description="0.7 mm blue pens",unit="boxes",quantity_on_hand=24,reorder_level=8,reorder_quantity=12,unit_price=95,supplier=s),
                    Product(name="Hand Sanitizer 500ml",sku="HYG-003",description="500 ml pump bottle",unit="bottles",quantity_on_hand=4,reorder_level=10,reorder_quantity=15,unit_price=120,supplier=s)])
            db.session.commit()
    return app

app=create_app()
if __name__=="__main__":
    app.run(debug=os.getenv("FLASK_DEBUG","false").lower()=="true")
