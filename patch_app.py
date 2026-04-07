import os

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
if 'import uuid' not in content:
    content = content.replace('import smtplib', 'import smtplib\nimport uuid\nimport qrcode\nfrom io import BytesIO\nimport base64')

# Replace the entire register_event function
old_func_start = '@app.route("/register/<int:category_id>", methods=["GET","POST"])'
old_func_end = '@app.route("/add_category", methods=["POST"])'

# Find bounds
start_idx = content.find(old_func_start)
end_idx = content.find(old_func_end)

if start_idx != -1 and end_idx != -1:
    new_func = """
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
    conn = get_db_coonection()
    cursor = conn.cursor(dictionary=True)

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

        cursor.execute(\"\"\"
        INSERT INTO registrations_new(event_id,category_id,name,email,phone,team_name, ticket_id, status, payment_status, transaction_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        \"\"\",(category["event_id"],category['id'],names[i],emails[i],phones[i],team_name, ticket_id, status, payment_status, transaction_id))

    conn.commit()

    # APP NOTIFICATION 
    notification_title = "New Event Registration ⭐"
    notification_message = f"{leader_name} just registered for {event['name']} ({category['category_name']})!"
    if team_name:
         notification_message = f"Team '{team_name}' just registered for {event['name']} ({category['category_name']})!"
    
    try:
        from chatbot import model
        if model:
            prompt_name = team_name if team_name else leader_name
            prompt = f"Write a vibrant, hyped 1-sentence announcement for a college portal that a student/team named '{prompt_name}' just registered for '{event['name']}' (module: '{category['category_name']}'). Use emojis. No quotes."
            response = model.generate_content(prompt)
            if response and response.text:
                notification_message = response.text.strip()
    except:
        pass 

    try:
        cursor.execute("INSERT INTO notifications (title, message, username) VALUES (%s, %s, %s)", (notification_title, notification_message, leader_name))
        conn.commit()
    except Exception as e:
        print("Notification insert failed:", e)

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
    teammates_text = "\\n".join([f"- {names[i]} ({emails[i]}) [Ticket ID: {ticket_ids[i]}]" for i in range(len(names))])
    message = f\"\"\"
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
\"\"\"
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

    cursor.close()
    conn.close()

    return render_template(
        "registration_success.html",
        event=event,
        category=category,
        name=leader_name
    )

@app.route("/register/<int:category_id>", methods=["GET","POST"])
def register_event(category_id):
    conn = get_db_coonection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM event_categories WHERE id=%s",(category_id,))
    category = cursor.fetchone()

    cursor.execute("SELECT * FROM events WHERE id=%s",(category["event_id"],))
    event = cursor.fetchone()

    if request.method == "POST":
        names = request.form.getlist("name[]")
        emails = request.form.getlist("email[]")
        phones = request.form.getlist("phone[]")
        team_name = request.form.get("team_name") if request.form.get("team_name") else None

        # Check existing
        if emails:
            format_strings = ','.join(['%s'] * len(emails))
            cursor.execute(f"SELECT email, name FROM registrations_new WHERE event_id=%s AND email IN ({format_strings})",
                           [category["event_id"]] + emails)
            existing_registrations = cursor.fetchall()
            
            if existing_registrations:
                duplicate_names = [row['name'] for row in existing_registrations]
                error_msg = f"Registration failed! Members already registered: {', '.join(duplicate_names)}."
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
            cursor.close()
            conn.close()
            return redirect(url_for('checkout'))
        else:
            # Free registration
            res = finalize_registration(category, event, names, emails, phones, team_name)
            cursor.close()
            conn.close()
            return res

    cursor.close()
    conn.close()
    return render_template("registration.html",category=category, event=event)

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

"""
    
    content = content[:start_idx] + new_func + '\n' + content[end_idx:]
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patch applied to app.py successfully!")
else:
    print("Failed to find bounds in app.py")

