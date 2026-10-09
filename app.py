
from flask import Flask, render_template, request, redirect, session
from db import Base, engine, SessionLocal
import models
import PyPDF2
import docx
import json
import os
from ai import analyze_resume

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

Base.metadata.create_all(bind=engine)


# HOME
@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/login")


# SIGNUP
@app.route("/signup", methods=["GET", "POST"])
def signup():
    db = SessionLocal()

    try:
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            existing_user = (
                db.query(models.User)
                .filter_by(email=email)
                .first()
            )

            if existing_user:
                return "User already exists"

            user = models.User(email=email, password=password)
            db.add(user)
            db.commit()

            return redirect("/login")

        return render_template("signup.html")

    finally:
        db.close()


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    db = SessionLocal()

    try:
        if request.method == "POST":
            email = request.form.get("email")
            password = request.form.get("password")

            user = (
                db.query(models.User)
                .filter_by(email=email, password=password)
                .first()
            )

            if user:
                session["user"] = user.email
                return redirect("/dashboard")

            return "Invalid credentials"

        return render_template("login.html")

    finally:
        db.close()


# DASHBOARD
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect("/login")

    result = None

    if request.method == "POST":
        user_goal = request.form.get("role", "").strip()
        resume_text = request.form.get("resume", "").strip()
        file = request.files.get("file")

        if file and file.filename:
            filename = file.filename.lower()

            try:
                if filename.endswith(".pdf"):
                    pdf_reader = PyPDF2.PdfReader(file)

                    resume_text = "\n".join(
                        page.extract_text() or ""
                        for page in pdf_reader.pages
                    )

                elif filename.endswith(".docx"):
                    document = docx.Document(file)

                    resume_text = "\n".join(
                        paragraph.text
                        for paragraph in document.paragraphs
                    )

                else:
                    result = {
                        "error": "Please upload a PDF or DOCX file."
                    }

            except Exception as e:
                result = {"error": f"File reading error: {e}"}

        if result is None:
            if not resume_text:
                result = {"error": "Please paste or upload your resume."}

            elif not user_goal:
                result = {"error": "Please enter your career goal."}

            else:
                try:
                    result = analyze_resume(resume_text, user_goal)

                    db = SessionLocal()

                    try:
                        user = (
                            db.query(models.User)
                            .filter_by(email=session["user"])
                            .first()
                        )

                        if user:
                            report = models.Reports(
                                user_id=user.id,
                                resume_text=resume_text,
                                result=json.dumps(result)
                            )

                            db.add(report)
                            db.commit()

                    finally:
                        db.close()

                except Exception as e:
                    result = {"error": f"Analysis error: {e}"}

    return render_template(
        "dashboard.html",
        user=session["user"],
        result=result
    )


# HISTORY
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")

    db = SessionLocal()

    try:
        user = (
            db.query(models.User)
            .filter_by(email=session["user"])
            .first()
        )

        reports = []

        if user:
            reports = (
                db.query(models.Reports)
                .filter_by(user_id=user.id)
                .order_by(models.Reports.id.desc())
                .all()
            )

        return render_template("history.html", reports=reports)

    finally:
        db.close()


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
