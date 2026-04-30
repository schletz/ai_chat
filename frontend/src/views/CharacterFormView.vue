<template>
  <div class="header">
    <button class="icon-btn header-back" @click="$router.back()">←</button>
    <span>{{ isEditMode ? "Charakter bearbeiten" : "Neuer Charakter" }}</span>

    <AsyncButton v-if="isEditMode" :action="confirmDelete" customClass="icon-btn header-delete" title="Charakter löschen">
      🗑️
    </AsyncButton>
    <div v-else style="width: 30px"></div>
  </div>

  <div class="content form-content">
    <div class="box form-box">
      <div v-if="isFetching" style="text-align: center; padding: 20px; color: #666">
        Lade Daten...
      </div>

      <form v-else @submit.prevent class="flex-form">
        <div class="form-group">
          <label>Name</label>
          <input v-model="formData.name" type="text" required :disabled="isEditMode" placeholder="z.B. Dean" />
          <small v-if="isEditMode" class="hint">Der Name kann nachträglich nicht geändert werden.</small>
        </div>

        <div class="form-group prompt-group">
          <label>System Prompt</label>
          <textarea v-model="formData.system_prompt" required placeholder="Du bist ein hilfreicher Assistent..."></textarea>
        </div>

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" v-model="formData.send_with_timestamp" />
            Zeitstempel bei Nachrichten mitsenden
          </label>
        </div>

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

// Tracks initial data loading state for edit mode
const isFetching = ref(false);

const formData = ref<Character>({
  name: "",
  system_prompt: "",
  send_with_timestamp: true,
});

/**
 * Fetches existing character data on mount if in edit mode.
 */
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

/**
 * Handles saving the character form. Creates a new record or updates an existing one, then navigates back.
 */
const save = async () => {
  if (isEditMode.value && characterName.value) {
    await formService.updateCharacter(characterName.value, formData.value);
  } else {
    await formService.createCharacter(formData.value);
  }
  router.back();
};

/**
 * Prompts for confirmation before deleting the current character.
 */
const confirmDelete = async () => {
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

.form-box {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.flex-form {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.prompt-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 150px;
}

.prompt-group textarea {
  flex: 1;
  resize: none;
}
</style>