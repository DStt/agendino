/**
 * AgenDino — Login page logic
 */
(function () {
    "use strict";

    const form = document.getElementById("login-form");
    const usernameInput = document.getElementById("login-username");
    const passwordInput = document.getElementById("login-password");
    const submitBtn = document.getElementById("login-submit");
    const btnText = document.getElementById("login-btn-text");
    const btnSpinner = document.getElementById("login-btn-spinner");
    const errorBox = document.getElementById("login-error");
    const errorMsg = document.getElementById("login-error-msg");
    const togglePassword = document.getElementById("login-toggle-password");
    const card = document.getElementById("login-card");

    // ─── Password visibility toggle ───
    togglePassword.addEventListener("click", () => {
        const isPassword = passwordInput.type === "password";
        passwordInput.type = isPassword ? "text" : "password";
        togglePassword.querySelector("i").className = isPassword
            ? "bi bi-eye-slash-fill"
            : "bi bi-eye-fill";
    });

    // ─── Show / hide error ───
    function showError(msg) {
        errorMsg.textContent = msg;
        errorBox.classList.add("visible");
    }

    function hideError() {
        errorBox.classList.remove("visible");
    }

    // ─── Loading state ───
    function setLoading(loading) {
        submitBtn.disabled = loading;
        btnText.classList.toggle("d-none", loading);
        btnSpinner.classList.toggle("d-none", !loading);
        usernameInput.disabled = loading;
        passwordInput.disabled = loading;
    }

    // ─── Form submit ───
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideError();

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        if (!username || !password) {
            showError("Please enter both username and password.");
            return;
        }

        setLoading(true);

        try {
            const resp = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });

            const data = await resp.json();

            if (!resp.ok) {
                throw new Error(data.detail || "Authentication failed.");
            }


            // Visual success feedback
            card.classList.add("login-success");
            submitBtn.classList.add("login-btn--success");
            btnSpinner.classList.add("d-none");
            btnText.classList.remove("d-none");
            btnText.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>Welcome!';

            // Redirect after brief animation
            setTimeout(() => {
                window.location.href = "/";
            }, 600);
        } catch (err) {
            setLoading(false);
            showError(err.message || "An error occurred. Please try again.");
            // Shake the password field
            passwordInput.select();
        }
    });

    // ─── Clear error on typing ───
    usernameInput.addEventListener("input", hideError);
    passwordInput.addEventListener("input", hideError);

    // ─── Enter key handling ───
    usernameInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            passwordInput.focus();
        }
    });
})();
