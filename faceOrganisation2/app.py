import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
import dlib
import numpy as np
import pickle
import firebase_admin
from firebase_admin import credentials, auth, storage

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads'
FACES_FOLDER = 'static/uploads/faces'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['FACES_FOLDER'] = FACES_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(FACES_FOLDER):
    os.makedirs(FACES_FOLDER)

# Initialize Firebase Admin SDK
cred = credentials.Certificate("faceorganisation2-firebase-adminsdk-b4vlh-74350c5f9b.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'faceorganisation2.appspot.com'
})
bucket = storage.bucket()

@app.context_processor
def utility_processor():
    return dict(enumerate=enumerate)

def list_directories_with_first_image(user_id, prefix):
    blobs = bucket.list_blobs(prefix=f"{user_id}/{prefix}", delimiter='/')
    directories = []
    for page in blobs.pages:
        for prefix in page.prefixes:
            dir_name = prefix.split('/')[-2]  # Extract directory name
            files = list_files_in_directory(prefix)  # Corrected: Use the prefix directly
            if files:
                first_image = files[0]  # Get the first image in the directory
                first_image_url = f"https://firebasestorage.googleapis.com/v0/b/faceorganisation2.appspot.com/o/{first_image.replace('/', '%2F')}?alt=media"
                directories.append({'name': dir_name, 'first_image': first_image_url})
           
    return directories








def get_id_token():
    id_token = session.get('id_token')
    if isinstance(id_token, bytes):
        id_token = id_token.decode('utf-8')
    return id_token

def get_authenticated_user_id():
    id_token = get_id_token()
    if id_token:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token['uid']
    return None

def list_files_in_directory(directory):
    blobs = bucket.list_blobs(prefix=directory)
    files = []
    for blob in blobs:
        if not blob.name.endswith('/'):
            files.append(blob.name)
    return files


def list_directories(user_id):
    blobs = bucket.list_blobs(prefix=f"{user_id}/organised_faces/", delimiter='/')
    directories = []
    for page in blobs.pages:
        for prefix in page.prefixes:
            dir_name = prefix.split('/')[-2]  # Extract directory name
            directories.append(dir_name)
    return directories

# Route to delete a single folder
@app.route('/delete_folder', methods=['POST'])
def delete_folder():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    folder_name = request.form['folder_name']

    # Delete all blobs in the specified folder
    blobs = bucket.list_blobs(prefix=f'{user_id}/organised_faces/{folder_name}/')
    for blob in blobs:
        blob.delete()

    flash(f'Folder "{folder_name}" has been deleted.', 'success')
    return redirect(url_for('image_library'))

# Route to delete all folders
@app.route('/delete_all_folders', methods=['POST'])
def delete_all_folders():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Delete all blobs in the user's organised_faces folder
    blobs = bucket.list_blobs(prefix=f'{user_id}/organised_faces/')
    for blob in blobs:
        blob.delete()

    flash('All folders have been deleted.', 'success')
    return redirect(url_for('image_library'))

# Initialize dlib's face detector and facial landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor('shape_predictor_68_face_landmarks.dat')
face_rec_model = dlib.face_recognition_model_v1('dlib_face_recognition_resnet_model_v1.dat')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_embedding(file_path):
    img = dlib.load_rgb_image(file_path)
    dets = detector(img, 1)
    if len(dets) == 0:
        raise Exception("No faces detected")
    shape = predictor(img, dets[0])
    face_descriptor = face_rec_model.compute_face_descriptor(img, shape)
    return np.array(face_descriptor)

def load_known_faces(user_id):
    blob = bucket.blob(f'{user_id}/known_faces.pkl')
    if blob.exists():
        data = blob.download_as_bytes()
        known_faces = pickle.loads(data)
    else:
        known_faces = {}
    return known_faces

def save_known_faces(known_faces, user_id):
    blob = bucket.blob(f'{user_id}/known_faces.pkl')
    data = pickle.dumps(known_faces)
    blob.upload_from_string(data)

def upload_to_firebase(file_path, destination_blob_name):
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file_path)
    os.remove(file_path)

def list_files_in_firebase(prefix):
    blobs = bucket.list_blobs(prefix=prefix)
    return [blob.name for blob in blobs]

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('introduction'))
    return redirect(url_for('dashboard'))

@app.route('/check_auth')
def check_auth():
    id_token = get_id_token()  # Ensure this fetches the ID token correctly
    if not id_token:
        return {"error": "ID token not found."}, 401

    try:
        decoded_token = auth.verify_id_token(id_token)
        user_id = decoded_token['uid']
        return {"user_id": user_id}, 200
    except Exception as e:
        return {"error": str(e)}, 401

@app.route('/view/<directory>')
def view_directory(directory):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    files = list_files_in_directory(f'{user_id}/organised_faces/{directory}')
    
    id_token = get_id_token()  # Ensure this fetches the ID token correctly
    
    image_urls = [
        f'https://firebasestorage.googleapis.com/v0/b/faceorganisation2.appspot.com/o/{file.replace("/", "%2F")}?alt=media' 
        for file in files
    ]

    return render_template('view.html', directory=directory, files=image_urls)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.create_user(email=email, password=password)
            flash('User successfully registered!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
    return render_template('register.html')

import requests

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.get_user_by_email(email)
            session['user_id'] = user.uid

            # Generate a custom token for the user
            custom_token = auth.create_custom_token(user.uid)

            # Exchange custom token for ID token
            api_key = "AIzaSyAr08dg03XcRcD2uk3s3Db9bXWMj3gx5Do"  # Replace with your Firebase project API key
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
            headers = {"Content-Type": "application/json"}
            data = {"token": custom_token.decode('utf-8'), "returnSecureToken": True}
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                id_token = response.json()['idToken']
                session['id_token'] = id_token
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error exchanging custom token for ID token.', 'danger')
        except Exception as e:
            flash('Invalid email or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('id_token', None)
    return redirect(url_for('introduction'))

@app.route('/introduction')
def introduction():
    return render_template('introduction.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = auth.get_user(session['user_id'])
    return render_template('dashboard.html', user_email=user.email)

@app.route('/image_library')
def image_library():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    directories_tab1 = list_directories_with_first_image(user_id, 'organised_faces/')
    directories_tab2 = list_directories_with_first_image(user_id, 'other_prefix/')  # Adjust 'other_prefix/' for actual data
    return render_template('image_library.html', directories_tab1=directories_tab1, directories_tab2=directories_tab2)


@app.route('/view_repository/<repository>')
def view_repository(repository):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    files = list_files_in_directory(f'{user_id}/organised_faces/{repository}')
    id_token = get_id_token()
    image_urls = [
        f'https://firebasestorage.googleapis.com/v0/b/faceorganisation2.appspot.com/o/{file.replace("/", "%2F")}?alt=media'
        for file in files
    ]
    return render_template('view_repository.html', repository=repository, files=image_urls)

@app.route('/rename_folders', methods=['POST'])
def rename_folders():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    directories = list_directories(user_id)

    new_names = request.form.getlist('new_name[]')
    for old_name, new_name in zip(directories, new_names):
        if new_name and new_name != old_name:
            blobs = list_files_in_directory(f'{user_id}/organised_faces/{old_name}')
            for blob_name in blobs:
                new_blob_name = blob_name.replace(f'{old_name}/', f'{new_name}/', 1)
                bucket.rename_blob(bucket.blob(blob_name), new_blob_name)
    return redirect(url_for('image_library'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        files = request.files.getlist('file')
        known_faces = load_known_faces(user_id)
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                try:
                    embedding = calculate_embedding(file_path)
                    recognized = False
                    for face_name, known_embedding in known_faces.items():
                        similarity = np.linalg.norm(embedding - known_embedding)
                        if (similarity < 0.525):
                            face_folder = f'{user_id}/organised_faces/{face_name}/'
                            upload_to_firebase(file_path, face_folder + filename)
                            flash(f'File "{filename}" successfully recognized as {face_name} and saved in {face_name} folder', 'success')
                            recognized = True
                            break

                    if not recognized:
                        new_face_id = len(known_faces) + 1
                        face_name = f'person_{new_face_id:02d}'  # Ensures the new face ID is zero-padded
                        face_folder = f'{user_id}/organised_faces/{face_name}/'
                        upload_to_firebase(file_path, face_folder + filename)
                        known_faces[face_name] = embedding
                        flash(f'File "{filename}" recognized as a new person and saved in {face_name} folder', 'success')

                except Exception as e:
                    if str(e) == "No faces detected":
                        os.remove(file_path)  # Remove the file if no faces are detected
                        flash(f'No faces detected in the image "{filename}". The file was ignored.', 'warning')
                    else:
                        flash(f'Error processing the image "{filename}": {e}', 'danger')

        save_known_faces(known_faces, user_id)
        return redirect(url_for('image_library'))

    return render_template('upload.html')


if __name__ == '__main__':
    app.run(debug=True)
