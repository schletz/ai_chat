<template>
  <div class="header">
    <button class="icon-btn header-back" @click="$router.back()">←</button>
    <span>Einstellungen</span>
    <div style="width: 30px"></div>
  </div>

  <div class="content">
    <div class="box">
      <h3>Verbindung</h3>
      <div class="form-group">
        <label>API URL</label>
        <input v-model="apiUrl" type="text" placeholder="https://localhost:8000" />
      </div>
      <button @click="save" class="btn-save">Speichern</button>
      <div v-if="saved" class="success-msg">✅ Gespeichert!</div>
    </div>

    <!-- NEU: Modell-Auswahl -->
    <div class="box" style="margin-top: 20px;">
      <h3>KI Modell</h3>
      <div v-if="isLoadingModels" style="color: #666;">Lade verfügbare Modelle...</div>

      <div v-else class="form-group">
        <label>Aktives Modell wählen</label>
        <select v-model="selectedModelId" class="model-select">
          <option v-for="model in availableModels" :key="model.id" :value="model.id">
            {{ model.id }}
          </option>
        </select>

        <small class="hint-text" v-if="selectedModel">
          {{ selectedModel.file_path }}
        </small>
      </div>

      <AsyncButton :action="changeModel" :disabled="selectedModelId === originalModelId" customClass="btn-save"
        style="margin-top: 10px;">
        {{ isRestarting ? 'Server startet neu...' : 'Modell wechseln' }}
      </AsyncButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { updateApiUrl, api } from "../api";
import AsyncButton from "../components/AsyncButton.vue";

const apiUrl = ref("");
const saved = ref(false);

// State für die Modelle
const availableModels = ref<any[]>([]);
const originalModelId = ref("");
const selectedModelId = ref("");
const isLoadingModels = ref(true);
const isRestarting = ref(false);

const selectedModel = computed(() => {
  return availableModels.value.find(m => m.id === selectedModelId.value);
});

onMounted(async () => {
  apiUrl.value = localStorage.getItem("api_url") || "https://localhost:8000";

  try {
    const response = await api.get('/system/models');
    availableModels.value = response.data.models;
    originalModelId.value = response.data.active_model_id;
    selectedModelId.value = originalModelId.value;
  } catch (error) {
    console.error("Fehler beim Laden der Modelle:", error);
  } finally {
    isLoadingModels.value = false;
  }
});

const save = () => {
  updateApiUrl(apiUrl.value);
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
};

const changeModel = async () => {
  isRestarting.value = true;
  try {
    // 1. Befehl an den Server schicken
    await api.post('/system/model', { model_id: selectedModelId.value });

    // 2. Dem Server Zeit geben, sich zu beenden und neu zu starten (z.B. 4 Sekunden)
    await new Promise(resolve => setTimeout(resolve, 4000));

    // 3. Frontend hart neu laden, um sauberen Zustand zu haben
    window.location.href = '/';
  } catch (error) {
    console.error("Fehler beim Modellwechsel:", error);
    alert("Fehler beim Wechseln des Modells.");
    isRestarting.value = false;
  }
};
</script>

<style scoped>
/* Bestehende Styles bleiben ... */
.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  box-sizing: border-box;
}

.btn-save {
  padding: 10px 15px;
  background-color: #075e54;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  width: 100%;
  font-size: 1rem;
  transition: background-color 0.2s;
}

.btn-save:disabled {
  background-color: #999;
  cursor: not-allowed;
}

.success-msg {
  margin-top: 10px;
  color: green;
  text-align: center;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: white;
}

.header-back {
  font-size: 1.5rem;
  padding: 0 10px 0 0;
}

/* NEU: Styles für das Dropdown */
.model-select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  font-size: 1rem;
  background-color: white;
  font-family: inherit;
}

.hint-text {
  display: block;
  margin-top: 5px;
  color: #888;
  font-size: 0.8rem;
  word-break: break-all;
}
</style>