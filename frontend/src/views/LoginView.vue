<template>
  <div class="login-container">
    <div class="box login-box">
      <h2 style="text-align: center; color: #075e54">Willkommen</h2>

      <form @submit.prevent>
        <div class="form-group">
          <label>Benutzername</label>
          <input v-model="username" type="text" required placeholder="username" />
        </div>
        <div class="form-group">
          <label>Passwort</label>
          <input v-model="password" type="password" required />
        </div>

        <div v-if="errorMessage" class="error">{{ errorMessage }}</div>

        <AsyncButton type="submit" :action="handleLogin" customClass="btn-primary">
          Einloggen
        </AsyncButton>
      </form>

      <div class="settings-link">
        <router-link to="/settings">⚙️ API-URL konfigurieren</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { LoginService } from "../services/LoginService";
import { api } from "../api";
import AsyncButton from "../components/AsyncButton.vue";

const router = useRouter();
const route = useRoute();
const loginService = new LoginService();

const username = ref("");
const password = ref("");
const errorMessage = ref("");

/**
 * Initializes the component and handles automatic credential restoration.
 * Checks for a certificate acceptance redirect parameter and restores saved credentials from session storage.
 */
onMounted(async () => {
  if (route.query.certificateAccepted) {
    username.value = sessionStorage.getItem("temp_user") || "";
    password.value = sessionStorage.getItem("temp_pass") || "";

    sessionStorage.removeItem("temp_user");
    sessionStorage.removeItem("temp_pass");

    router.replace("/login");

    if (username.value && password.value) {
      await handleLogin();
    }
  }
});

/**
 * Executes the login process and handles potential SSL/certificate errors.
 * Attempts standard authentication first. If a network error occurs, it triggers a browser-level certificate acceptance flow by redirecting to the backend.
 */
const handleLogin = async (): Promise<void> => {
  errorMessage.value = "";

  try {
    await loginService.login(username.value, password.value);
    router.push("/");
  } catch (error: any) {
    if (!error.response) {
      // Redirect to backend certificate acceptance flow on network failure
      const baseUrl = api.defaults.baseURL || "https://localhost:8000";
      const fullRedirectUrl = window.location.href;

      sessionStorage.setItem("temp_user", username.value);
      sessionStorage.setItem("temp_pass", password.value);

      window.location.href = `${baseUrl}/accept-cert?redirectUrl=${encodeURIComponent(fullRedirectUrl)}`;

      return new Promise<void>(() => {});
    }

    errorMessage.value = error.response?.data?.detail || "Login fehlgeschlagen.";
    throw error;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 20px;
  box-sizing: border-box;
}

.login-box {
  width: 100%;
  max-width: 400px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #333;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  box-sizing: border-box;
}

.error {
  color: red;
  margin-bottom: 15px;
  text-align: center;
  font-weight: bold;
}

.settings-link {
  text-align: center;
  margin-top: 20px;
  font-size: 0.9rem;
}

.settings-link a {
  color: #075e54;
  text-decoration: none;
}

.btn-primary {
  padding: 12px;
  background-color: #075e54;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  width: 100%;
  font-size: 1.1rem;
  font-weight: bold;
  transition: background-color 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background-color: #128c7e;
}
</style>