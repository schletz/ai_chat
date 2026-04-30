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

      <AsyncButton
        :action="changeModel"
        :disabled="selectedModelId === originalModelId"
        customClass="btn-save"
        style="margin-top: 10px;"
      >
        {{ isRestarting ? 'Server startet neu...' : 'Modell wechseln' }}
      </AsyncButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { updateApiUrl, api } from "../api";
import AsyncButton from "../components/AsyncButton.vue";

/** Reactive state for API configuration and UI feedback */
const apiUrl = ref("");
const saved = ref(false);

/** Reactive state for model management */
const availableModels = ref<any[]>([]);
const originalModelId = ref("");
const selectedModelId = ref("");
const isLoadingModels = ref(true);
const isRestarting = ref(false);

/** Computed property to retrieve the currently selected model object */
const selectedModel = computed(() => {
  return availableModels.value.find(m => m.id === selectedModelId.value);
});

/** Initialize component state and fetch available models on mount */
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

/** Persist the API URL to local storage and show temporary success feedback */
const save = () => {
  updateApiUrl(apiUrl.value);
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
};

/** Trigger model change, wait for server restart, then reload the frontend */
const changeModel = async () => {
  isRestarting.value = true;
  try {
    // Send model selection command to the backend
    await api.post('/system/model', { model_id: selectedModelId.value });

    // Allow time for the server to terminate and restart
    await new Promise(resolve => setTimeout(resolve, 4000));

    // Hard reload frontend to ensure a clean state
    window.location.href = '/';
  } catch (error) {
    console.error("Fehler beim Modellwechsel:", error);
    alert("Fehler beim Wechseln des Modells.");
    isRestarting.value = false;
  }
};
</script>

<style scoped>
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