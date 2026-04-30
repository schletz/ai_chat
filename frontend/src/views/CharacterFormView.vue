<template>
  <div class="header">
    <button class="icon-btn header-back" @click="$router.back()">←</button>
    <span>{{ isEditMode ? "Charakter bearbeiten" : "Neuer Charakter" }}</span>

    <!-- Delete Button im Header über AsyncButton -->
    <AsyncButton v-if="isEditMode" :action="confirmDelete" customClass="icon-btn header-delete"
      title="Charakter löschen">
      🗑️
    </AsyncButton>
    <div v-else style="width: 30px"></div>
  </div>

  <div class="content form-content">
    <div class="box form-box">
      <!-- Kurzer Ladehinweis -->
      <div v-if="isFetching" style="text-align: center; padding: 20px; color: #666">
        Lade Daten...
      </div>

      <form v-else @submit.prevent class="flex-form">
        <div class="form-group">
          <label>Name</label>
          <input v-model="formData.name" type="text" required :disabled="isEditMode" placeholder="z.B. Dean" />
          <small v-if="isEditMode" class="hint">Der Name kann nachträglich nicht geändert werden.</small>
        </div>

        <!-- NEU: Diese Gruppe bekommt die Klasse prompt-group -->
        <div class="form-group prompt-group">
          <label>System Prompt</label>
          <textarea v-model="formData.system_prompt" required
            placeholder="Du bist ein hilfreicher Assistent..."></textarea>
        </div>

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" v-model="formData.send_with_timestamp" />
            Zeitstempel bei Nachrichten mitsenden
          </label>
        </div>

        <!-- Speichern Button über AsyncButton -->
        <AsyncButton type="submit" :action="save" customClass="btn-save">
          Speichern
        </AsyncButton>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { CharacterFormService } from "../services/CharacterFormService";
import { Character } from "../services/CharacterListService";
import AsyncButton from "../components/AsyncButton.vue";

const router = useRouter();
const route = useRoute();
const formService = new CharacterFormService();

const characterName = computed(() => route.params.name as string | undefined);
const isEditMode = computed(() => !!characterName.value);

// isFetching steuert nur das initiale Laden, wenn wir im Editier-Modus sind
const isFetching = ref(false);

const formData = ref<Character>({
  name: "",
  system_prompt: "",
  send_with_timestamp: true,
});

onMounted(async () => {
  if (isEditMode.value && characterName.value) {
    isFetching.value = true;
    try {
      const existingChar = await formService.getCharacter(characterName.value);
      if (existingChar) {
        formData.value = { ...existingChar };
      }
    } catch (error) {
      console.error("Fehler beim Laden des Charakters", error);
    } finally {
      isFetching.value = false;
    }
  }
});

const save = async () => {
  if (isEditMode.value && characterName.value) {
    await formService.updateCharacter(characterName.value, formData.value);
  } else {
    await formService.createCharacter(formData.value);
  }
  router.back();
};

const confirmDelete = async () => {
  // Wenn der User auf Abbrechen klickt, passiert nichts.
  // Der AsyncButton-Spinner verschwindet sofort wieder.
  if (confirm(`Möchtest du ${characterName.value} wirklich löschen?`)) {
    await formService.deleteCharacter(characterName.value!);
    router.push("/");
  }
};
</script>

<style scoped>
.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #333;
}

.form-group input[type="text"],
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ccc;
  border-radius: 8px;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 1rem;
}

.form-group input[type="text"]:disabled {
  background-color: #f5f5f5;
  color: #888;
  cursor: not-allowed;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  font-weight: normal;
  cursor: pointer;
  color: #333;
}

.checkbox-group input {
  margin-right: 10px;
  width: 18px;
  height: 18px;
  accent-color: #075e54;
}

.hint {
  color: #888;
  display: block;
  margin-top: 5px;
  font-size: 0.85rem;
}

/* Speichern Button */
.btn-save {
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

.btn-save:hover:not(:disabled) {
  background-color: #128c7e;
}

/* Header Icon Buttons */
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

.header-delete {
  font-size: 1.3rem;
  color: #ffcccc;
  transition: transform 0.2s;
}

.header-delete:hover:not(:disabled) {
  transform: scale(1.1);
  color: #ff4444;
}

.form-content {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 70px);
  box-sizing: border-box;
}

/* Die Box nimmt die volle Höhe ein */
.form-box {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  /* Wichtig, damit Flexbox bei kleinen Screens nicht überläuft */
}

/* Das Formular nimmt ebenfalls die volle Höhe der Box ein */
.flex-form {
  display: flex;
  flex-direction: column;
  flex: 1;
}

/* 
 * Der Magische Teil:
 * Diese Gruppe darf wachsen (flex: 1), die anderen behalten ihre normale Höhe!
 */
.prompt-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 150px;
  /* Eine garantierte Mindesthöhe für das Feld */
}

/* Die Textarea füllt den neu gewonnenen Platz exakt aus */
.prompt-group textarea {
  flex: 1;
  resize: none;
  /* Manuelles Skalieren ist jetzt unnötig */
}
</style>
