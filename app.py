from flask import Flask, render_template, request, redirect, session, url_for, jsonify, send_file
from mongodb_connection import get_db
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from chatbot import get_bot_response
from ml_chatbot import predict_intent
import os
from werkzeug.utils import secure_filename
from email.mime.text import MIMEText
import smtplib
import uuid
import qrcode
from io import BytesIO
import base64
import pandas as pd
import threading
import time
from datetime import datetime, timedelta
import re

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ==========================
# DATABASE CONFIG (MONGODB)
# ==========================
def get_db_coonection():
    # Returning the database object directly for simpler use
    return get_db()

# ==========================
# START PAGE
# ==========================
@app.route("/")
def start():
    return redirect(url_for("login"))

# ==========================
# HOME
# ==========================
@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
        
    db = get_db_coonection()
    
    latest_event = db.events.find_one(sort=[("id", pymongo.DESCENDING)])
    
    events = list(db.events.find({"tech_fest_id": None}).sort("event_date", pymongo.DESCENDING).limit(5))
    
    competitions = list(db.competitions.find({}))
    
    tech_fests = list(db.tech_fests.find({"show_on_home": True}))
    
    stats_events_count = db.events.count_documents({})
    
    stats_users_count = db.registrations_new.count_documents({})
    
    feedbacks = list(db.event_feedback.find({}, {"message": 1}))
    
    total_rating = 0
    valid_reviews = 0
    import re
    for f in feedbacks:
        msg = f['message']
        if msg:
            match = re.search(r'Overall Rating:\s*(\d+(\.\d+)?)/5', msg)
            if match:
                total_rating += float(match.group(1))
                valid_reviews += 1
                
    stats_avg_rating = round(total_rating / valid_reviews, 1) if valid_reviews > 0 else 0.0
    
    
    return render_template("index.html", 
        username=session["user"], 
        latest_event=latest_event, 
        events=events, 
        competitions=competitions, 
        tech_fests=tech_fests,
        stats_events_count=stats_events_count,
        stats_users_count=stats_users_count,
        stats_avg_rating=stats_avg_rating)

# ==========================
# USER PROFILE
# ==========================
@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("login"))
        
    username = session["user"]
    db = get_db_coonection()
    
    reg_cnt = db.registrations_new.count_documents({"name": username})
    fb_cnt = db.event_feedback.count_documents({"username": username})
    
    points = (reg_cnt * 10) + (fb_cnt * 20)
    if points >= 100:
        badge = "👑 Campus Legend"
    elif points >= 30:
        badge = "🔥 Event Enthusiast"
    else:
        badge = "🌱 Explorer"
        
    # Leaderboard (simplified)
    all_users_cursor = db.users.find({})
    leaderboard = []
    for u in all_users_cursor:
        u_name = u["username"]
        u_reg = db.registrations_new.count_documents({"name": u_name})
        u_fb = db.event_feedback.count_documents({"username": u_name})
        pts = (u_reg * 10) + (u_fb * 20)
        leaderboard.append({"username": u_name, "pts": pts})
    
    leaderboard.sort(key=lambda x: x["pts"], reverse=True)
    user_rank = 1
    for i, u in enumerate(leaderboard):
        if u['username'] == username:
            user_rank = i + 1
            break

    # registrations with event info
    registrations = []
    regs = db.registrations_new.find({"name": username})
    for r in regs:
        event = db.events.find_one({"id": r["event_id"]})
        category = db.event_categories.find_one({"id": r["category_id"]})
        if event and category:
            r.update({
                "event_name": event["name"],
                "description": event["description"],
                "event_date": event["event_date"],
                "venue": event["venue"],
                "price": event["price"],
                "category_name": category["category_name"]
            })
            registrations.append(r)
    
    all_events = list(db.events.find({}))
    
    return render_template("profile.html", username=username, registrations=registrations, points=points, badge=badge, user_rank=user_rank, all_events=all_events)

# ==========================
# FEEDBACK & NOTIFICATIONS
# ==========================
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if "user" not in session:
        return redirect(url_for("login"))
        
    username = session["user"]
    db = get_db_coonection()
    
    # Get all events the user is registered for
    # In MongoDB, we'll manually join or just find the registrations and then the events
    attended_regs = list(db.registrations_new.find({"name": username}))
    event_ids = [r["event_id"] for r in attended_regs]
    attended_events = list(db.events.find({"id": {"$in": event_ids}}))
    
    if request.method == "POST":
        event_id = request.form.get("event_id")
        
        # Combine 8 feedback questions into single message block
        overall_rating = request.form.get("overall_rating", "")
        org_rating = request.form.get("org_rating", "")
        content_rating = request.form.get("content_rating", "")
        venue_rating = request.form.get("venue_rating", "")
        recommend = request.form.get("recommend", "")
        liked_most = request.form.get("liked_most", "")
        improvements = request.form.get("improvements", "")
        suggestions = request.form.get("suggestions", "")
        
        message = f"1. Overall Rating: {overall_rating}/5\n" \
                  f"2. Organization: {org_rating}/5\n" \
                  f"3. Content Quality: {content_rating}/5\n" \
                  f"4. Venue: {venue_rating}/5\n" \
                  f"5. Recommend: {recommend}\n" \
                  f"6. Liked Most: {liked_most}\n" \
                  f"7. Enhancements: {improvements}\n" \
                  f"8. Suggestions: {suggestions}"
        
        if event_id:
            event_id = int(event_id)
            db.event_feedback.insert_one({"event_id": event_id, "username": username, "message": message})
            
            # Send automated Thank You Email
            user_data = db.registrations_new.find_one({"event_id": event_id, "name": username})
            
            event_data = db.events.find_one({"id": event_id})
            
            if user_data and event_data:
                try:
                    from email.mime.text import MIMEText
                    import smtplib

                    
                    email = user_data["email"]
                    event_name = event_data["name"]
                    
                    msg_body = f"Hi {username},\n\nThank you so much for attending '{event_name}' and leaving your valuable feedback!\n\nWe appreciate your input and hope to see you at future events.\n\nBest Regards,\nEventopia Team"
                    msg = MIMEText(msg_body)
                    msg["Subject"] = "Thank You for Your Feedback!"
                    msg["From"] = "atharvkudtarkar4406@gmail.com"
                    msg["To"] = email
                    
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login("atharvkudtarkar4406@gmail.com", "dxnt tdxx egdg sgua")
                    server.send_message(msg)
                    server.quit()
                except Exception as e:
                    print("Feedback email failed:", e)
            
    return render_template("feedback.html", success=False, attended_events=attended_events)

@app.route("/notifications")
def notifications():
    username = session.get("user")
    db = get_db_coonection()
    notifs = list(db.notifications.find({"$or": [{"username": username}, {"username": None}]}).sort("id", pymongo.DESCENDING))
    
    return render_template("notifications.html", notifications=notifs)

# ==========================
# API NOTIFICATIONS (AI/TOAST)
# ==========================
@app.route("/api/add_notification", methods=["POST"])
def api_add_notification():
    data = request.get_json()
    if data and "title" in data and "message" in data:
        username = data.get("username", None)
        db = get_db_coonection()
        db.notifications.insert_one({"title": data["title"], "message": data["message"], "username": username})
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/api/latest_notification", methods=["GET"])
def api_latest_notification():
    username = session.get("user")
    db = get_db_coonection()
    notif = db.notifications.find_one({"$or": [{"username": username}, {"username": None}]}, sort=[("id", pymongo.DESCENDING)])
    if notif:
        return jsonify({"id": str(notif.get("id")), "title": notif["title"], "message": notif["message"]})
    return jsonify({})

@app.route("/api/unread_notifications_count", methods=["GET"])
def api_unread_notifications_count():
    username = session.get("user")
    if not username:
        return jsonify({"count": 0})
        
    db = get_db_coonection()
    count = db.notifications.count_documents({"$or": [{"username": username}, {"username": None}]})
    return jsonify({"count": count})

# ==========================
# LOGIN
# ==========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db_coonection()
        user = db.users.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user"] = user["username"]

            # -------------------------
            # ADD TO ACTIVE USERS
            # -------------------------
            db.active_users.update_one(
                {"username": user["username"]},
                {"$set": {"login_time": datetime.now()}},
                upsert=True
            )
            return redirect(url_for("home"))

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

# ==========================
# REGISTER
# ==========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        db = get_db_coonection()
        if db.users.find_one({"username": username}):
            return render_template("register.html", error="Username already exists")

        db.users.insert_one({"username": username, "password": password})
        return redirect(url_for("login"))

    return render_template("register.html")

# ==========================
# LOGOUT
# ==========================
@app.route("/logout")
def logout():
    username = session.get("user")
    db = get_db_coonection()
    db.active_users.delete_one({"username": username})
    session.clear()
    return redirect(url_for("login"))

# ==========================
# CHATBOT
# ==========================
@app.route("/ask_ai", methods=["POST"])
def ask_ai():
    try:
        data = request.get_json()
        message = data.get("message","")

        response = get_bot_response(message)

        return response

    except Exception as e:
        print("AI ERROR:", e)
        return jsonify({"response": "AI assistant error"})

# ==========================
# EVENTS PAGE
# ==========================
@app.route("/events")
def events_page():
    db = get_db_coonection()

    events = list(db.events.find({"tech_fest_id": None}))
    competitions = list(db.competitions.find({}))
    tech_fests = list(db.tech_fests.find({}))

    return render_template("events.html", events=events, competitions=competitions, tech_fests=tech_fests)

# ==========================
# TECH FEST DETAILS
# ==========================
@app.route("/techfest/<int:id>")
def techfest_details(id):
    db = get_db_coonection()
    techfest = db.tech_fests.find_one({"id": id})
    
    if not techfest:
        return redirect("/events")
        
    events = list(db.events.find({"tech_fest_id": id}))
    return render_template("techfest.html", techfest=techfest, events=events)

# ==========================
# EVENT CATEGORIES
# ==========================
@app.route("/event_categories/<int:event_id>")
def event_categories(event_id):
    db = get_db_coonection()

    categories = list(db.event_categories.find({"event_id": event_id}))
    event = db.events.find_one({"id": event_id})
    past_events = list(db.events.find({"image": {"$ne": None}, "id": {"$ne": event_id}}).sort("event_date", pymongo.DESCENDING).limit(3))

    return render_template("event_details.html", categories=categories, event=event, past_events=past_events)

def generate_ticket_qr(ticket_id):
    os.makedirs("static/tickets", exist_ok=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(ticket_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    filepath = f"static/tickets/{ticket_id}.png"
    img.save(filepath)
    return filepath

def finalize_registration(category, event, names, emails, phones, team_name, transaction_id=None):
    from flask import render_template
    db = get_db_coonection()

    leader_name = names[0]
    leader_email = emails[0]
    leader_phone = phones[0]
    ticket_ids = []

    for i in range(len(names)):
        ticket_id = uuid.uuid4().hex[:12].upper()
        ticket_ids.append(ticket_id)
        generate_ticket_qr(ticket_id)

        status = 'Registered'
        payment_status = 'Completed' if transaction_id or not event.get('price') else 'Pending'

        db.registrations_new.insert_one({
            "event_id": category["event_id"],
            "category_id": category["id"],
            "name": names[i],
            "email": emails[i],
            "phone": phones[i],
            "team_name": team_name,
            "ticket_id": ticket_id,
            "status": status,
            "payment_status": payment_status,
            "transaction_id": transaction_id
        })

    # APP NOTIFICATION 
    notification_title = "New Event Registration ⭐"
    notification_message = f"{leader_name} just registered for {event['name']} ({category['category_name']})!"
    if team_name:
         notification_message = f"Team '{team_name}' just registered for {event['name']} ({category['category_name']})!"
    
    # ... (skipping some logic for brevity in this replace call, will keep the chatbot part)
    db.notifications.insert_one({
        "title": notification_title,
        "message": notification_message,
        "username": leader_name
    })

    # SMS NOTIFICATION
    try:
        from twilio.rest import Client
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")

        if twilio_sid and twilio_token and twilio_phone:
            client = Client(twilio_sid, twilio_token)
            sms_body = f"Eventopia Quick Update: {notification_message}"
            formatted_phone = leader_phone if leader_phone.startswith('+') else f"+91{leader_phone}"
            client.messages.create(body=sms_body, from_=twilio_phone, to=formatted_phone)
    except Exception as e:
        print("SMS sending failed:", e)

    # SEND EMAIL
    teammates_text = "\n".join([f"- {names[i]} ({emails[i]}) [Ticket ID: {ticket_ids[i]}]" for i in range(len(names))])
    message = f"""
Congratulations {leader_name}!

Your registration is confirmed. Please keep your Ticket IDs safe for scanning at the venue.

Event: {event['name']}
Category: {category['category_name']}
{"Team Name: " + team_name if team_name else ""}
Venue: {event['venue']}
Date: {event['event_date']}
Time: {event['event_time']}
Transaction ID: {transaction_id if transaction_id else 'N/A (Free/Pending)'}

Registered Members & Tickets:
{teammates_text}

We look forward to seeing you there!

Eventopia Team
"""
    try:
        from email.mime.text import MIMEText
        import smtplib
        msg = MIMEText(message)
        msg["Subject"] = "Event Registration Confirmed (Tickets Inside!)"
        msg["From"] = "atharvkudtarkar4406@gmail.com"
        msg["To"] = leader_email
        server = smtplib.SMTP("smtp.gmail.com",587)
        server.starttls()
        server.login("atharvkudtarkar4406@gmail.com","dxnt tdxx egdg sgua")
        server.send_message(msg)
        server.quit()
    except:
        print("Email sending failed")

    return render_template(
        "registration_success.html",
        event=event,
        category=category,
        name=leader_name
    )

@app.route("/register/<int:category_id>", methods=["GET","POST"])
def register_event(category_id):
    db = get_db_coonection()

    category = db.event_categories.find_one({"id": category_id})
    if not category:
        return redirect("/events")

    event = db.events.find_one({"id": category["event_id"]})

    if request.method == "POST":
        names = request.form.getlist("name[]")
        emails = request.form.getlist("email[]")
        phones = request.form.getlist("phone[]")
        team_name = request.form.get("team_name") if request.form.get("team_name") else None

        # Check existing
        if emails:
            existing_registrations = list(db.registrations_new.find({
                "event_id": category["event_id"],
                "email": {"$in": emails}
            }))
            
            if existing_registrations:
                duplicate_emails = list(set([row['email'] for row in existing_registrations]))
                error_msg = f"Registration failed! The following email(s) are already registered for this event: {', '.join(duplicate_emails)}."
                return render_template("registration.html", category=category, event=event, error=error_msg)

        price = event.get('price')
        if price and int(price) > 0:
            # Save to session and redirect to checkout
            session['checkout_data'] = {
                'category': category,
                'event': event,
                'names': names,
                'emails': emails,
                'phones': phones,
                'team_name': team_name,
                'amount': int(price) * len(names) # charge per person
            }
            return redirect(url_for('checkout'))
        else:
            # Free registration
            return finalize_registration(category, event, names, emails, phones, team_name)

    return render_template("registration.html", category=category, event=event)

@app.route("/checkout")
def checkout():
    if 'checkout_data' not in session:
        return redirect('/events')
        
    data = session['checkout_data']
    amount = data['amount']
    # Create UPI Intent string (generic example)
    upi_id = "eventopia@okhdfcbank"
    merchant_name = "Eventopia"
    upi_url = f"upi://pay?pa={upi_id}&pn={merchant_name}&am={amount}&cu=INR"
    
    # Generate QR Code dynamically
    qr = qrcode.QRCode(version=1, box_size=5, border=3)
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_code_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return render_template("checkout.html", amount=amount, event_name=data['event']['name'], upi_url=upi_url, qr_code_data=qr_code_b64)

@app.route("/process_payment", methods=["POST"])
def process_payment():
    if 'checkout_data' not in session:
        return redirect('/events')
        
    transaction_id = request.form.get('transaction_id')
    data = session['checkout_data']
    
    res = finalize_registration(data['category'], data['event'], data['names'], data['emails'], data['phones'], data['team_name'], transaction_id)
    
    session.pop('checkout_data', None)
    return res


@app.route("/add_category", methods=["POST"])
def add_category():
    if "admin" not in session:
        return redirect("/admin_login")

    event_id = int(request.form["event_id"])
    category_name = request.form["category_name"]

    db = get_db_coonection()
    # Get last ID for simple auto-increment simulation
    last_cat = db.event_categories.find_one(sort=[("id", -1)])
    next_id = (last_cat["id"] + 1) if last_cat else 1
    
    db.event_categories.insert_one({
        "id": next_id,
        "event_id": event_id,
        "category_name": category_name
    })

    return redirect("/admin")
@app.route("/delete_event/<int:id>")
def delete_event(id):
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db_coonection()

    # get registered users to notify them before deleting
    registered_users = list(db.registrations_new.find({"event_id": id}))
    event_info = db.events.find_one({"id": id})
    event_name = event_info["name"] if event_info else "An event"

    if registered_users:
        notification_title = "Event Cancelled 🚫"
        notification_message = f"The event '{event_name}' has been cancelled. Your registration is removed."
        for user in registered_users:
            db.notifications.insert_one({
                "title": notification_title,
                "message": notification_message,
                "username": user["name"]
            })

    # delete registrations, categories, and event
    db.registrations_new.delete_many({"event_id": id})
    db.event_categories.delete_many({"event_id": id})
    db.events.delete_one({"id": id})

    return redirect("/admin")

@app.route("/delete_user/<int:id>")
def delete_user(id):
    if "admin" not in session:
        return redirect("/admin_login")
        
    reason = request.args.get("reason", "No reason provided.")
    db = get_db_coonection()
    
    reg = db.registrations_new.find_one({"id": id})
    if reg:
        event = db.events.find_one({"id": reg["event_id"]})
        event_name = event["name"] if event else "Unknown Event"
        
        db.registrations_new.delete_one({"id": id})
        
        # App Notification
        db.notifications.insert_one({
            "title": "Registration Cancelled ❌",
            "message": f"Your registration for '{event_name}' has been cancelled by the administrator. Reason: {reason}",
            "username": reg["name"]
        })
        
        # Email would go here (skipped for brevity)
        
    return redirect("/admin")

@app.route("/cancel_registration/<int:id>", methods=["POST"])
def cancel_registration(id):
    if "user" not in session:
        return redirect(url_for("login"))
        
    username = session["user"]
    
    conn = get_db_coonection()
    cursor = conn.cursor(dictionary=True)
    
    # Verify the registration belongs to this user
    cursor.execute("SELECT r.name, r.email, e.name as event_name FROM registrations_new r JOIN events e ON r.event_id = e.id WHERE r.id=%s AND r.name=%s", (id, username))
    reg = cursor.fetchone()
    
    if reg:
        cursor.execute("DELETE FROM registrations_new WHERE id=%s", (id,))
        conn.commit()
        
        # Send confirmation email
        try:
            from email.mime.text import MIMEText
            import smtplib

            
            msg = MIMEText(f"Hello {reg['name']},\n\nYou have successfully cancelled your registration for the event '{reg['event_name']}'.\n\nWe hope to see you at future events!\n\nBest Regards,\nEventopia")
            msg["Subject"] = "Registration Cancellation Confirmed"
            msg["From"] = "atharvkudtarkar4406@gmail.com"
            msg["To"] = reg["email"]
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login("atharvkudtarkar4406@gmail.com", "dxnt tdxx egdg sgua")
            server.send_message(msg)
            server.quit()
        except Exception as e:
            print("Failed to send user cancellation email:", e)

    cursor.close()
    conn.close()
    
    return redirect(url_for("profile"))
@app.route('/add_event', methods=['POST'])
def add_event():
    if "admin" not in session:
        return redirect("/admin_login")

    name = request.form['name']
    description = request.form['description']
    category = request.form['category']
    event_type = request.form.get('event_type', 'Individual')
    department = request.form.get('department')
    tech_fest_id = request.form.get('tech_fest_id')
    tech_fest_id = int(tech_fest_id) if tech_fest_id else None

    event_date = request.form['event_date']
    event_time = request.form['event_time']
    venue = request.form['venue']
    price = int(request.form.get('price', 0))

    image_file = request.files['image']
    filename = None
    if image_file and image_file.filename != "":
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image_file.save(image_path)

    db = get_db_coonection()
    last_event = db.events.find_one(sort=[("id", -1)])
    next_id = (last_event["id"] + 1) if last_event else 1

    db.events.insert_one({
        "id": next_id,
        "name": name,
        "description": description,
        "category": category,
        "department": department,
        "tech_fest_id": tech_fest_id,
        "event_date": event_date,
        "event_time": event_time,
        "venue": venue,
        "image": filename,
        "price": price,
        "event_type": event_type
    })

    # Auto add general category
    last_cat = db.event_categories.find_one(sort=[("id", -1)])
    next_cat_id = (last_cat["id"] + 1) if last_cat else 1
    db.event_categories.insert_one({
        "id": next_cat_id,
        "event_id": next_id,
        "category_name": "General Registration"
    })

    return redirect('/admin')

@app.route('/edit_event/<int:id>', methods=['GET', 'POST'])
def edit_event(id):
    if "admin" not in session:
        return redirect("/admin_login")
        
    conn = get_db_coonection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Get existing event name
        cursor.execute("SELECT name FROM events WHERE id=%s", (id,))
        event_info = cursor.fetchone()
        event_name = event_info["name"] if event_info else "An Event"

        event_date = request.form['event_date']
        event_time = request.form['event_time']
        price = request.form.get('price', 0)
        category = request.form.get('category')
        event_type = request.form.get('event_type', 'Individual')
        department = request.form.get('department')
        tech_fest_id = request.form.get('tech_fest_id')
        if not tech_fest_id:
            tech_fest_id = None
        
        cursor.execute("""
            UPDATE events 
            SET event_date=%s, event_time=%s, price=%s, category=%s, department=%s, tech_fest_id=%s, event_type=%s
            WHERE id=%s
        """, (event_date, event_time, price, category, department, tech_fest_id, event_type, id))
        
        # Add Notification for the update
        try:
            notification_title = "Event Rescheduled 🚨"
            notification_message = f"Heads up! '{event_name}' has been updated to {event_date} at {event_time}."
            cursor.execute("INSERT INTO notifications (title, message) VALUES (%s, %s)", (notification_title, notification_message))
        except Exception as e:
            print("Failed to add edit notification:", e)
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return redirect("/admin")
        
    cursor.execute("SELECT * FROM events WHERE id=%s", (id,))
    event = cursor.fetchone()
    
    cursor.execute("SELECT * FROM tech_fests")
    tech_fests = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if not event:
        return redirect("/admin")
        
    return render_template("edit_event.html", event=event, tech_fests=tech_fests)

@app.route('/add_competition', methods=['POST'])
def add_competition():
    if "admin" not in session:
        return redirect("/admin_login")

    name = request.form['name']
    comp_type = request.form['type']
    description = request.form['description']
    comp_date = request.form['competition_date']
    venue = request.form['venue']

    image_file = request.files.get('image')
    filename = None
    if image_file and image_file.filename != "":
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image_file.save(image_path)

    conn = get_db_coonection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO competitions 
        (name, type, description, competition_date, venue, image)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (name, comp_type, description, comp_date, venue, filename))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/admin')

@app.route('/add_tech_fest', methods=['POST'])
def add_tech_fest():
    if "admin" not in session:
        return redirect("/admin_login")

    name = request.form['name']
    department = request.form['department']
    description = request.form['description']
    fest_date = request.form['fest_date']
    venue = request.form['venue']

    show_on_home = True if request.form.get('show_on_home') else False

    image_file = request.files.get('image')
    filename = None
    if image_file and image_file.filename != "":
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image_file.save(image_path)

    conn = get_db_coonection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tech_fests 
        (name, department, description, fest_date, venue, image, show_on_home)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (name, department, description, fest_date, venue, filename, show_on_home))
    
    # Send Notification
    try:
        notification_title = "New Tech Fest Announced! 🚀"
        notification_message = f"The {department} department just announced {name}! Get ready for exciting sub-events."
        cursor.execute("INSERT INTO notifications (title, message) VALUES (%s, %s)", (notification_title, notification_message))
    except Exception as e:
        print("Notification failed:", e)

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/admin')

@app.route('/edit_tech_fest/<int:id>', methods=['GET', 'POST'])
def edit_tech_fest(id):
    if "admin" not in session:
        return redirect("/admin_login")
        
    conn = get_db_coonection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        description = request.form['description']
        fest_date = request.form['fest_date']
        venue = request.form['venue']
        show_on_home = True if request.form.get('show_on_home') else False
        
        cursor.execute("""
            UPDATE tech_fests 
            SET name=%s, department=%s, description=%s, fest_date=%s, venue=%s, show_on_home=%s
            WHERE id=%s
        """, (name, department, description, fest_date, venue, show_on_home, id))
        
        # Send Notification
        try:
            notification_title = "Tech Fest Updated ✏️"
            notification_message = f"Details for {name} have been updated. Check them out!"
            cursor.execute("INSERT INTO notifications (title, message) VALUES (%s, %s)", (notification_title, notification_message))
        except Exception as e:
            pass
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return redirect("/admin")
        
    cursor.execute("SELECT * FROM tech_fests WHERE id=%s", (id,))
    fest = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not fest:
        return redirect("/admin")
        
    return render_template("edit_tech_fest.html", fest=fest)

@app.route('/add_sub_event/<int:tech_fest_id>', methods=['GET'])
def add_sub_event(tech_fest_id):
    if "admin" not in session:
        return redirect("/admin_login")
        
    conn = get_db_coonection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM tech_fests WHERE id=%s", (tech_fest_id,))
    fest = cursor.fetchone()
    
    cursor.execute("SELECT * FROM tech_fests")
    all_tech_fests = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if not fest:
        return redirect("/admin")
    
    return render_template("add_sub_event.html", fest=fest, tech_fests=all_tech_fests)

@app.route("/delete_competition/<int:id>")
def delete_competition(id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_coonection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM competitions WHERE id=%s", (id,))
    conn.commit()
    
    cursor.close()
    conn.close()

    return redirect("/admin")

@app.route("/delete_tech_fest/<int:id>")
def delete_tech_fest(id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_coonection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tech_fests WHERE id=%s", (id,))
    conn.commit()
    
    cursor.close()
    conn.close()

    return redirect("/admin")
@app.route("/delete_category/<int:id>")
def delete_category(id):
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db_coonection()
    db.event_categories.delete_one({"id": id})
    return redirect("/admin")
@app.route("/admin_logout")
def admin_logout():
    session.clear()
    return redirect("/admin_login")

@app.route("/admin_login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        if email == "admin@gmail.com" and password == "1234":
            session.clear()
            session["admin"] = True
            return redirect("/admin")

    return render_template("admin_login.html")

@app.route("/admin/remove_system_user/<int:user_id>", methods=["POST"])
def remove_system_user(user_id):
    if "admin" not in session:
        return redirect("/admin_login")
        
    db = get_db_coonection()
    user = db.users.find_one({"id": user_id})
    
    if user:
        uname = user['username']
        db.active_users.delete_many({"username": uname})
        db.event_feedback.delete_many({"username": uname})
        db.notifications.delete_many({"username": uname})
        db.registrations_new.delete_many({"name": uname})
        db.users.delete_one({"id": user_id})
        
    return redirect("/admin")

# ==========================
# ADMIN PANEL
# ==========================
@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect("/admin_login")

    db = get_db_coonection()

    events = list(db.events.find({}))
    
    # Manual Join for Registrations
    users = []
    regs = list(db.registrations_new.find({}))
    for r in regs:
        event = db.events.find_one({"id": r["event_id"]})
        category = db.event_categories.find_one({"id": r["category_id"]})
        users.append({
            "id": r.get("id"),
            "name": r["name"],
            "email": r["email"],
            "event_name": event["name"] if event else "Unknown",
            "category_name": category["category_name"] if category else "Unknown"
        })

    # Categories with Event info
    categories = []
    cats = list(db.event_categories.find({}))
    for c in cats:
        event = db.events.find_one({"id": c["event_id"]})
        categories.append({
            "id": c["id"],
            "category_name": c["category_name"],
            "event_name": event["name"] if event else "Unknown"
        })

    # System Users with Last Login
    system_users_raw = list(db.users.find({}))
    system_users = []
    for u in system_users_raw:
        last_log = db.active_users.find_one({"username": u["username"]}, sort=[("login_time", -1)])
        system_users.append({
            "id": u.get("id"),
            "username": u["username"],
            "last_login": last_log["login_time"] if last_log else "Never"
        })
    
    competitions = list(db.competitions.find({}))
    tech_fests = list(db.tech_fests.find({}))

    return render_template(
        "admin.html",
        events=events,
        users=users,
        categories=categories,
        system_users=system_users,
        competitions=competitions,
        tech_fests=tech_fests
    )

@app.route("/admin_analytics")
def admin_analytics():
    if "admin" not in session:
        return redirect("/admin_login")
    return render_template("admin_analytics.html")

@app.route("/api/analytics_data")
def api_analytics_data():
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 403
        
    dept_filter = request.args.get("department", "All")
    
@app.route("/api/dashboard_stats")
def dashboard_stats():
    dept_filter = request.args.get("dept", "All")
    db = get_db_coonection()
    
    if dept_filter == "All":
        events = list(db.events.find({}))
    else:
        events = list(db.events.find({"department": dept_filter}))
    
    event_ids = [e['id'] for e in events]
    total_events = len(events)
    
    total_registrations = 0
    events_labels = []
    events_data = []
    
    for e in events:
        cnt = db.registrations_new.count_documents({"event_id": e["id"]})
        total_registrations += cnt
        name_label = e['name'][:20] + '...' if len(e['name']) > 20 else e['name']
        events_labels.append(name_label)
        events_data.append(cnt)
    
    active_users = db.active_users.count_documents({})
    
    # Dept counts (aggregation)
    pipeline = []
    if dept_filter != "All":
        pipeline.append({"$match": {"department": dept_filter}})
    pipeline.append({"$group": {"_id": "$department", "cnt": {"$sum": 1}}})
    
    dept_counts = list(db.events.aggregate(pipeline))
    dept_labels = [d['_id'] if d['_id'] else 'Unspecified' for d in dept_counts]
    dept_data = [d['cnt'] for d in dept_counts]
    
    return jsonify({
        "total_registrations": total_registrations,
        "total_events": total_events,
        "active_users": active_users,
        "events_labels": events_labels,
        "events_data": events_data,
        "dept_labels": dept_labels,
        "dept_data": dept_data
    })

@app.route("/request_event_feedback/<int:event_id>")
def request_event_feedback(event_id):
    if "admin" not in session:
        return redirect("/admin_login")
        
    db = get_db_coonection()
    event = db.events.find_one({"id": event_id})
    
    if event:
        users = list(db.registrations_new.find({"event_id": event_id}))
        for u in users:
            db.notifications.insert_one({
                "title": "Feedback Requested 📝",
                "message": f"We hope you enjoyed '{event['name']}'! Please visit the Feedback section to share your thoughts.",
                "username": u["name"]
            })
    
    return redirect("/admin")
# ==========================
# DOWNLOAD EXCEL
# ==========================
@app.route("/download_registrations")
def download_registrations():
    db = get_db_coonection()
    regs = list(db.registrations_new.find({}))
    data = []
    for r in regs:
        event = db.events.find_one({"id": r["event_id"]})
        category = db.event_categories.find_one({"id": r["category_id"]})
        data.append({
            "id": r.get("id"),
            "name": r["name"],
            "email": r["email"],
            "phone": r["phone"],
            "event_name": event["name"] if event else "N/A",
            "category_name": category["category_name"] if category else "N/A"
        })

    df = pd.DataFrame(data)
    file_path = "registrations.xlsx"
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)

@app.route("/admin/scan_ticket", methods=["GET", "POST"])
def admin_scan_ticket():
    if "admin" not in session:
        return redirect("/admin_login")
        
    message = None
    success = False
    
    if request.method == "POST":
        ticket_id = request.form.get("ticket_id")
        if ticket_id:
            ticket_id = ticket_id.strip()
            db = get_db_coonection()
            reg = db.registrations_new.find_one({"ticket_id": ticket_id})
            
            if reg:
                if reg.get('status') == 'Attended':
                    message = f"Ticket ({ticket_id}) was ALREADY marked as Attended!"
                else:
                    db.registrations_new.update_one({"ticket_id": ticket_id}, {"$set": {"status": "Attended"}})
                    message = f"Success! {reg['name']} is marked as Attended."
                    success = True
            else:
                message = "Invalid Ticket ID."
                
    return render_template("admin_scan.html", message=message, success=success)

# ==========================
# BACKGROUND REMINDERS (1 HOUR)
# ==========================
def parse_event_datetime(evt_date, evt_time_str):
    try:
        date_str = str(evt_date)
        evt_time_str = evt_time_str.strip().upper()
        
        if 'AM' in evt_time_str or 'PM' in evt_time_str:
            t = datetime.strptime(evt_time_str, '%I:%M %p').time()
        else:
            if len(evt_time_str.split(':')[0]) == 1:
                evt_time_str = "0" + evt_time_str
            t = datetime.strptime(evt_time_str, '%H:%M').time()
            
        return datetime.strptime(f"{date_str} {t.strftime('%H:%M:%S')}", '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print("Time parse error:", e)
        return None

def check_and_send_1h_reminders():
    while True:
        try:
            db = get_db_coonection()
            events = list(db.events.find({"reminder_1h_sent": {"$ne": True}}))
            
            now = datetime.now()
            for evt in events:
                if not evt.get('event_date') or not evt.get('event_time'):
                    continue
                    
                evt_dt = parse_event_datetime(evt['event_date'], evt['event_time'])
                if not evt_dt:
                    continue
                    
                time_diff = evt_dt - now
                if timedelta(seconds=0) < time_diff <= timedelta(hours=1):
                    regs = list(db.registrations_new.find({"event_id": evt['id']}))
                    if regs:
                        # Email logic would go here
                        pass
                    db.events.update_one({"id": evt['id']}, {"$set": {"reminder_1h_sent": True}})
        except Exception as e:
            print("Reminder thread error:", e)
        time.sleep(300)

# Start thread if not in werkzeug reloader parent process
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    reminder_thread = threading.Thread(target=check_and_send_1h_reminders, daemon=True)
    reminder_thread.start()

# ==========================
# RUN
# ==========================
if __name__ == "__main__":
    app.run(debug=True)