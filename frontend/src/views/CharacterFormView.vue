<template>
  <div class="header">
    <button class="icon-btn header-back" @click="$router.back()">←</button>
    <span>{{ isEditMode ? "Charakter bearbeiten" : "Neuer Charakter" }}</span>

    <AsyncButton v-if="isEditMode" :action="confirmDelete" customClass="icon-btn header-delete"
      title="Charakter löschen">
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
          <input v-model="formData.name" type="text" required :disabled="isEditMode" />
          <small v-if="isEditMode" class="hint">Der Name kann nachträglich nicht geändert werden.</small>
        </div>

        <div class="form-group prompt-group">
          <label>System Prompt</label>
          <div class="prompt-editor-container">
            <div class="prompt-highlight-layer" ref="highlightLayerRef" v-html="highlightedPrompt"></div>
            
            <textarea 
              ref="textareaRef"
              v-model="formData.system_prompt" 
              required
              placeholder="Du bist ein hilfreicher Assistent..."
              spellcheck="false"
              @scroll="syncScroll"
            ></textarea>
          </div>
        </div>

        <div class="form-group">
          <label>Intro</label>
          <textarea
            v-model="formData.intro"
            class="intro-textarea"
            placeholder="Optionale Rahmenhandlung, die dem Modell vor der Zusammenfassung als Kontext mitgegeben wird."
          ></textarea>
          <small class="hint">
            Beschreibt das Setting bzw. die Rahmenhandlung des Rollenspiels. Wird vor der
            Zusammenfassung in den Chat injiziert und nicht in die Zusammenfassung einbezogen.
          </small>
        </div>

        <div class="form-group">
          <label>Plot</label>
          <textarea
            v-model="formData.plot"
            class="intro-textarea"
            placeholder="Handlung des Tages, die dem Modell als Vorgabe für den aktuellen Verlauf mitgegeben wird."
          ></textarea>
          <small class="hint">
            Gibt die Handlung des Tages vor. Wird nach Intro und Zusammenfassung
            mit &lt;plot&gt;-Tags in den Chat injiziert.
          </small>
        </div>

        <div class="form-group checkbox-group">
          <label>
            <input type="checkbox" v-model="formData.send_with_timestamp" />
            Zeitstempel bei Nachrichten mitsenden
          </label>
        </div>
        <div class="params-grid">

          <div class="form-group">
            <label>Inaktivität (Stunden)</label>
            <input v-model.number="idleThresholdHours" type="number" min="0.1" step="0.1" required />
            <small class="hint">Zeitspanne, nach der der Agent von sich aus das Gespräch sucht.</small>
          </div>

          <div class="form-group">
            <label>Temperature</label>
            <input v-model.number="formData.temperature" type="number" step="0.01" min="0" placeholder="z. B. 0.85" />
            <small class="hint">Höhere Werte machen die KI kreativer/zufälliger, niedrigere Werte präziser.</small>
          </div>

          <div class="form-group">
            <label>Min P</label>
            <input v-model.number="formData.min_p" type="number" step="0.01" min="0" max="1" placeholder="z. B. 0.1" />
            <small class="hint">Entfernt unwahrscheinliche Antworten basierend auf dem Top-Token. Verbessert die Stabilität.</small>
          </div>

          <div class="form-group">
            <label>Top P</label>
            <input v-model.number="formData.top_p" type="number" step="0.01" min="0" max="1" placeholder="z. B. 0.9" />
            <small class="hint">Begrenzt die Wortauswahl auf die wahrscheinlichsten Kandidaten (Nucleus Sampling).</small>
          </div>

          <div class="form-group">
            <label>Repeat Penalty</label>
            <input v-model.number="formData.repeat_penalty" type="number" step="0.01" min="0" placeholder="z. B. 1.1" />
            <small class="hint">Bestraft Wortwiederholungen. Ein Wert > 1.0 reduziert monotone Sätze.</small>
          </div>

          <div class="form-group">
            <label>Max output tokens</label>
            <input v-model.number="formData.max_tokens" type="number" step="512" min="4096" placeholder="z. B. 4096" />
            <small class="hint">Maximaler Output. 1 Token sind ca. 3.5 Zeichen.</small>
          </div>

          <div class="form-group">
            <label>Auto summarize</label>
            <input v-model.number="formData.auto_summarize_tokens" type="number" step="512" min="0" placeholder="z. B. 16384" />
            <small class="hint">Optional. Übersteigt die Context-Größe diesen Wert nach einer Antwort, wird automatisch eine Zusammenfassung erzeugt. Leer lassen, um die Funktion zu deaktivieren.</small>
          </div>
        </div>

        <div class="button-group">
          <AsyncButton type="submit" :action="save" customClass="btn-save">
            Speichern
          </AsyncButton>

          <AsyncButton v-if="isEditMode" type="button" :action="generateSummary" customClass="btn-secondary">
            Chat zusammenfassen
          </AsyncButton>
        </div>
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

const textareaRef = ref<HTMLTextAreaElement | null>(null);
const highlightLayerRef = ref<HTMLDivElement | null>(null);

// Tracks initial data loading state for edit mode
const isFetching = ref(false);

const formData = ref<Character>({
  name: "",
  system_prompt: "",
  intro: "",
  plot: "",
  send_with_timestamp: true,
  idle_threshold_ms: 3600000,
});

/**
 * Two-way bindings for translating milliseconds from the DTO to hours in the UI.
 */
const idleThresholdHours = computed({
  get: () => (formData.value.idle_threshold_ms || 3600000) / 3600000,
  set: (val: number) => {
    formData.value.idle_threshold_ms = Math.round(val * 3600000);
  }
});

/**
 * Computes the HTML string for syntax highlighting markdown styles.
 */
const highlightedPrompt = computed(() => {
  if (!formData.value.system_prompt) return "";
  
  let text = formData.value.system_prompt
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Highlight markdown headings
  text = text.replace(/^(#+\s+.*)$/gm, '<span class="md-heading">$&</span>');

  // Highlight markdown bold (**text**)
  text = text.replace(/\*\*([^\n]+?)\*\*/g, '<span class="md-bold">**$1**</span>');

  // Highlight markdown italic (*text*) using lookarounds to avoid conflicting with bold syntax
  text = text.replace(/(?<!\*)\*([^\n*]+?)\*(?!\*)/g, '<span class="md-italic">*$1*</span>');

  // Necessary to render trailing newlines accurately in the underlying div
  if (text.endsWith('\n')) {
      text += ' ';
  }

  return text;
});

/**
 * Synchronizes the scroll position between the invisible textarea and the formatting layer.
 */
const syncScroll = (e: Event) => {
  if (highlightLayerRef.value) {
    highlightLayerRef.value.scrollTop = (e.target as HTMLTextAreaElement).scrollTop;
  }
};

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
 * Optional numeric fields whose inputs may be cleared by the user.
 */
const NUMERIC_FIELDS = [
  "temperature",
  "min_p",
  "top_p",
  "repeat_penalty",
  "max_tokens",
  "auto_summarize_tokens",
] as const;

/**
 * Builds a clean payload for the API. The ``.number`` v-model modifier leaves
 * a cleared number input as an empty string, which the backend rejects with a
 * float_parsing error. Such values are normalized to null so the optional
 * fields are simply unset.
 */
const buildPayload = (): Character => {
  const payload: Record<string, unknown> = { ...formData.value };
  for (const field of NUMERIC_FIELDS) {
    const value = payload[field];
    if (value === "" || value === undefined || (typeof value === "number" && Number.isNaN(value))) {
      payload[field] = null;
    }
  }
  return payload as unknown as Character;
};

/**
 * Handles saving the character form. Creates a new record or updates an existing one, then navigates back.
 */
const save = async () => {
  const payload = buildPayload();
  if (isEditMode.value && characterName.value) {
    await formService.updateCharacter(characterName.value, payload);
  } else {
    await formService.createCharacter(payload);
  }
  router.back();
};

/**
 * Triggers a manual context window summarization for the current character.
 */
const generateSummary = async () => {
  if (!characterName.value) return;
  await formService.createSummary(characterName.value);
  alert("Die Zusammenfassung wurde erfolgreich erstellt.");
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
  line-height: 1.3;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.btn-save, .btn-secondary {
  padding: 12px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  width: 100%;
  font-size: 1.1rem;
  font-weight: bold;
  transition: background-color 0.2s;
}

.btn-save {
  background-color: #075e54;
  color: white;
}

.btn-save:hover:not(:disabled) {
  background-color: #128c7e;
}

.btn-secondary {
  background-color: #e0e0e0;
  color: #333;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #cccccc;
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
  overflow-y: auto;
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
  transition: min-height 0.25s ease;
}

.prompt-group:focus-within {
  /* Bequemerer Editier-Bereich, sobald der Cursor in der Textarea liegt. */
  min-height: min(70vh, 600px);
}

/* Prompt Editor Container - Overlay approach */
.prompt-editor-container {
  position: relative;
  flex: 1;
  display: flex;
  background: #fff;
  border: 1px solid #ccc;
  border-radius: 8px;
  overflow: hidden;
  /* Modern Monospace Font Stack mirroring IDE environments like VS Code */
  font-family: Consolas, Menlo, Monaco, "Ubuntu Mono", "Liberation Mono", monospace;
}

.prompt-highlight-layer,
.prompt-editor-container textarea {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  width: 100%; height: 100%;
  padding: 12px;
  margin: 0;
  border: none;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 14px; /* Default IDE font size */
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-y: auto;
}

.prompt-editor-container textarea {
  color: transparent;
  background: transparent;
  caret-color: #333;
  resize: none;
  outline: none;
}

.prompt-highlight-layer {
  color: #333;
  pointer-events: none;
}

/* Ensure selected text via transparent textarea shows background selection */
.prompt-editor-container textarea::selection {
  background-color: rgba(0, 120, 215, 0.3);
}

/* Highlighting styles injected into the layer */
:deep(.md-heading) {
  font-weight: bold;
  color: #075e54;
}

:deep(.md-bold) {
  font-weight: bold;
}

:deep(.md-italic) {
  font-style: italic;
}

.intro-textarea {
  min-height: 120px;
  resize: vertical;
  font-family: Consolas, Menlo, Monaco, "Ubuntu Mono", "Liberation Mono", monospace;
  font-size: 14px;
  line-height: 1.5;
  transition: min-height 0.25s ease;
}

.intro-textarea:focus {
  /* Auf Fokus wächst die Textarea, damit längere Rahmenhandlungen lesbar bleiben. */
  min-height: min(60vh, 420px);
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.params-grid .form-group {
  margin-bottom: 0;
}
</style>