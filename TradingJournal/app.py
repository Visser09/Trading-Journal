import os
import uuid
import calendar
import holidays
import openai
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask import session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash


from datetime import datetime, date


app = Flask(__name__)
app.secret_key = "your-secret-key"

# Setup
db_dir = os.path.join(os.getcwd(), "db")
os.makedirs(db_dir, exist_ok=True)

uploads_dir = os.path.join("static", "uploads")
os.makedirs(uploads_dir, exist_ok=True)

db_path = os.path.join(db_dir, "journal.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

# Flask-Login initialization
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Define the User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # User preferences (for theme mode and accent color)
    theme_mode = db.Column(db.String(10), default="dark")
    accent_color = db.Column(db.String(20), default="purple")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
###############################################################################
# PRODUCT DATA
###############################################################################
PRODUCT_DATA = {
    "ES": {
        "type": "futures",
        "tick_size": 0.25,
        "tick_value": 12.50
    },
    "NQ": {
        "type": "futures",
        "tick_size": 0.25,
        "tick_value": 5.00
    },
    "CL": {
        "type": "futures",
        "tick_size": 0.01,
        "tick_value": 10.00
    },
    "MNQ": {
        "type": "futures",
        "tick_size": 0.25,
        "tick_value": 0.50
    },
    "TSLA": {
        "type": "option",
        "option_multiplier": 100
    },
    # Add more products as needed...
}

###############################################################################
# MODELS
###############################################################################
class DayRecord(db.Model):
    date = db.Column(db.String(10), primary_key=True)
    pnl = db.Column(db.Float, default=0)
    # We remove or ignore day-level notes if we don't need them
    # day_notes = db.Column(db.Text)

    screenshots = db.relationship("Screenshot", backref="day_record", lazy=True)
    trades = db.relationship("Trade", backref="day_record", lazy=True)

class Screenshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), db.ForeignKey("day_record.date"), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), db.ForeignKey("day_record.date"), nullable=False)
    side = db.Column(db.String(4))  # "buy" or "sell"
    ticker = db.Column(db.String(20))
    trade_type = db.Column(db.String(20))
    trade_notes = db.Column(db.Text)
    entry_price = db.Column(db.Float, default=0)
    exit_price = db.Column(db.Float, default=0)
    contract_count = db.Column(db.Integer, default=1)
    trade_pnl = db.Column(db.Float, default=0)
    scale_events = db.relationship("ScaleEvent", backref="trade", lazy=True)

class ScaleEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey("trade.id"), nullable=False)
    scale_price = db.Column(db.Float, default=0)
    scale_contracts = db.Column(db.Integer, default=0)

with app.app_context():
    db.create_all()




class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), default="New Chat")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship("Message", backref="conversation", lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    role = db.Column(db.String(20))  # "user" or "assistant"
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

###############################################################################
# HELPERS
###############################################################################
def parse_float(value):
    try:
        return float(value)
    except ValueError:
        return 0.0

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in {"png", "jpg", "jpeg", "gif"}

def get_multiplier(ticker_info, side):
    """
    Return a function that calculates PnL given (entry, exit, contracts).
    If side='buy', PnL = (exit-entry)*contracts*multiplier
    If side='sell', PnL = (entry-exit)*contracts*multiplier
    """
    if not ticker_info:
        # fallback
        if side == "sell":
            return lambda e, x, c: (e - x) * c
        else:
            return lambda e, x, c: (x - e) * c

    if ticker_info["type"] == "futures":
        tick_size = ticker_info["tick_size"]
        tick_value = ticker_info["tick_value"]
        if side == "sell":
            return lambda e, x, c: ((e - x) / tick_size) * tick_value * c
        else:
            return lambda e, x, c: ((x - e) / tick_size) * tick_value * c
    elif ticker_info["type"] == "option":
        multiplier = ticker_info["option_multiplier"]
        if side == "sell":
            return lambda e, x, c: (e - x) * multiplier * c
        else:
            return lambda e, x, c: (x - e) * multiplier * c
    else:
        # fallback
        if side == "sell":
            return lambda e, x, c: (e - x) * c
        else:
            return lambda e, x, c: (x - e) * c

###############################################################################
# CONTEXT PROCESSOR
###############################################################################

@app.context_processor
def inject_globals():
    return {
        "today": date.today(),
        "theme_mode": current_user.theme_mode if current_user.is_authenticated else "dark",
        "accent_color": current_user.accent_color if current_user.is_authenticated else "purple",
        "current_user": current_user
    }

###############################################################################
# ROUTES
###############################################################################

@app.route("/ai_chat")
@login_required
def ai_chat():
    # Query the user's conversations.
    convs = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
    if not convs:
        # No conversation exists, so create one.
        new_conv = Conversation(user_id=current_user.id, title="New Chat")
        db.session.add(new_conv)
        db.session.commit()
        convs = [new_conv]
    # Redirect to the most recent conversation.
    return redirect(url_for("ai_chat_conv", conv_id=convs[0].id))

@app.route("/ai_chat/new", methods=["POST"])
@login_required
def new_conversation():
    """Create a new conversation and redirect to it."""
    conv = Conversation(user_id=current_user.id, title="New Chat")
    db.session.add(conv)
    db.session.commit()
    return redirect(url_for("ai_chat_conv", conv_id=conv.id))

@app.route("/ai_chat/<int:conv_id>", methods=["GET", "POST"])
@login_required
def ai_chat_conv(conv_id):
    conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first_or_404()

    # Get all conversations for the sidebar.
    convs = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()

    if request.method == "POST":
        user_message = request.form.get("user_message", "").strip()
        if user_message:
            # Save user message.
            new_msg = Message(conversation_id=conversation.id, role="user", content=user_message)
            db.session.add(new_msg)
            db.session.commit()

            # Get AI response.
            ai_reply = get_ai_response(conversation)
            assistant_msg = Message(conversation_id=conversation.id, role="assistant", content=ai_reply)
            db.session.add(assistant_msg)
            db.session.commit()

        return redirect(url_for("ai_chat_conv", conv_id=conversation.id))

    messages = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.created_at).all()
    return render_template("ai_chat.html", conversation=conversation, messages=messages, user_conversations=convs)



def get_ai_response(conversation):
    """
    Build a prompt from the conversation messages, call OpenAI (or another LLM),
    and return the model's reply.
    """
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY", "YOUR-API-KEY")

    # Build the messages param
    chat_history = []
    # A system message to define the bot's persona
    chat_history.append({
        "role": "system",
        "content": (
            "You are a trading mentor with extensive knowledge of futures, options, and stocks. "
            "You provide educational advice, disclaimers, and guidance, but not financial advice."
        )
    })

    # Include all messages from the DB
    msgs = Message.query.filter_by(conversation_id=conversation.id).order_by(Message.created_at).all()
    for m in msgs:
        chat_history.append({
            "role": m.role,
            "content": m.content
        })

    # Call OpenAI
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=chat_history,
        max_tokens=300,
        temperature=0.7
    )

    return response.choices[0].message["content"]

@app.route("/")
@login_required
def home():
    return redirect(url_for("dashboard"))

@app.route("/quick_entry")
def quick_entry():
    return render_template("quick_entry.html")

@app.route("/trades")
def trades():
    all_trades = Trade.query.order_by(Trade.date.desc()).all()
    return render_template("trades.html", trades=all_trades)

@app.route("/reports")
def reports():
    trades = Trade.query.order_by(Trade.date).all()
    total_pnl = sum(trade.trade_pnl for trade in trades)

    wins = [t for t in trades if t.trade_pnl > 0]
    losses = [t for t in trades if t.trade_pnl < 0]
    trade_count = len(trades)

    win_rate = f"{(len(wins) / trade_count * 100):.2f}%" if trade_count else "0%"

    total_win_amount = sum(t.trade_pnl for t in wins)
    total_loss_amount = abs(sum(t.trade_pnl for t in losses))
    profit_factor = round(total_win_amount / total_loss_amount, 2) if total_loss_amount else "N/A"

    average_win = total_win_amount / len(wins) if wins else 0
    average_loss = total_loss_amount / len(losses) if losses else 0

    # Max Drawdown calculation
    cumulative_pnl = 0
    peak = 0
    max_drawdown = 0
    pnl_over_time = []
    dates_labels = []

    for trade in sorted(trades, key=lambda t: t.date):
        cumulative_pnl += trade.trade_pnl
        peak = max(peak, cumulative_pnl)
        drawdown = peak - cumulative_pnl
        max_drawdown = max(max_drawdown, drawdown)
        pnl_over_time.append(round(cumulative_pnl, 2))
        dates_labels.append(datetime.strptime(trade.day_record.date, '%Y-%m-%d').strftime('%b %d'))

    # Average trade duration placeholder
    average_duration = 1

    metrics = {
        "total_pnl": round(total_pnl, 2),
        "win_rate": win_rate,
        "trade_count": trade_count,
        "profit_factor": profit_factor,
        "max_drawdown": round(max_drawdown, 2),
        "average_win": round(average_win, 2),
        "average_loss": round(average_loss, 2),
        "average_duration": average_duration,
        "chart_labels": dates_labels,
        "chart_data": pnl_over_time
    }

    return render_template("reports.html", metrics=metrics)


@app.route("/day/<date_str>")
def show_day(date_str):
    """
    Multi–trade day view
    """
    day = DayRecord.query.get(date_str)
    if not day:
        day = DayRecord(date=date_str)
        db.session.add(day)
        db.session.commit()
    return render_template("day_multi.html", day=day)

import holidays

@app.route("/month/<int:year>/<int:month>")
def show_month(year, month):
    cal = calendar.Calendar(firstweekday=6)
    all_records = DayRecord.query.all()
    day_records = {dr.date: dr for dr in all_records}
    
    # Get US holidays for the year (you can expand this to multiple years or regions)
    us_holidays = holidays.US(years=[year])
    
    weeks = []
    i = 0
    for d in cal.itermonthdates(year, month):
        if d.month == month:
            date_str = d.strftime("%Y-%m-%d")
            record = day_records.get(date_str)
            # Determine if it's a trading day: a weekday and not a holiday
            is_trading_day = (d.weekday() < 5) and (d not in us_holidays)
            # If not a trading day, set a neutral color; otherwise, use PnL-based or theme-based color
            if not is_trading_day:
                color = "grey"
            else:
                if record:
                    color = "green" if record.pnl > 0 else "red" if record.pnl < 0 else "var(--primary-color)"
                else:
                    color = "var(--primary-color)"
            day_pnl = record.pnl if record else None
            holiday_name = us_holidays.get(d, "")  # Returns holiday name if it is a holiday, else empty string
            cell_info = (d.day, date_str, color, day_pnl, holiday_name)
        else:
            cell_info = (0, "", "", None, "")
        if i % 7 == 0:
            weeks.append([])
        weeks[-1].append(cell_info)
        i += 1

    # prev/next month logic remains the same...
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    month_name = calendar.month_name[month]
    return render_template("month.html",
                           year=year, month=month, month_name=month_name,
                           weeks=weeks,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month)

from flask import Flask, render_template, request, redirect, url_for, flash, session

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        # Update user preferences
        current_user.theme_mode = request.form.get("mode", "dark")
        current_user.accent_color = request.form.get("accent_color", "purple")
        # Update account details if provided
        current_user.username = request.form.get("username", current_user.username)
        current_user.email = request.form.get("email", current_user.email)
        db.session.commit()
        flash("Settings updated successfully!")
        return redirect(url_for("settings"))
    return render_template("settings.html", user=current_user)



@app.route("/update_account", methods=["POST"])
def update_account():
    # Here you’d normally fetch the current user from your database,
    # then update username/email from the form data.
    username = request.form.get("username")
    email = request.form.get("email")
    
    # Example:
    # current_user.username = username
    # current_user.email = email
    # db.session.commit()

    flash("Account details updated!")
    return redirect(url_for("settings"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        # Check if username or email already exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email already exists!")
            return redirect(url_for("register"))
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))
    return render_template("register.html")  # Create this template with a registration form

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Logged in successfully!")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out!")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    trades = Trade.query.all()

    # Basic stats for the metrics
    total_pnl = sum(t.trade_pnl for t in trades)
    trade_count = len(trades)
    wins = len([t for t in trades if t.trade_pnl > 0])
    win_rate = f"{(wins / trade_count * 100):.2f}%" if trade_count else "0%"
    account_balance = 10000 + total_pnl  # Example logic

    metrics = {
        "total_pnl": round(total_pnl, 2),
        "account_balance": round(account_balance, 2),
        "total_trades": trade_count,
        "win_rate": win_rate
    }

    # Build PnL-over-time data for the chart
    cumulative_pnl = 0
    pnl_over_time = []
    date_labels = []

    for trade in sorted(trades, key=lambda t: t.date):
        cumulative_pnl += trade.trade_pnl
        pnl_over_time.append(round(cumulative_pnl, 2))
        date_labels.append(trade.date)  # Or format as you like

    return render_template(
        "dashboard.html",
        metrics=metrics,
        chart_labels=date_labels,
        chart_data=pnl_over_time
    )

###############################################################################
# QUICK ENTRY => Single DayRecord logic
###############################################################################
@app.route("/save_dayrecord", methods=["POST"])
def save_dayrecord():
    date_str = request.form["date_str"]
    side = request.form.get("side", "").lower()
    entry_price = parse_float(request.form.get("entry_price", "0"))
    exit_price = parse_float(request.form.get("exit_price", "0"))
    notes = request.form.get("notes", "").strip()
    trade_type = request.form.get("trade_type", "").strip()
    ticker = request.form.get("ticker", "").strip().upper()
    contract_count = request.form.get("contract_count", "1")
    try:
        contract_count = int(contract_count)
    except ValueError:
        contract_count = 1

    files = request.files.getlist("screenshots[]")
    valid_files = [f for f in files if f.filename]
    if len(valid_files) > 10:
        flash("You can only upload up to 10 screenshots at once.")
        return redirect(url_for("quick_entry"))

    day = DayRecord.query.get(date_str)
    if not day:
        day = DayRecord(date=date_str)
        db.session.add(day)

    # We'll do a naive PnL approach for single-day usage
    ticker_info = PRODUCT_DATA.get(ticker, None)
    calc_pnl = get_multiplier(ticker_info, side)
    naive_pnl = calc_pnl(entry_price, exit_price, contract_count)
    day.pnl = naive_pnl

    # Store day-level screenshots
    for f in valid_files:
        if allowed_file(f.filename):
            ext = os.path.splitext(f.filename)[1]
            unique_name = f"{date_str}_{uuid.uuid4().hex}{ext}"
            save_path = os.path.join(uploads_dir, unique_name)
            f.save(save_path)
            new_shot = Screenshot(date=date_str, file_path=f"uploads/{unique_name}")
            db.session.add(new_shot)
        else:
            flash(f"Invalid file type: {f.filename}")

    db.session.commit()
    flash("Day record saved successfully!")
    return redirect(url_for("quick_entry"))

###############################################################################
# MULTI–TRADE: ADD A NEW TRADE
###############################################################################
@app.route("/add_trade/<date_str>", methods=["POST"])
def add_trade(date_str):
    day = DayRecord.query.get(date_str)
    if not day:
        flash("Invalid day.")
        return redirect(url_for("home"))

    side = request.form.get("side", "").lower()
    ticker = request.form.get("ticker", "").strip().upper()
    trade_type = request.form.get("trade_type", "").strip()
    trade_notes = request.form.get("trade_notes", "").strip()

    entry_price = parse_float(request.form.get("entry_price", "0"))
    exit_price = parse_float(request.form.get("exit_price", "0"))
    contract_count = parse_float(request.form.get("contract_count", "1"))

    # create trade
    new_trade = Trade(
        date=date_str,
        side=side,
        ticker=ticker,
        trade_type=trade_type,
        trade_notes=trade_notes,
        entry_price=entry_price,
        exit_price=exit_price,
        contract_count=contract_count
    )
    db.session.add(new_trade)
    db.session.flush()  # get new_trade.id

    # main trade PnL
    ticker_info = PRODUCT_DATA.get(ticker, None)
    calc_pnl = get_multiplier(ticker_info, side)
    main_pnl = calc_pnl(entry_price, exit_price, contract_count)
    new_trade.trade_pnl = main_pnl

    # scale events
    scale_index = 0
    while True:
        price_key = f"scale_{scale_index}_price"
        contracts_key = f"scale_{scale_index}_contracts"
        if price_key not in request.form:
            break
        scale_price_val = parse_float(request.form.get(price_key, "0"))
        scale_contracts_val = parse_float(request.form.get(contracts_key, "0"))
        if scale_contracts_val != 0:
            new_scale = ScaleEvent(
                trade_id=new_trade.id,
                scale_price=scale_price_val,
                scale_contracts=int(scale_contracts_val)
            )
            db.session.add(new_scale)

            # partial scale PnL
            partial_pnl = calc_pnl(entry_price, scale_price_val, scale_contracts_val)
            new_trade.trade_pnl += partial_pnl

        scale_index += 1

    # screenshots for this trade (stored day-level for now)
    files = request.files.getlist("screenshots[]")
    valid_files = [f for f in files if f.filename]
    if len(valid_files) > 10:
        flash("You can only upload up to 10 screenshots at once.")
        return redirect(url_for("show_day", date_str=date_str))

    for f in valid_files:
        if allowed_file(f.filename):
            ext = os.path.splitext(f.filename)[1]
            unique_name = f"{date_str}_{uuid.uuid4().hex}{ext}"
            save_path = os.path.join(uploads_dir, unique_name)
            f.save(save_path)
            new_shot = Screenshot(date=date_str, file_path=f"uploads/{unique_name}")
            db.session.add(new_shot)
        else:
            flash(f"Invalid file type: {f.filename}")

    # update day-level PnL = sum of trade_pnl
    db.session.flush()
    day.pnl = sum(t.trade_pnl for t in day.trades)
    db.session.commit()

    flash("Trade added!")
    return redirect(url_for("show_day", date_str=date_str))

###############################################################################
# MULTI–TRADE: EDIT AN EXISTING TRADE
###############################################################################
@app.route("/edit_trade/<int:trade_id>", methods=["POST"])
def edit_trade(trade_id):
    trade = Trade.query.get(trade_id)
    if not trade:
        flash("Trade not found.")
        return redirect(url_for("home"))

    # Update fields from form
    side = request.form.get("side", "").lower()
    ticker = request.form.get("ticker", "").strip().upper()
    trade_type = request.form.get("trade_type", "").strip()
    trade_notes = request.form.get("trade_notes", "").strip()

    entry_price = parse_float(request.form.get("entry_price", "0"))
    exit_price = parse_float(request.form.get("exit_price", "0"))
    contract_count = parse_float(request.form.get("contract_count", "1"))

    trade.side = side
    trade.ticker = ticker
    trade.trade_type = trade_type
    trade.trade_notes = trade_notes
    trade.entry_price = entry_price
    trade.exit_price = exit_price
    trade.contract_count = contract_count

    # Recalculate the main trade PnL
    ticker_info = PRODUCT_DATA.get(ticker, None)
    calc_pnl = get_multiplier(ticker_info, side)
    main_pnl = calc_pnl(entry_price, exit_price, contract_count)
    
    # Recalculate scale events PnL from scratch
    scale_total = 0
    for scale in trade.scale_events:
        scale_total += calc_pnl(entry_price, scale.scale_price, scale.scale_contracts)
    
    # Set the trade's total PnL as the sum of main PnL and the recalculated scale events PnL
    trade.trade_pnl = main_pnl + scale_total

    # Optional: process any new screenshots (your existing code)

    # Recalculate the day-level PnL for the day that contains this trade
    day = DayRecord.query.get(trade.date)
    if day:
        day.pnl = sum(t.trade_pnl for t in day.trades)

    db.session.commit()
    flash("Trade updated!")
    return redirect(url_for("show_day", date_str=trade.date))

###############################################################################
# ADD SCALE EVENT (Optional)
###############################################################################
@app.route("/add_scale_event/<int:trade_id>", methods=["POST"])
def add_scale_event(trade_id):
    trade = Trade.query.get(trade_id)
    if not trade:
        flash("Invalid trade.")
        return redirect(url_for("home"))

    scale_price_val = parse_float(request.form.get("scale_price", "0"))
    scale_contracts_val = parse_float(request.form.get("scale_contracts", "0"))

    if scale_contracts_val != 0:
        new_scale = ScaleEvent(
            trade_id=trade.id,
            scale_price=scale_price_val,
            scale_contracts=int(scale_contracts_val)
        )
        db.session.add(new_scale)

        ticker_info = PRODUCT_DATA.get(trade.ticker, None)
        calc_pnl = get_multiplier(ticker_info, trade.side)
        partial_pnl = calc_pnl(trade.entry_price, scale_price_val, scale_contracts_val)
        trade.trade_pnl += partial_pnl

        day = DayRecord.query.get(trade.date)
        if day:
            db.session.flush()
            day.pnl = sum(t.trade_pnl for t in day.trades)

        db.session.commit()
        flash("Scale event added!")

    return redirect(url_for("show_day", date_str=trade.date))

###############################################################################
# ERROR HANDLERS
###############################################################################
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(debug=True)
