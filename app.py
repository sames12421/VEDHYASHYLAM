from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import json
import requests
from werkzeug.utils import secure_filename
from datetime import datetime
import sqlite3
import csv
import pandas as pd
import re
from difflib import SequenceMatcher
from flask import session
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
import io
from datetime import datetime
import time
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, session
app = Flask(__name__)
app.secret_key = 'namaste_icd11_integration_2024'


# ==================== SIMPLE VOICE CHATBOT ====================

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyC_WXI8fi4EqedWNoaMdbMYocPW16d2ybw"  # Replace with your actual key
genai.configure(api_key=GEMINI_API_KEY)


# Configuration
UPLOAD_FOLDER = 'uploads'
MAPPING_FOLDER = 'mappings'
ALLOWED_EXTENSIONS = {'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAPPING_FOLDER'] = MAPPING_FOLDER

# Create directories
for system in ['ayurveda', 'siddha', 'unani']:
    os.makedirs(os.path.join(UPLOAD_FOLDER, system), exist_ok=True)
os.makedirs(MAPPING_FOLDER, exist_ok=True)








def get_gemini_response(prompt):
    """Get response from Gemini API for healthcare questions only"""
    full_prompt = (
        f"You are a professional healthcare assistant. "
        f"Answer ONLY questions related to: "
        f"1. Medical symptoms and conditions "
        f"2. Medications and treatments "
        f"3. Nutrition and diet advice "
        f"4. Exercise and fitness guidance "
        f"5. Mental health "
        f"6. Doctor appointments and healthcare services "
        f"7. General health advice "
        f"8. Prescription information "
        f"\n\n"
        f"If the question is NOT related to healthcare or medicine, reply politely: "
        f"'I'm sorry, I can only answer healthcare-related questions. Please ask about medical symptoms, medications, nutrition, exercise, or general health advice.'"
        f"\n\n"
        f"IMPORTANT: Always remind users to consult with healthcare professionals for personalized medical advice. "
        f"User asked: {prompt}"
        f"\n\n"
        f"Answer in a clear, concise manner (2-3 sentences maximum). "
        f"Be professional but friendly."
    )
    
    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return "I'm having trouble connecting to the medical database. Please try again."

def get_gemini_response_with_retry(prompt, max_retries=2):
    """Retry Gemini API call if it fails"""
    for attempt in range(max_retries):
        try:
            return get_gemini_response(prompt)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
            else:
                raise e
    return "I'm currently unable to process medical queries. Please try again later."

@app.route("/api/health-chatbot", methods=["POST"])
def health_chatbot():
    """Voice-enabled healthcare chatbot endpoint"""
    try:
        data = request.get_json()
        user_text = data.get("text", "").strip()
        
        if not user_text:
            return jsonify({
                'reply': "Please ask a healthcare-related question.",
                'error': False
            })
        
        # Check for greetings
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        if any(greet in user_text.lower() for greet in greetings):
            return jsonify({
                'reply': "Hello! I'm your Vedashayam Health Assistant. How can I help you with your health today?",
                'error': False
            })
        
        # Check for goodbye
        if "bye" in user_text.lower() or "thank you" in user_text.lower() or "thanks" in user_text.lower():
            return jsonify({
                'reply': "You're welcome! Remember to consult with healthcare professionals for personalized advice. Take care!",
                'error': False
            })
        
        # Get response from Gemini
        bot_response = get_gemini_response_with_retry(user_text)
        
        return jsonify({
            'reply': bot_response,
            'error': False
        })
        
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        return jsonify({
            'reply': "I'm experiencing technical difficulties. Please try again.",
            'error': True
        })






def add_manual_mappings():
    """Add manual mappings for codes that didn't map automatically"""
    manual_mappings = [
        # Format: (namaste_code, icd11_code, confidence_score)
        ('AYU099', 'XM0RM3', 0.95),  # Force map specific codes
        ('SID088', 'XM1RT4', 0.90),
    ]
    
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    for namaste_code, icd11_code, confidence in manual_mappings:
        cursor.execute('''
            INSERT OR REPLACE INTO intelligent_mappings 
            (namaste_code, icd11_code, confidence_score, mapping_method)
            VALUES (?, ?, ?, ?)
        ''', (namaste_code, icd11_code, confidence, 'manual_override'))
    
    conn.commit()
    conn.close()
    print(f"✅ Added {len(manual_mappings)} manual mappings")
# ==================== BUILT-IN FUZZY MATCHING ====================
def similarity_score(text1, text2):
    """Calculate similarity between two texts using built-in methods"""
    if not text1 or not text2:
        return 0.0
    
    text1 = text1.lower().strip()
    text2 = text2.lower().strip()
    
    # If exact match, return 1.0 immediately
    if text1 == text2:
        return 1.0
    
    # Method 1: SequenceMatcher
    seq_match = SequenceMatcher(None, text1, text2)
    base_score = seq_match.ratio()
    
    # Method 2: Word overlap with multiple metrics
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if words1 and words2:
        # Jaccard similarity (intersection over union)
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        jaccard = len(intersection) / len(union) if union else 0
        
        # Overlap coefficient (intersection over min size)
        overlap_coeff = len(intersection) / min(len(words1), len(words2)) if min(len(words1), len(words2)) > 0 else 0
        
        # Combined score with weights
        combined_score = (base_score * 0.3 + jaccard * 0.3 + overlap_coeff * 0.4)
    else:
        combined_score = base_score
    
    # Enhanced keyword matching with your actual medical terms
    medical_keywords = [
        'fever', 'cough', 'pain', 'skin', 'headache', 'joint', 'muscle',
        'infection', 'inflammation', 'chronic', 'acute', 'disorder',
        'disease', 'syndrome', 'respiratory', 'cardiac', 'digestive',
        'neurological', 'mental', 'sleep', 'anxiety', 'depression',
        'diabetes', 'hypertension', 'asthma', 'arthritis', 'migraine',
        'malaria', 'tuberculosis', 'pneumonia', 'bronchitis', 'dermatitis',
        'rash', 'edema', 'fatigue', 'nausea', 'vomiting', 'diarrhea'
    ]
    
    # Count keyword matches
    text1_keywords = [k for k in medical_keywords if k in text1]
    text2_keywords = [k for k in medical_keywords if k in text2]
    
    # Boost based on keyword overlap
    if text1_keywords and text2_keywords:
        common = set(text1_keywords) & set(text2_keywords)
        if common:
            # Boost 0.1 per common keyword, max 0.3
            boost = min(len(common) * 0.1, 0.3)
            combined_score = min(combined_score + boost, 0.95)
        else:
            # Small boost if both have medical terms
            combined_score = min(combined_score + 0.05, 0.95)
    
    # Special handling for common phrase mappings
    phrase_mappings = [
        ('high blood pressure', 'hypertension'),
        ('skin rash', 'dermatitis'),
        ('joint pain', 'arthritis'),
        ('stomach pain', 'abdominal pain'),
        ('shortness of breath', 'dyspnea'),
        ('chest pain', 'angina'),
        ('rapid heartbeat', 'tachycardia'),
        ('weight loss', 'cachexia'),
        ('blood sugar', 'diabetes'),
        ('swollen joints', 'arthritis'),
        ('difficulty breathing', 'asthma'),
        ('runny nose', 'rhinitis'),
        ('sore throat', 'pharyngitis'),
        ('back pain', 'lumbago'),
        ('neck pain', 'cervicalgia')
    ]
    
    for phrase1, phrase2 in phrase_mappings:
        if (phrase1 in text1 and phrase2 in text2) or (phrase2 in text1 and phrase1 in text2):
            combined_score = min(combined_score + 0.2, 0.95)
            break
    
    return combined_score
def find_best_match(search_text, choices, threshold=0.4):
    """Find best match from list of choices"""
    best_match = None
    best_score = 0
    
    for choice in choices:
        score = similarity_score(search_text, choice)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = choice
    
    return best_match, best_score

def init_database():
    """Initialize SQLite database for real project data"""
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    # NAMASTE Codes table (from your CSV uploads)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS namaste_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system TEXT NOT NULL,
            code TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT,
            synonyms TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ICD-11 TM2 Codes table (from your ICD CSV file)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS icd11_tm2_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            icd11_code TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            category TEXT,
            chapter TEXT,
            parent_code TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Intelligent Mappings table (dynamically created)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intelligent_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namaste_code TEXT NOT NULL,
            icd11_code TEXT NOT NULL,
            confidence_score REAL DEFAULT 0.0,
            mapping_method TEXT,
            verified_by_expert BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            qualification TEXT,
            specialization TEXT,
            experience TEXT,
            password TEXT NOT NULL
        )
    ''')

    
    # User Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            age INTEGER,
            phone TEXT,
            email TEXT UNIQUE NOT NULL,
            city TEXT,
            state TEXT,
            address TEXT,
            pincode TEXT,
            password TEXT NOT NULL
        )
    ''')

 # Check if appointments table exists, create if not
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (id)
            )
        ''')           
    # Prescriptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            mapped_codes TEXT,
            medications TEXT NOT NULL,
            instructions TEXT NOT NULL,
            notes TEXT,
            pdf_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id),
            FOREIGN KEY (patient_id) REFERENCES users (id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (id)
        )
    ''')

    # User prescriptions view (for user dashboard)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prescription_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            doctor_name TEXT NOT NULL,
            appointment_date DATE NOT NULL,
            diagnosis TEXT,
            medications TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prescription_id) REFERENCES prescriptions (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # FHIR Resources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fhir_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id TEXT UNIQUE NOT NULL,
            resource_type TEXT DEFAULT 'Condition',
            fhir_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

def parse_namaste_csv(filepath, system):
    """Parse uploaded NAMASTE CSV files dynamically"""
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    try:
        # Read CSV with flexible encoding
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1')
        
        print(f"📊 Processing {system} CSV with columns: {df.columns.tolist()}")
        
        # Flexible column mapping - adapts to your CSV structure
        code_col = None
        desc_col = None
        category_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'code' in col_lower:
                code_col = col
            elif 'description' in col_lower or 'disease' in col_lower or 'name' in col_lower or 'term' in col_lower:
                desc_col = col
            elif 'category' in col_lower or 'type' in col_lower or 'classification' in col_lower:
                category_col = col
        
        if not code_col:
            # If no code column, create one
            code_col = 'AutoCode'
            df[code_col] = [f'{system.upper()}{i+1:03d}' for i in range(len(df))]
        
        if not desc_col:
            flash(f'❌ CSV must contain description column. Found: {df.columns.tolist()}', 'error')
            return
        
        row_count = 0
        for index, row in df.iterrows():
            code = str(row[code_col]).strip()
            description = str(row[desc_col]).strip()
            category = str(row[category_col]).strip() if category_col and pd.notna(row[category_col]) else ''
            
            if description:  # Only insert rows with description
                cursor.execute('''
                    INSERT OR REPLACE INTO namaste_codes (system, code, description, category)
                    VALUES (?, ?, ?, ?)
                ''', (system, code, description, category))
                row_count += 1
        
        conn.commit()
        flash(f'✅ Successfully processed {row_count} {system} codes!', 'success')
        print(f"✅ Saved {row_count} {system} codes to database")
        
    except Exception as e:
        error_msg = f'❌ Error processing {system} CSV: {str(e)}'
        flash(error_msg, 'error')
        print(error_msg)
    finally:
        conn.close()

def parse_icd11_csv(filepath):
    """Parse ICD-11 TM2 CSV file"""
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    try:
        # Read CSV with flexible encoding
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1')
        
        print(f"🌍 Processing ICD-11 CSV with columns: {df.columns.tolist()}")
        
        # Flexible column mapping for ICD-11 CSV
        code_col = None
        desc_col = None
        category_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'code' in col_lower or 'id' in col_lower:
                code_col = col
            elif 'description' in col_lower or 'title' in col_lower or 'name' in col_lower or 'term' in col_lower:
                desc_col = col
            elif 'category' in col_lower or 'chapter' in col_lower or 'group' in col_lower:
                category_col = col
        
        if not code_col:
            # If no code column, create one
            code_col = 'AutoICDCode'
            df[code_col] = [f'ICD11_{i+1:03d}' for i in range(len(df))]
        
        if not desc_col:
            flash(f'❌ ICD-11 CSV must contain description column', 'error')
            return
        
        row_count = 0
        for index, row in df.iterrows():
            code = str(row[code_col]).strip()
            description = str(row[desc_col]).strip()
            category = str(row[category_col]).strip() if category_col and pd.notna(row[category_col]) else ''
            
            if description:
                cursor.execute('''
                    INSERT OR REPLACE INTO icd11_tm2_codes (icd11_code, description, category)
                    VALUES (?, ?, ?)
                ''', (code, description, category))
                row_count += 1
        
        conn.commit()
        flash(f'✅ Successfully processed {row_count} ICD-11 TM2 codes!', 'success')
        print(f"✅ Saved {row_count} ICD-11 codes to database")
        
    except Exception as e:
        error_msg = f'❌ Error processing ICD-11 CSV: {str(e)}'
        flash(error_msg, 'error')
        print(error_msg)
    finally:
        conn.close()

def intelligent_mapping():
    """Dynamically create mappings between NAMASTE and ICD-11 codes using built-in methods"""
    conn = sqlite3.connect('namaste_icd11.db')
    
    try:
        # Get all NAMASTE codes
        namaste_codes = pd.read_sql('SELECT code, description, system FROM namaste_codes', conn)
        
        # Get all ICD-11 codes
        icd11_codes = pd.read_sql('SELECT icd11_code, description FROM icd11_tm2_codes', conn)
        
        if namaste_codes.empty or icd11_codes.empty:
            print("⚠️ No codes found for mapping")
            return 0
        
        mappings_created = 0
        
        for _, namaste_row in namaste_codes.iterrows():
            namaste_desc = namaste_row['description']
            namaste_code = namaste_row['code']
            system = namaste_row['system']
            
            best_match = None
            best_score = 0
            
            for _, icd11_row in icd11_codes.iterrows():
                icd11_desc = icd11_row['description']
                icd11_code = icd11_row['icd11_code']
                
                # Calculate similarity score using built-in method
                score = similarity_score(namaste_desc, icd11_desc)
                
                if score > best_score and score > 0.3:  # Lower threshold to 30%  # Threshold for matching
                    best_score = score
                    best_match = icd11_code
            
            if best_match:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO intelligent_mappings 
                    (namaste_code, icd11_code, confidence_score, mapping_method)
                    VALUES (?, ?, ?, ?)
                ''', (namaste_code, best_match, best_score, 'similarity_match'))
                
                mappings_created += 1
                print(f"🔗 Mapped {namaste_code} → {best_match} (Score: {best_score:.2f})")
        
        conn.commit()
        print(f"✅ Created {mappings_created} intelligent mappings!")
        return mappings_created
        
    except Exception as e:
        print(f"❌ Error in intelligent mapping: {str(e)}")
        return 0
    finally:
        conn.close()

# Initialize database
init_database()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Routes
@app.route('/')
def main():
    lang = request.args.get('lang', 'en')  # Get language from URL
    return render_template('main.html', lang=lang)

@app.route('/index')
def index():
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/register', methods=['GET', 'POST'])
def doctor_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        qualification = request.form['qualification']
        specialization = request.form['specialization']
        experience = request.form['experience']
        password = request.form['password']

        conn = sqlite3.connect('namaste_icd11.db')  # or DB_NAME
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO doctors 
                (name, email, phone, qualification, specialization, experience, password)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, email, phone, qualification, specialization, experience, password))
            conn.commit()
            flash('Doctor registered successfully!', 'success')
            return redirect(url_for('doctor_login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'danger')
        finally:
            conn.close()
    return render_template('doctor_register.html')


# Update doctor login route
@app.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM doctors WHERE email=? AND password=?", (email, password))
        doctor = cursor.fetchone()
        conn.close()
        
        if doctor:
            session['doctor_id'] = doctor[0]
            session['doctor_name'] = doctor[1]
            session['doctor_email'] = doctor[2]
            flash(f'Welcome Dr. {doctor[1]}!', 'success')
            return redirect(url_for('doctor_dashboard'))
        else:
            flash('Invalid credentials!', 'danger')
    return render_template('doctor_login.html')

# Doctor dashboard
@app.route('/doctor/dashboard')
def doctor_dashboard():
    lang = request.args.get('lang', 'en')  # Get language from URL
    doctor_id = session.get('doctor_id')
    
    if not doctor_id:
        flash("Please login as doctor first", "warning")
        return redirect(url_for('doctor_login'))

    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get doctor details
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) FROM namaste_codes')
    total_codes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM intelligent_mappings')
    mapped_codes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id = ? AND status = 'pending'", (doctor_id,))
    pending_appointments = cursor.fetchone()[0]
    
    # Get recent uploads
    cursor.execute('''
        SELECT system, description, uploaded_at 
        FROM namaste_codes 
        ORDER BY uploaded_at DESC 
        LIMIT 5
    ''')
    recent_uploads = cursor.fetchall()
    
    # Get uploaded files count
    cursor.execute("SELECT COUNT(DISTINCT system) FROM namaste_codes")
    uploaded_systems = cursor.fetchone()[0]
    
    conn.close()
    
    # Format recent uploads for display
    upload_list = []
    for upload in recent_uploads:
        upload_list.append({
            'system': upload['system'],
            'name': f"{upload['system']}_codes.csv",
            'date': upload['uploaded_at'],
            'status': 'Mapped'
        })
    
    return render_template(
        'doctor_dashboard.html',
        doctor=doctor,
        doctor_name=doctor['name'] if doctor else 'Doctor',
        stats={
            'total_codes': total_codes,
            'mapped_codes': mapped_codes,
            'pending_appointments': pending_appointments,
            'uploaded_files': uploaded_systems
        },
        recent_uploads=upload_list
    )

# Doctor profile page
@app.route('/doctor/profile')
def doctor_profile():
    doctor_id = session.get('doctor_id')
    
    if not doctor_id:
        flash("Please login as doctor first", "warning")
        return redirect(url_for('doctor_login'))

    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    conn.close()

    if not doctor:
        flash("Doctor not found", "danger")
        return redirect(url_for('doctor_login'))

    return render_template(
        "doctor_profile.html",
        doctor=doctor,
        doctor_name=doctor['name']
    )

# Update doctor profile
@app.route('/doctor/update-profile', methods=['POST'])
def doctor_update_profile():
    doctor_id = session.get('doctor_id')
    if not doctor_id:
        flash("Please login first", "warning")
        return redirect(url_for('doctor_login'))

    name = request.form['name']
    email = request.form['email']
    phone = request.form.get('phone')
    qualification = request.form.get('qualification')
    specialization = request.form.get('specialization')
    experience = request.form.get('experience')

    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE doctors SET 
            name=?, email=?, phone=?, qualification=?, specialization=?, experience=?
        WHERE id=?
    """, (name, email, phone, qualification, specialization, experience, doctor_id))
    conn.commit()
    conn.close()

    # Update session
    session['doctor_name'] = name
    
    flash("Profile updated successfully!", "success")
    return redirect('/doctor/profile')



# Doctor appointments page
@app.route('/doctor/appointments')
def doctor_appointments():
    doctor_id = session.get('doctor_id')
    
    if not doctor_id:
        flash("Please login as doctor first", "warning")
        return redirect(url_for('doctor_login'))

    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get doctor details
    cursor.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cursor.fetchone()
    
    # Get appointments for this doctor
    cursor.execute('''
        SELECT appointments.*, users.name as patient_name, users.phone as patient_phone
        FROM appointments 
        JOIN users ON appointments.user_id = users.id
        WHERE doctor_id = ?
        ORDER BY appointment_date DESC, appointment_time DESC
    ''', (doctor_id,))
    appointments = cursor.fetchall()
    
    conn.close()

    return render_template(
        'doctor_appointments.html',
        doctor=doctor,
        appointments=appointments,
        doctor_name=doctor['name'] if doctor else 'Doctor'
    )



# Update appointment status
@app.route('/doctor/update-appointment-status', methods=['POST'])
def update_appointment_status():
    doctor_id = session.get('doctor_id')
    if not doctor_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    new_status = data.get('status')
    
    if not appointment_id or not new_status:
        return jsonify({'error': 'Missing parameters'}), 400
    
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    # Verify the appointment belongs to this doctor
    cursor.execute('SELECT doctor_id FROM appointments WHERE id = ?', (appointment_id,))
    appointment = cursor.fetchone()
    
    if not appointment or appointment[0] != doctor_id:
        conn.close()
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Update status
    cursor.execute('UPDATE appointments SET status = ? WHERE id = ?', (new_status, appointment_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Appointment marked as {new_status}'})

# Get appointment statistics
@app.route('/api/doctor/appointment-stats')
def doctor_appointment_stats():
    doctor_id = session.get('doctor_id')
    if not doctor_id:
        return jsonify({'error': 'Not logged in'}), 401
    
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    # Get counts for different statuses
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id = ? AND status = 'pending'", (doctor_id,))
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id = ? AND status = 'confirmed'", (doctor_id,))
    confirmed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id = ? AND status = 'completed'", (doctor_id,))
    completed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id = ? AND status = 'cancelled'", (doctor_id,))
    cancelled = cursor.fetchone()[0]
    
    # Today's appointments
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE doctor_id = ? AND appointment_date = date('now')", (doctor_id,))
    today = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'pending': pending,
        'confirmed': confirmed,
        'completed': completed,
        'cancelled': cancelled,
        'today': today,
        'total': pending + confirmed + completed + cancelled
    })



# Route for mapping with appointment context
@app.route('/mapping-with-appointment')
def mapping_with_appointment():
    appointment_id = request.args.get('appointment_id')
    
    if not appointment_id:
        flash("No appointment specified", "error")
        return redirect(url_for('doctor_appointments'))
    
    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get appointment details
    cursor.execute('''
        SELECT appointments.*, users.name as patient_name, users.email as patient_email,
               users.phone as patient_phone, users.age, users.gender, users.address,
               doctors.name as doctor_name
        FROM appointments 
        JOIN users ON appointments.user_id = users.id
        JOIN doctors ON appointments.doctor_id = doctors.id
        WHERE appointments.id = ?
    ''', (appointment_id,))
    
    appointment = cursor.fetchone()
    conn.close()
    
    if not appointment:
        flash("Appointment not found", "error")
        return redirect(url_for('doctor_appointments'))
    
    return render_template('mapping_with_appointment.html', 
                         appointment=appointment,
                         appointment_id=appointment_id)


# Save prescription endpoint
# Save prescription endpoint - UPDATED
@app.route('/api/save-prescription', methods=['POST'])
def save_prescription():
    try:
        data = request.get_json()
        appointment_id = data.get('appointment_id')
        
        # Check if doctor is logged in
        doctor_id = session.get('doctor_id')
        if not doctor_id:
            return jsonify({'error': 'Doctor not logged in'}), 401
        
        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        
        # Get doctor details
        cursor.execute("SELECT name, qualification, specialization FROM doctors WHERE id = ?", (doctor_id,))
        doctor = cursor.fetchone()
        doctor_name = doctor[0] if doctor else "Doctor"
        doctor_qual = doctor[1] if doctor and doctor[1] else "MBBS"
        doctor_spec = doctor[2] if doctor and doctor[2] else "General Physician"
        
        # Save prescription
        cursor.execute('''
            INSERT INTO prescriptions 
            (appointment_id, patient_id, doctor_id, mapped_codes, medications, instructions, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            appointment_id,
            data['patient_id'],
            data['doctor_id'],
            json.dumps(data['mapped_codes']),
            data['medications'],
            data['instructions'],
            data.get('notes', '')
        ))
        
        prescription_id = cursor.lastrowid
        
        # Update appointment status to completed
        cursor.execute('UPDATE appointments SET status = ? WHERE id = ?', ('completed', appointment_id))
        
        # Get diagnosis from mapped codes
        diagnosis = ', '.join([code['namaste_desc'] for code in data['mapped_codes']][:3])
        
        # Add to user prescriptions view
        cursor.execute('''
            INSERT INTO user_prescriptions 
            (prescription_id, user_id, doctor_name, appointment_date, diagnosis, medications)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            prescription_id,
            data['patient_id'],
            doctor_name,
            data['appointment_date'],
            diagnosis[:100],  # Limit to 100 chars
            data['medications'][:200]  # Limit to 200 chars
        ))
        
        conn.commit()
        
        # Get patient details
        cursor.execute("SELECT name, age, gender, phone, address FROM users WHERE id = ?", (data['patient_id'],))
        patient = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'prescription_id': prescription_id,
            'message': 'Prescription saved and appointment marked as completed',
            'prescription_data': {
                'id': prescription_id,
                'patient_name': patient[0] if patient else '',
                'patient_age': patient[1] if patient else '',
                'patient_gender': patient[2] if patient else '',
                'patient_phone': patient[3] if patient else '',
                'patient_address': patient[4] if patient else '',
                'doctor_name': doctor_name,
                'doctor_qualification': doctor_qual,
                'doctor_specialization': doctor_spec,
                'medications': data['medications'],
                'instructions': data['instructions'],
                'notes': data.get('notes', ''),
                'mapped_codes': data['mapped_codes'],
                'appointment_date': data['appointment_date'],
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500




# Generate PDF prescription
@app.route('/generate-prescription-pdf/<int:prescription_id>')
def generate_prescription_pdf(prescription_id):
    try:
        conn = sqlite3.connect('namaste_icd11.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get prescription details
        cursor.execute('''
            SELECT p.*, 
                   u.name as patient_name, u.age as patient_age, u.gender as patient_gender,
                   u.phone as patient_phone, u.address as patient_address, u.email as patient_email,
                   d.name as doctor_name, d.qualification as doctor_qualification,
                   d.specialization as doctor_specialization, d.phone as doctor_phone,
                   a.appointment_date, a.symptoms
            FROM prescriptions p
            JOIN users u ON p.patient_id = u.id
            JOIN doctors d ON p.doctor_id = d.id
            JOIN appointments a ON p.appointment_id = a.id
            WHERE p.id = ?
        ''', (prescription_id,))
        
        prescription = cursor.fetchone()
        conn.close()
        
        if not prescription:
            return "Prescription not found", 404
        
        # Parse mapped codes
        mapped_codes = json.loads(prescription['mapped_codes']) if prescription['mapped_codes'] else []
        
        # Create PDF in memory
        buffer = io.BytesIO()
        
        # Create document with more margins
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=50, leftMargin=50,
                                topMargin=50, bottomMargin=50)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#064635'),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#35635b'),
            spaceAfter=15,
            alignment=TA_CENTER
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#064635'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderColor=colors.white,
            backColor=colors.white
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=8,
            leading=12  # Line spacing
        )
        
        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )
        
        small_style = ParagraphStyle(
            'CustomSmall',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            spaceAfter=4
        )
        
        # Title Section
        elements.append(Paragraph("VEDASHAYAM", title_style))
        elements.append(Paragraph("Integrative Healthcare System", subtitle_style))
        elements.append(Paragraph("NAMASTE-ICD11 Mapping Prescription", subtitle_style))
        
        elements.append(Spacer(1, 20))
        
        # Prescription Header
        elements.append(Paragraph(f"<b>Prescription ID:</b> RX{str(prescription_id).zfill(6)}", normal_style))
        elements.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d-%m-%Y %H:%M')}", normal_style))
        
        elements.append(Spacer(1, 20))
        
        # Horizontal Line
        elements.append(Paragraph("<hr/>", normal_style))
        elements.append(Spacer(1, 15))
        
        # Patient Information Section
        elements.append(Paragraph("PATIENT INFORMATION", header_style))
        elements.append(Paragraph(f"<b>Name:</b> {prescription['patient_name']}", normal_style))
        elements.append(Paragraph(f"<b>Age/Gender:</b> {prescription['patient_age']} years / {prescription['patient_gender']}", normal_style))
        elements.append(Paragraph(f"<b>Phone:</b> {prescription['patient_phone']}", normal_style))
        elements.append(Paragraph(f"<b>Email:</b> {prescription['patient_email']}", normal_style))
        elements.append(Paragraph(f"<b>Address:</b> {prescription['patient_address']}", normal_style))
        
        elements.append(Spacer(1, 15))
        
        # Doctor Information Section
        elements.append(Paragraph("DOCTOR INFORMATION", header_style))
        elements.append(Paragraph(f"<b>Name:</b> Dr. {prescription['doctor_name']}", normal_style))
        elements.append(Paragraph(f"<b>Qualification:</b> {prescription['doctor_qualification']}", normal_style))
        elements.append(Paragraph(f"<b>Specialization:</b> {prescription['doctor_specialization']}", normal_style))
        elements.append(Paragraph(f"<b>Phone:</b> {prescription['doctor_phone']}", normal_style))
        elements.append(Paragraph(f"<b>Registration No:</b> MED{str(prescription['doctor_id']).zfill(4)}", normal_style))
        
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<hr/>", normal_style))
        elements.append(Spacer(1, 15))
        
        # Appointment Details Section
        elements.append(Paragraph("APPOINTMENT DETAILS", header_style))
        elements.append(Paragraph(f"<b>Appointment Date:</b> {prescription['appointment_date']}", normal_style))
        elements.append(Paragraph(f"<b>Symptoms:</b> {prescription['symptoms']}", normal_style))
        elements.append(Paragraph(f"<b>Prescription Date:</b> {prescription['created_at'][:10] if prescription['created_at'] else datetime.now().strftime('%Y-%m-%d')}", normal_style))
        
        elements.append(Spacer(1, 20))
        
        # Diagnosis Section (if mapped codes exist)
        if mapped_codes:
            elements.append(Paragraph("DIAGNOSIS & MAPPED CODES", header_style))
            
            for i, code in enumerate(mapped_codes[:5], 1):  # Show max 5 codes
                diagnosis_text = f"""
                <b>{i}. NAMASTE Code:</b> {code['namaste_code']}<br/>
                <b>Diagnosis:</b> {code['namaste_desc']}<br/>
                <b>ICD-11 Code:</b> {code['icd11_code']}<br/>
                <b>Confidence:</b> {code['confidence']*100:.0f}%
                """
                elements.append(Paragraph(diagnosis_text, normal_style))
                elements.append(Spacer(1, 10))
            
            elements.append(Spacer(1, 10))
        
        # Horizontal Line
        elements.append(Paragraph("<hr/>", normal_style))
        elements.append(Spacer(1, 15))
        
        # Medications Section
        elements.append(Paragraph("MEDICATIONS & DOSAGE", header_style))
        
        # Format medications with bullet points if they contain newlines
        medications = prescription['medications']
        if '\n' in medications:
            med_lines = medications.split('\n')
            for line in med_lines:
                if line.strip():
                    elements.append(Paragraph(f"• {line.strip()}", normal_style))
        else:
            elements.append(Paragraph(medications, normal_style))
        
        elements.append(Spacer(1, 20))
        
        # Instructions Section
        elements.append(Paragraph("PATIENT INSTRUCTIONS", header_style))
        
        # Format instructions with bullet points if they contain newlines
        instructions = prescription['instructions']
        if '\n' in instructions:
            instr_lines = instructions.split('\n')
            for line in instr_lines:
                if line.strip():
                    elements.append(Paragraph(f"• {line.strip()}", normal_style))
        else:
            elements.append(Paragraph(instructions, normal_style))
        
        elements.append(Spacer(1, 20))
        
        # Notes Section (if exists)
        if prescription['notes']:
            elements.append(Paragraph("ADDITIONAL NOTES", header_style))
            
            notes = prescription['notes']
            if '\n' in notes:
                note_lines = notes.split('\n')
                for line in note_lines:
                    if line.strip():
                        elements.append(Paragraph(f"• {line.strip()}", normal_style))
            else:
                elements.append(Paragraph(notes, normal_style))
            
            elements.append(Spacer(1, 20))
        
        # Page break before signature if content is long
        if len(elements) > 40:
            from reportlab.platypus import PageBreak
            elements.append(PageBreak())
        
        # Footer with signatures
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("<hr/>", normal_style))
        elements.append(Spacer(1, 20))
        
        # Doctor's Signature Section
        elements.append(Paragraph("DOCTOR'S SIGNATURE", header_style))
        elements.append(Paragraph(f"Dr. {prescription['doctor_name']}", normal_style))
        elements.append(Paragraph(f"{prescription['doctor_qualification']}", normal_style))
        elements.append(Paragraph(f"{prescription['doctor_specialization']}", normal_style))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%d-%m-%Y')}", normal_style))
        
        elements.append(Spacer(1, 30))
        
        # Patient's Acknowledgement Section
        elements.append(Paragraph("PATIENT'S ACKNOWLEDGEMENT", header_style))
        elements.append(Paragraph("I have received and understood the prescription", normal_style))
        elements.append(Paragraph("and will follow the instructions as directed.", normal_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("Signature: _________________", normal_style))
        elements.append(Paragraph("Date: _________________", normal_style))
        
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("<hr/>", normal_style))
        elements.append(Spacer(1, 15))
        
        # Footer notes
        footer_notes = [
            "** IMPORTANT NOTES **",
            "1. This is a computer-generated prescription. No physical signature is required.",
            "2. Take medications as prescribed. Do not self-medicate.",
            "3. Complete the full course of medication even if you feel better.",
            "4. Report any side effects or adverse reactions immediately.",
            "5. Keep this prescription for future reference.",
            "6. Follow-up appointment may be required as advised.",
            f"© {datetime.now().year} Vedashayam Integrative Healthcare System. All rights reserved."
        ]
        
        for note in footer_notes:
            elements.append(Paragraph(note, small_style))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF value from buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        # Create response
        response = app.response_class(
            response=pdf,
            status=200,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=Prescription_RX{str(prescription_id).zfill(6)}.pdf'
            }
        )
        
        return response
        
    except Exception as e:
        print(f"PDF Generation Error: {str(e)}")
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500






# Get user prescriptions
@app.route('/api/user-prescriptions')
def get_user_prescriptions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401
    
    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM user_prescriptions 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    
    prescriptions = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    prescriptions_list = []
    for prescription in prescriptions:
        prescriptions_list.append(dict(prescription))
    
    return jsonify(prescriptions_list)

# Route for user prescriptions page
@app.route('/my-prescriptions')
def my_prescriptions():
    user_id = session.get('user_id')
    
    if not user_id:
        flash("Please login first", "warning")
        return redirect(url_for('user_login'))
    
    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get user details
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    # Get prescriptions
    cursor.execute('''
        SELECT up.*, p.instructions, p.notes, p.created_at as prescription_date
        FROM user_prescriptions up
        LEFT JOIN prescriptions p ON up.prescription_id = p.id
        WHERE up.user_id = ?
        ORDER BY up.created_at DESC
    ''', (user_id,))
    
    prescriptions = cursor.fetchall()
    conn.close()
    
    return render_template(
        'user_prescriptions.html',
        user=user,
        username=user['name'] if user else 'User',
        prescriptions=prescriptions
    )




@app.route('/api/health-graph-data')
def health_graph_data():
    """API endpoint to get health data for graphs"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401
    
    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get total appointments
        cursor.execute("SELECT COUNT(*) FROM appointments WHERE user_id = ?", (user_id,))
        total_appointments = cursor.fetchone()[0]
        
        # Get total prescriptions
        cursor.execute("SELECT COUNT(*) FROM prescriptions WHERE patient_id = ?", (user_id,))
        total_prescriptions = cursor.fetchone()[0]
        
        # Get last appointment date
        cursor.execute("""
            SELECT appointment_date 
            FROM appointments 
            WHERE user_id = ? 
            ORDER BY appointment_date DESC 
            LIMIT 1
        """, (user_id,))
        last_appointment = cursor.fetchone()
        
        days_since_last_visit = 0
        if last_appointment and last_appointment['appointment_date']:
            last_date = datetime.strptime(last_appointment['appointment_date'], '%Y-%m-%d')
            days_since_last_visit = (datetime.now() - last_date).days
        
        # Calculate health score (simplified)
        health_score = min(100, max(0, 100 - (days_since_last_visit / 30) * 10))
        
        # Get appointment history for graph
        cursor.execute("""
            SELECT appointment_date, COUNT(*) as count
            FROM appointments 
            WHERE user_id = ? 
            GROUP BY appointment_date 
            ORDER BY appointment_date
        """, (user_id,))
        
        appointments_data = []
        for row in cursor.fetchall():
            appointments_data.append({
                'date': row['appointment_date'],
                'count': row['count']
            })
        
        # Get prescription history
        cursor.execute("""
            SELECT DATE(p.created_at) as date, COUNT(*) as count
            FROM prescriptions p
            WHERE p.patient_id = ?
            GROUP BY DATE(p.created_at)
            ORDER BY DATE(p.created_at)
        """, (user_id,))
        
        prescriptions_data = []
        for row in cursor.fetchall():
            prescriptions_data.append({
                'date': row['date'],
                'count': row['count']
            })
        
        # Get recent health records
        cursor.execute("""
            SELECT 
                a.appointment_date as date,
                d.name as doctor_name,
                a.symptoms as diagnosis,
                p.medications,
                a.status
            FROM appointments a
            LEFT JOIN doctors d ON a.doctor_id = d.id
            LEFT JOIN prescriptions p ON a.id = p.appointment_id
            WHERE a.user_id = ?
            ORDER BY a.appointment_date DESC
            LIMIT 10
        """, (user_id,))
        
        recent_records = []
        for row in cursor.fetchall():
            recent_records.append(dict(row))
        
        # Calculate average visits per month
        cursor.execute("""
            SELECT 
                STRFTIME('%Y-%m', appointment_date) as month,
                COUNT(*) as visits
            FROM appointments 
            WHERE user_id = ? 
            AND appointment_date >= DATE('now', '-6 months')
            GROUP BY STRFTIME('%Y-%m', appointment_date)
        """, (user_id,))
        
        monthly_visits = cursor.fetchall()
        avg_visits_per_month = 0
        if monthly_visits:
            total_visits = sum(row['visits'] for row in monthly_visits)
            avg_visits_per_month = total_visits / len(monthly_visits)
        
        # Get common conditions (from mapped codes in prescriptions)
        cursor.execute("""
            SELECT COUNT(DISTINCT JSON_EXTRACT(mapped_codes, '$[0].namaste_desc')) as conditions
            FROM prescriptions 
            WHERE patient_id = ?
        """, (user_id,))
        
        common_conditions = cursor.fetchone()[0] or 0
        
        # Calculate prescription rate
        cursor.execute("""
            SELECT 
                COUNT(*) as total_appointments,
                SUM(CASE WHEN p.id IS NOT NULL THEN 1 ELSE 0 END) as appointments_with_prescriptions
            FROM appointments a
            LEFT JOIN prescriptions p ON a.id = p.appointment_id
            WHERE a.user_id = ?
        """, (user_id,))
        
        rate_data = cursor.fetchone()
        prescription_rate = 0
        if rate_data['total_appointments'] > 0:
            prescription_rate = round((rate_data['appointments_with_prescriptions'] / rate_data['total_appointments']) * 100)
        
        conn.close()
        
        return jsonify({
            'stats': {
                'totalAppointments': total_appointments,
                'totalPrescriptions': total_prescriptions,
                'healthScore': round(health_score),
                'daysSinceLastVisit': days_since_last_visit,
                'avgVisitsPerMonth': avg_visits_per_month,
                'commonConditions': common_conditions,
                'prescriptionRate': prescription_rate
            },
            'appointments': appointments_data,
            'prescriptions': prescriptions_data,
            'recentRecords': recent_records
        })
        
    except Exception as e:
        print(f"Error in health graph data: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()






@app.route('/user-graph')
def user_graph():
    """Render the health graph page"""
    user_id = session.get('user_id')
    
    if not user_id:
        flash("Please login first", "warning")
        return redirect(url_for('user_login'))

    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get user details
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash("User not found", "danger")
        return redirect(url_for('user_login'))

    return render_template(
        "user_graph.html",
        username=user["name"],
        user=user
    )




# Doctor logout
@app.route('/doctor/logout')
def doctor_logout():
    session.pop('doctor_id', None)
    session.pop('doctor_name', None)
    session.pop('doctor_email', None)
    flash("Logged out successfully!", "success")
    return redirect(url_for('doctor_login'))
# ---------- User Routes ----------
@app.route('/user/register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        age = request.form['age']
        phone = request.form['phone']
        email = request.form['email']
        city = request.form['city']
        state = request.form['state']
        address = request.form['address']
        pincode = request.form['pincode']
        password = request.form['password']

        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users 
                (name, gender, age, phone, email, city, state, address, pincode, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, gender, age, phone, email, city, state, address, pincode, password))
            conn.commit()
            flash('User registered successfully!', 'success')
            return redirect(url_for('user_login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'danger')
        finally:
            conn.close()
    return render_template('user_register.html')




@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]    # store ID
            session['username'] = user[1]   # store name for quick greeting
            flash(f'Welcome {user[1]}!', 'success')
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid credentials!', 'danger')
    return render_template('user_login.html')


@app.route('/user/dashboard')
def user_dashboard():
    lang = request.args.get('lang', 'en')
    user_id = session.get('user_id')
    
    if not user_id:
        flash("Please login first", "warning")
        return redirect(url_for('user_login'))

    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row   # So you can use dict-like access
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash("User not found", "danger")
        return redirect(url_for('user_login'))

    return render_template(
        "user_dashboard.html",
        username=user["name"],
        user=user
    )

@app.route('/update-profile', methods=['POST'])
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/login')

    name = request.form['name']
    email = request.form['email']
    gender = request.form['gender']
    age = request.form.get('age')
    phone = request.form.get('phone')
    address = request.form.get('address')
    city = request.form.get('city')
    state = request.form.get('state')

    conn = sqlite3.connect('namaste_icd11.db') 

    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET 
            name=?, email=?, gender=?, age=?, phone=?, address=?, city=?, state=?
        WHERE id=?
    """, (name, email, gender, age, phone, address, city, state, user_id))
    conn.commit()
    conn.close()

    flash("Profile updated successfully!", "success")
    return redirect('/user/dashboard')



# Add these routes to your Flask app

@app.route('/book-appointments')
def book_appointments():
    """Render the book appointments page"""
    user_id = session.get('user_id')
    
    if not user_id:
        flash("Please login first", "warning")
        return redirect(url_for('user_login'))

    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get user details
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash("User not found", "danger")
        return redirect(url_for('user_login'))

    return render_template(
        "book_appointments.html",
        username=user["name"],
        user=user
    )

@app.route('/api/doctors')
def get_doctors():
    """API endpoint to get all doctors"""
    conn = sqlite3.connect('namaste_icd11.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, email, phone, qualification, specialization, experience FROM doctors")
    doctors = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    doctors_list = []
    for doctor in doctors:
        doctors_list.append({
            'id': doctor['id'],
            'name': doctor['name'],
            'email': doctor['email'],
            'phone': doctor['phone'],
            'qualification': doctor['qualification'],
            'specialization': doctor['specialization'],
            'experience': doctor['experience']
        })
    
    return jsonify(doctors_list)

@app.route('/api/book-appointment', methods=['POST'])
def book_appointment_api():
    """API endpoint to book an appointment"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['doctor_id', 'appointment_date', 'appointment_time', 'symptoms']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        
        
        
        # Insert appointment
        cursor.execute('''
            INSERT INTO appointments 
            (user_id, doctor_id, appointment_date, appointment_time, symptoms, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            user_id,
            data['doctor_id'],
            data['appointment_date'],
            data['appointment_time'],
            data['symptoms'],
            data.get('priority', 'normal')
        ))
        
        appointment_id = cursor.lastrowid
        
        # Get doctor details for confirmation
        cursor.execute("SELECT name, email FROM doctors WHERE id = ?", (data['doctor_id'],))
        doctor = cursor.fetchone()
        
        # Get user details
        cursor.execute("SELECT name, email FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        conn.commit()
        conn.close()
        
        # Return success response
        return jsonify({
            'success': True,
            'appointment_id': appointment_id,
            'message': 'Appointment booked successfully',
            'appointment_details': {
                'doctor_name': doctor[0] if doctor else 'Unknown',
                'appointment_date': data['appointment_date'],
                'appointment_time': data['appointment_time']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/home')
def home():
    username = session.get('username', 'User')
    return render_template('user_dashboard.html', username=username)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('user_login'))
 # Redirect to login page

@app.route('/upload')
def upload():
    return render_template('upload.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    system = request.form.get('system')
    file_type = request.form.get('file_type', 'namaste')
    
    if 'file' not in request.files:
        flash('❌ No file selected', 'error')
        return redirect(url_for('upload'))
    
    file = request.files['file']
    if file.filename == '':
        flash('❌ No file selected', 'error')
        return redirect(url_for('upload'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        if file_type == 'icd11':
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'icd11', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            parse_icd11_csv(filepath)
            
        else:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], system, filename)
            file.save(filepath)
            parse_namaste_csv(filepath, system)
        
        # ============ FIX: Check if both datasets exist and run mapping ============
        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM namaste_codes')
        namaste_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM icd11_tm2_codes')
        icd11_count = cursor.fetchone()[0]
        
        conn.close()
        
        if namaste_count > 0 and icd11_count > 0:
            mappings_count = intelligent_mapping()
            if mappings_count > 0:
                flash(f'✅ Auto-generated {mappings_count} intelligent mappings!', 'success')
            else:
                flash('⚠️ No mappings generated. Check data compatibility.', 'warning')
        else:
            flash('💡 Upload both NAMASTE and ICD-11 files for automatic mapping', 'info')
        
        return redirect(url_for('upload'))
    else:
        flash('❌ Please upload a valid CSV file', 'error')
        return redirect(url_for('upload'))

# API Endpoints
@app.route('/api/map-code', methods=['POST'])
def map_code():
    """Map NAMASTE code to ICD-11 TM2 using intelligent mapping"""
    try:
        data = request.get_json()
        
        if not data or 'namaste_code' not in data:
            return jsonify({'error': 'NAMASTE code is required'}), 400
        
        namaste_code = data['namaste_code']
        print(f"Mapping request for code: {namaste_code}")  # Debug log
        
        conn = sqlite3.connect('namaste_icd11.db')
        cursor = conn.cursor()
        
        # Get NAMASTE code details
        cursor.execute('SELECT description, system FROM namaste_codes WHERE code = ?', (namaste_code,))
        namaste_data = cursor.fetchone()
        
        if not namaste_data:
            conn.close()
            return jsonify({'error': f'NAMASTE code {namaste_code} not found'}), 404
        
        namaste_description, system = namaste_data
        print(f"Found: {namaste_description} ({system})")  # Debug log
        
        # Get best mapping
        cursor.execute('''
            SELECT icd11_code, confidence_score 
            FROM intelligent_mappings 
            WHERE namaste_code = ? 
            ORDER BY confidence_score DESC 
            LIMIT 1
        ''', (namaste_code,))
        
        mapping = cursor.fetchone()
        
        if mapping:
            icd11_code, confidence = mapping
            print(f"Found mapping: {icd11_code} with confidence {confidence}")  # Debug log
            
            # Get ICD-11 details
            cursor.execute('SELECT description FROM icd11_tm2_codes WHERE icd11_code = ?', (icd11_code,))
            icd11_data = cursor.fetchone()
            icd11_description = icd11_data[0] if icd11_data else "Unknown"
            
        else:
            print(f"No mapping found for {namaste_code}")  # Debug log
            # No mapping found
            icd11_code = "Not Mapped"
            confidence = 0.0
            icd11_description = "No suitable mapping found"
        
        conn.close()
        
        # Create FHIR resource
        fhir_resource = create_fhir_condition_resource(
            namaste_code, 
            icd11_code, 
            data.get('patient_id'),
            namaste_description,
            icd11_description
        )
        
        response = {
            'namaste_code': namaste_code,
            'namaste_description': namaste_description,
            'system': system,
            'icd11_tm2_code': icd11_code,
            'icd11_description': icd11_description,
            'fhir_resource': fhir_resource,
            'mapping_confidence': confidence,
            'mapping_status': 'success' if icd11_code != "Not Mapped" else 'no_mapping'
        }
        
        print(f"Sending response with confidence: {confidence}")  # Debug log
        return jsonify(response)
        
    except Exception as e:
        print(f"ERROR in map_code: {str(e)}")  # Debug log
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

def create_fhir_condition_resource(namaste_code, icd11_code, patient_id, namaste_desc, icd11_desc):
    """Create FHIR Condition resource with real data"""
    resource_id = f"condition-{namaste_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    fhir_resource = {
        "resourceType": "Condition",
        "id": resource_id,
        "clinicalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": "active",
                "display": "Active"
            }]
        },
        "verificationStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed",
                "display": "Confirmed"
            }]
        },
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                "code": "encounter-diagnosis",
                "display": "Encounter Diagnosis"
            }]
        }],
        "code": {
            "coding": [
                {
                    "system": "http://who.int/icd11/tm2",
                    "code": icd11_code,
                    "display": icd11_desc
                },
                {
                    "system": "http://namaste.gov.in/ayush",
                    "code": namaste_code,
                    "display": namaste_desc
                }
            ],
            "text": namaste_desc
        },
        "subject": {
            "reference": f"Patient/{patient_id}" if patient_id else "Patient/example"
        },
        "recordedDate": datetime.now().isoformat()
    }
    
    # Store FHIR resource
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO fhir_resources (resource_id, fhir_json)
        VALUES (?, ?)
    ''', (resource_id, json.dumps(fhir_resource)))
    conn.commit()
    conn.close()
    
    return fhir_resource

@app.route('/api/search', methods=['GET'])
def search_codes():
    """Search across all codes"""
    query = request.args.get('q', '')
    system = request.args.get('system', 'all')
    
    conn = sqlite3.connect('namaste_icd11.db')
    
    try:
        if system == 'all':
            # Search both NAMASTE and ICD-11 codes
            namaste_results = pd.read_sql('''
                SELECT system, code, description, category 
                FROM namaste_codes 
                WHERE description LIKE ? OR code LIKE ?
                LIMIT 10
            ''', conn, params=(f'%{query}%', f'%{query}%'))
            
            icd11_results = pd.read_sql('''
                SELECT icd11_code as code, description, category 
                FROM icd11_tm2_codes 
                WHERE description LIKE ? OR icd11_code LIKE ?
                LIMIT 10
            ''', conn, params=(f'%{query}%', f'%{query}%'))
            
            results = []
            for _, row in namaste_results.iterrows():
                results.append({
                    'type': 'namaste',
                    'system': row['system'],
                    'code': row['code'],
                    'description': row['description'],
                    'category': row['category']
                })
            
            for _, row in icd11_results.iterrows():
                results.append({
                    'type': 'icd11',
                    'system': 'icd11_tm2',
                    'code': row['code'],
                    'description': row['description'],
                    'category': row['category']
                })
                
        else:
            # Search specific system
            cursor = conn.cursor()
            cursor.execute('''
                SELECT system, code, description, category 
                FROM namaste_codes 
                WHERE system = ? AND (description LIKE ? OR code LIKE ?)
                LIMIT 20
            ''', (system, f'%{query}%', f'%{query}%'))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'type': 'namaste',
                    'system': row[0],
                    'code': row[1],
                    'description': row[2],
                    'category': row[3]
                })
        
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/statistics')
def get_statistics():
    """Get real statistics from database"""
    conn = sqlite3.connect('namaste_icd11.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT COUNT(*) FROM namaste_codes')
        total_namaste = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM namaste_codes WHERE system = "ayurveda"')
        ayurveda_codes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM namaste_codes WHERE system = "siddha"')
        siddha_codes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM namaste_codes WHERE system = "unani"')
        unani_codes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM icd11_tm2_codes')
        icd11_codes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM intelligent_mappings')
        mapped_codes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM fhir_resources')
        fhir_resources = cursor.fetchone()[0]
        
        stats = {
            'total_namaste_codes': total_namaste,
            'ayurveda_codes': ayurveda_codes,
            'siddha_codes': siddha_codes,
            'unani_codes': unani_codes,
            'icd11_codes': icd11_codes,
            'mapped_codes': mapped_codes,
            'fhir_resources': fhir_resources,
            'mapping_coverage': f"{round((mapped_codes / total_namaste * 100) if total_namaste > 0 else 0, 1)}%"
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/mapping')
def mapping_interface():
    return render_template('mapping.html')

if __name__ == '__main__':
    print("🚀 Starting NAMASTE-ICD11 Integration System...")
    print("📊 Access the application at: http://localhost:5000")
    print("💡 Make sure to upload your CSV files through the web interface")
    app.run(debug=True, port=5000, host='0.0.0.0')