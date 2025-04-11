# app.py
from flask import Flask, render_template, request, redirect, session, url_for
from flask_session import Session
from auth import auth_bp
from email_template import generate_email_variants
from email_utils import send_email, save_draft, schedule_individual_email, schedule_batch_emails,schedule_all_at_once,get_scheduled_emails,fetch_replies
import os
import datetime
import json

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'  # or 'redis', 'sqlalchemy', etc.
Session(app)
app.secret_key = os.urandom(24)
app.register_blueprint(auth_bp)

@app.route('/')
def login():
    if 'credentials' in session:
        print("hii")
        print(session)
        return redirect(url_for('founder_form'))
    return render_template('login.html')

@app.route('/form', methods=['GET', 'POST'])
def founder_form():
    if request.method == 'POST':
        session['founder_data'] = request.form.to_dict()
        return redirect(url_for('generate_emails'))
    return render_template('form.html')

@app.route('/generate_emails')
def generate_emails():
    founder_data = session.get('founder_data')
    if not founder_data:
        return redirect(url_for('founder_form'))

    # Optional: show loading page while processing
    # This only helps if you use JavaScript to poll or wait
    # return render_template("loading.html")

    email_variants = generate_email_variants(founder_data)
    session['email_variants'] = email_variants
    return redirect(url_for('preview_emails'))


@app.route('/preview', methods=['GET', 'POST'])
def preview_emails():
    if request.method == 'POST':
        selected_variant = request.form.get('selected_variant')
        email_variants = session.get('email_variants', {})
        selected_email = email_variants.get(selected_variant)
        if selected_email:
            session['selected_email'] = selected_email
            return redirect(url_for('final_step'))  # or url_for('edit_email') if that's next
        else:
            return redirect(url_for('preview_emails'))
    return render_template("preview.html", emails=session.get('email_variants', {}))


@app.route('/edit_email', methods=['POST'])
def edit_email_redirect():
    selected = request.form.get('selected_variant')
    return redirect(url_for('edit_email', variant=selected))

@app.route('/edit/<variant>', methods=['GET', 'POST'])
def edit_email(variant):
    email = session['email_variants'].get(variant)
    if not email:
        return "Invalid email variant", 404

    if request.method == 'POST':
        session['selected_email'] = {
            'subject': request.form['subject'],
            'body': request.form['body']
        }
        return redirect(url_for('finalize_email'))

    return render_template("edit.html", subject=email['subject'], body=email['body'])

@app.route("/finalize", methods=["GET", "POST"])
def finalize_email():
    if 'selected_email' not in session:
        return redirect(url_for("preview_emails"))

    subject = session['selected_email'].get('subject', '')
    body_template = session['selected_email'].get('body', '')

    if request.method == "POST":
        if "credentials" not in session:
            return redirect(url_for("auth.login"))

        investors_json = request.form.get("investors_json", "[]")
        try:
            investors = json.loads(investors_json)
            if not investors:
                return "No investors provided.", 400
        except json.JSONDecodeError:
            return "Invalid investor data.", 400

        action = request.form.get("action")

        # Create personalized email for each investor
        personalized_emails = []
        for investor in investors:
            name = investor["name"]
            email = investor["email"]
            personalized_body = body_template.replace("[Investor Name]", name)
            personalized_emails.append({"email": email, "body": personalized_body})

        if action == "send":
            for entry in personalized_emails:
                send_email(subject, entry["body"], [entry["email"]])
            return redirect(url_for("finalize_email"))

        elif action == "draft":
            for entry in personalized_emails:
                save_draft(subject, entry["body"], [entry["email"]])
            return redirect(url_for("finalize_email"))

        elif action == "schedule":
            schedule_type = request.form.get("schedule_type")

            if schedule_type == "batch":
                batch_count = int(request.form.get("batch_count", 10))
                batches = [personalized_emails[i:i + batch_count] for i in range(0, len(personalized_emails), batch_count)]
                for day_offset, batch in enumerate(batches):
                    run_time = datetime.datetime.now() + datetime.timedelta(days=day_offset)
                    for entry in batch:
                        schedule_individual_email(subject, entry["body"], entry["email"], run_time)

            elif schedule_type == "fixed_time":
                scheduled_time_str = request.form.get("scheduled_time")
                try:
                    scheduled_time = datetime.datetime.fromisoformat(scheduled_time_str)
                except ValueError:
                    return "Invalid date/time format.", 400
                for entry in personalized_emails:
                    schedule_individual_email(subject, entry["body"], entry["email"], scheduled_time)

            else:
                return "Invalid schedule type selected.", 400

            return redirect(url_for("finalize_email"))
    # GET request
    email = {
        "subject": subject,
        "body": body_template,
    }
    return render_template("finalize.html", email=email)

@app.route("/dashboard")
def dashboard():
    scheduled_emails = get_scheduled_emails()
    sent_emails = []
    if os.path.exists("sent_log.json"):
        with open("sent_log.json", "r") as f:
            sent_emails = json.load(f)
    replies = fetch_replies(session.get("credentials", {}))

    return render_template("dashboard.html", scheduled_emails=scheduled_emails, sent_emails=sent_emails, replies=replies)

@app.template_filter("datetimeformat")
def datetimeformat(value):
    try:
        # Convert milliseconds (Gmail API style) to readable date-time
        return datetime.datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return value  # fallback if parsing fails
if __name__ == '__main__':
    app.run(debug=True)