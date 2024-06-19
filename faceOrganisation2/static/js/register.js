// Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, createUserWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js"

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyAr08dg03XcRcD2uk3s3Db9bXWMj3gx5Do",
    authDomain: "faceorganisation2.firebaseapp.com",
    projectId: "faceorganisation2",
    storageBucket: "faceorganisation2.appspot.com",
    messagingSenderId: "134651752401",
    appId: "1:134651752401:web:3986b783a8ba4e316d3af0"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

//submit button
document.getElementById('submit').addEventListener("click", function (event) {
    event.preventDefault()

    //inputs
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    createUserWithEmailAndPassword(auth, email, password)
        .then((userCredential) => {
            const user = userCredential.user;
            alert("Creating Account...")
            //window.location.href = "/login"; // Redirect to login after successful registration
        })
        .catch((error) => {
            const errorCode = error.code;
            const errorMessage = error.message;
            alert(errorMessage)
        });
})
