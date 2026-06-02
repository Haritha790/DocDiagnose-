from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from dotenv import load_dotenv
from ml_logic import get_specialty_for_symptom
from geopy.geocoders import OpenCage
from geopy.distance import geodesic

import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # Add secret key for session

# MongoDB setup
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["docdetails"]
doctors_collection = db["doctors"]
users_collection = db["users"]

print("DB Connected:", db.list_collection_names())

@app.route("/")
def home():
    return redirect("/signup")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        users_collection.insert_one({
            "username": username,
            "email": email,
            "password": password
        })

        return redirect("/login")
    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = users_collection.find_one({"username": username, "password": password})
        if user:
            session['email'] = user['email']  # Store session to keep user logged in
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Try again.")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect('/login')
    doctors = doctors_collection.find()
    return render_template('dashboard.html', doctors=doctors)

@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    if 'email' not in session:
        return redirect('/login')

    if request.method == 'GET':
        return render_template('recommend.html')

    user_symptom = request.form['symptom']
    user_address = request.form['location']

    specialty = get_specialty_for_symptom(user_symptom)

    geolocator = OpenCage(os.getenv("OPENCAGE_API_KEY"))
    user_location = geolocator.geocode(user_address)
    if not user_location:
        return render_template('recommend.html', error="Could not find your location. Please be more specific.", symptom=user_symptom, location=user_address)

    user_coords = (user_location.latitude, user_location.longitude)

    doctor_matches = list(doctors_collection.find({"specialty": specialty, "available": True}))

    closest_doctor = None
    min_distance = float('inf')

    for doc in doctor_matches:
        if 'latitude' not in doc or 'longitude' not in doc:
            full_address = f"{doc['address']}, {doc['city']}, {doc['state']}, {doc['pincode']}"
            location = geolocator.geocode(full_address)
            if location:
                doc['latitude'] = location.latitude
                doc['longitude'] = location.longitude
                doctors_collection.update_one({'_id': doc['_id']}, {'$set': {
                    'latitude': location.latitude,
                    'longitude': location.longitude
                }})
            else:
                continue

        doctor_coords = (doc['latitude'], doc['longitude'])
        distance_km = geodesic(user_coords, doctor_coords).kilometers

        if distance_km < min_distance:
            min_distance = distance_km
            closest_doctor = doc

    if closest_doctor:
        return render_template(
            'recommend.html',
            doctor=closest_doctor,
            symptom=user_symptom,
            specialty=specialty,
            distance=round(min_distance, 2),
            location=user_address
        )
    else:
        return render_template(
            'recommend.html',
            error=f"No available {specialty}s found near your location.",
            symptom=user_symptom,
            location=user_address
        )

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == "__main__":
    print("Flask app is running! Visit http://127.0.0.1:5000")
    app.run(debug=True)

