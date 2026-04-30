<template>
  <div class="header">
    <div class="header-left">
      <button class="icon-btn header-back" @click="$router.back()">←</button>
      <span class="header-title">{{ isEditMode ? "Charakter bearbeiten" : "Neuer Charakter" }}</span>
    </div>

    <div class="header-right">
      <AsyncButton type="button" :action="save" :disabled="isFetching" customClass="header-action header-save">
        Speichern
      </AsyncButton>

      <AsyncButton v-if="isEditMode" :action="confirmDelete" customClass="icon-btn header-delete"
        title="Charakter löschen">
        🗑️
      </AsyncButton>
    </div>
  </div>

  <div class="content form-content">
    <div class="box form-box">
      <div v-if="isFetching" style="text-align: center; padding: 20px; color: #666">
        Lade Daten...
      </div>

      <form v-else @submit.prevent class="flex-form">
        <div class="params-grid">
          <div class="form-group">
            <label>Name</label>
            <input v-model="formData.name" type="text" required :disabled="isEditMode" />
            <small v-if="isEditMode" class="hint">Der Name kann nachträglich nicht geändert werden.</small>
          </div>

          <div class="form-group">
            <label>Name des Characters</label>
            <input v-model="formData.character_name" type="text" />
            <small class="hint">Optional. Wird dem LLM in der History anstelle von ASSISTANT als Sprecher angezeigt. Leer lassen, um ASSISTANT zu verwenden.</small>
          </div>

          <div class="form-group">
            <label>Name des Users</label>
            <input v-model="formData.user_name" type="text" />
            <small class="hint">Optional. Wird dem LLM in der History anstelle von USER als Sprecher angezeigt. Leer lassen, um USER zu verwenden.</small>
          </div>
        </div>

        <div class="prompt-grid">
          <div class="system-prompt-cell">
            <div class="form-group prompt-group">
              <label>System Prompt</label>
              <textarea
                v-model="formData.system_prompt"
                class="prompt-textarea"
                required
                placeholder="Du bist ein hilfreicher Assistent..."
                spellcheck="false"
              ></textarea>
            </div>

            <div class="form-group checkbox-group">
              <label>
                <input type="checkbox" v-model="formData.append_timestamp" />
                Zeitstempel an jede User-Nachricht anhängen
              </label>
            </div>

            <div class="form-group checkbox-group">
              <label>
                <input type="checkbox" v-model="formData.reset_cache" />
                KV Cache vor jeder Nachricht leeren
              </label>
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
            <label>Prompt für die Plot-Generierung</label>
            <textarea
              v-model="formData.plot_generation_prompt"
              class="intro-textarea"
              placeholder="Anweisung, die nach der Chat-History angehängt wird und die Plot-Generierung auslöst. Leer lassen, um den Standard-Prompt zu verwenden."
            ></textarea>
            <small class="hint">
              Wird nach der Chat-History an das LLM angehängt und löst die Plot-Generierung aus.
              Die Anweisung steht so am Ende des Kontexts und wird durch die Nähe (Recency) besser
              beachtet als im System Prompt. Leer lassen, um den eingebauten Standard-Prompt zu
              verwenden. Der aktuelle Zeitpunkt kann mit <pre>${time}</pre> angegeben werden und wird automatisch ersetzt.
            </small>
          </div>

          <div class="form-group">
            <label>Sticky Note</label>
            <textarea
              v-model="formData.sticky_note"
              class="intro-textarea"
              placeholder="Eine Notiz, die das Rollenspiel steuert. Wird beim Generieren oder Einfügen eines Plots automatisch gesetzt."
            ></textarea>
            <div class="sticky-note-pos-row">
              <label>Position der Sticky Note</label>
              <input v-model.number="formData.sticky_note_pos" type="number" min="0" step="1" placeholder="z. B. 1" />
            </div>
            <small class="hint">
              Steuert die kommenden Antworten und wird beim Inferencing nahe dem Ende des Kontexts
              eingefügt. Ein guter Platz für einen Plot. Wird beim Generieren bzw. Einfügen eines
              Plots automatisch überschrieben. Leer lassen, um nichts einzufügen. Der aktuelle
              Zeitpunkt kann mit <pre>${time}</pre> angegeben werden und wird automatisch ersetzt.
              Die Position gibt an, dass die Note nach der n. letzten Usernachricht eingefügt wird.
              0 (Standard) sendet die Note als letzten Eintrag an das LLM, 1 setzt sie
              direkt nach die letzte User-Nachricht. Leer lassen entspricht 0.
            </small>
          </div>
        </div>

        <div class="params-grid">

          <div class="form-group">
            <label>Vollständig gesendete letzte Elemente</label>
            <input v-model.number="formData.full_history_for_last_n" type="number" min="0" step="1" placeholder="z. B. 1" />
            <small class="hint">
              Sendet diese Anzahl an Elementen vollständig, ältere Einträge werden je nach Alter ausgelassen. leer lassen, um alle zu senden.
            </small>
          </div>

          <div class="form-group">
            <label>Vollständig gesendete letzte Elemente (Plotgenerierung)</label>
            <input v-model.number="formData.full_history_for_last_n_plot_generation" type="number" min="0" step="1" placeholder="z. B. 16" />
            <small class="hint">
              Wie oben, jedoch nur für die Plotgenerierung. Hier ist meist mehr History
              sinnvoll; leer lassen, um alle zu senden.
            </small>
          </div>

          <div class="form-group">
            <label>Maximale History-Länge</label>
            <input v-model.number="formData.cap_history" type="number" min="0" step="1" placeholder="z. B. 50" />
            <small class="hint">
              Begrenzt die Gesamtzahl der zuletzt gesendeten History-Einträge (alle Rollen),
              die an das LLM übergeben werden; leer lassen, um die komplette History zu senden.
            </small>
          </div>

          <div class="form-group">
            <label>Inaktivität (Stunden)</label>
            <input v-model.number="idleThresholdHours" type="number" min="0.1" step="0.1" required />
            <small class="hint">Zeitspanne, nach der der Agent von sich aus das Gespräch sucht.</small>
          </div>

          <div class="form-group">
            <label>Time scale</label>
            <input v-model.number="formData.time_scale" type="number" step="0.1" min="0" placeholder="z. B. 1" />
            <small class="hint">
              Geschwindigkeit der virtuellen Uhr im Verhältnis zur Echtzeit; Werte &gt; 1 lassen
              die Zeit schneller, Werte &lt; 1 langsamer vergehen. Leer lassen entspricht 1 (Echtzeit).
            </small>
          </div>

          <div class="form-group">
            <label>Temperature</label>
            <input v-model.number="formData.temperature" type="number" step="0.01" min="0"
              :class="{ 'input-warning': paramWarnings.temperature }" placeholder="z. B. 0.85" />
            <small v-if="paramWarnings.temperature" class="warning-hint">{{ paramWarnings.temperature }}</small>
            <small class="hint">Höhere Werte machen die KI kreativer/zufälliger, niedrigere Werte präziser.</small>
          </div>

          <div class="form-group">
            <label>Min P</label>
            <input v-model.number="formData.min_p" type="number" step="0.01" min="0" max="1"
              :class="{ 'input-warning': paramWarnings.min_p }" placeholder="z. B. 0.1" />
            <small v-if="paramWarnings.min_p" class="warning-hint">{{ paramWarnings.min_p }}</small>
            <small class="hint">Entfernt unwahrscheinliche Tokens relativ zum Top-Token und verbessert so die Stabilität.</small>
          </div>

          <div class="form-group">
            <label>Top P</label>
            <input v-model.number="formData.top_p" type="number" step="0.01" min="0" max="1"
              :class="{ 'input-warning': paramWarnings.top_p }" placeholder="z. B. 0.9" />
            <small v-if="paramWarnings.top_p" class="warning-hint">{{ paramWarnings.top_p }}</small>
            <small class="hint">Begrenzt die Wortauswahl auf die wahrscheinlichsten Kandidaten (Nucleus Sampling).</small>
          </div>

          <div class="form-group">
            <label>Top K</label>
            <input v-model.number="formData.top_k" type="number" step="1" min="0" placeholder="z. B. 40" />
            <small class="hint">Begrenzt die Wortauswahl auf die K wahrscheinlichsten Tokens. 0 deaktiviert die Begrenzung; leer lassen, um den Standard des Modells zu verwenden.</small>
          </div>

          <div class="form-group">
            <label>Repeat Penalty</label>
            <input v-model.number="formData.repeat_penalty" type="number" step="0.01" min="0"
              :class="{ 'input-warning': paramWarnings.repeat_penalty }" placeholder="z. B. 1.1" />
            <small v-if="paramWarnings.repeat_penalty" class="warning-hint">{{ paramWarnings.repeat_penalty }}</small>
            <small class="hint">Bestraft Wortwiederholungen, ein Wert &gt; 1.0 reduziert monotone Sätze.</small>
          </div>

          <div class="form-group">
            <label>Frequency Penalty</label>
            <input v-model.number="formData.frequency_penalty" type="number" step="0.01"
              :class="{ 'input-warning': paramWarnings.frequency_penalty }" placeholder="z. B. 0.0" />
            <small v-if="paramWarnings.frequency_penalty" class="warning-hint">{{ paramWarnings.frequency_penalty }}</small>
            <small class="hint">Senkt die Wahrscheinlichkeit von Tokens, die bereits erschienen sind – je häufiger, desto stärker.</small>
          </div>

          <div class="form-group">
            <label>Presence Penalty</label>
            <input v-model.number="formData.presence_penalty" type="number" step="0.01"
              :class="{ 'input-warning': paramWarnings.presence_penalty }" placeholder="z. B. 0.0" />
            <small v-if="paramWarnings.presence_penalty" class="warning-hint">{{ paramWarnings.presence_penalty }}</small>
            <small class="hint">Bestraft Tokens allein dafür, dass sie überhaupt schon vorgekommen sind, und fördert so neue Themen.</small>
          </div>

          <div class="form-group">
            <label>Max output tokens</label>
            <input v-model.number="formData.max_tokens" type="number" step="512" min="4096" placeholder="z. B. 4096" />
            <small class="hint">Maximaler Output (1 Token entspricht ca. 3.5 Zeichen).</small>
          </div>
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

// Tracks initial data loading state for edit mode
const isFetching = ref(false);

const formData = ref<Character>({
  name: "",
  character_name: "",
  user_name: "",
  system_prompt: "",
  intro: "",
  plot_generation_prompt: "",
  sticky_note: "",
  sticky_note_pos: null,
  append_timestamp: true,
  reset_cache: false,
  idle_threshold_ms: 3600000,
  time_scale: null,
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
  "top_k",
  "repeat_penalty",
  "frequency_penalty",
  "presence_penalty",
  "max_tokens",
  "full_history_for_last_n",
  "full_history_for_last_n_plot_generation",
  "cap_history",
  "time_scale",
  "sticky_note_pos",
] as const;

/**
 * Sampling parameters whose value is technically accepted but usually points to
 * a configuration mistake. Each entry pairs a predicate that flags the suspicious
 * range with the explanation shown to the user. Cleared (empty/null) fields are
 * never flagged.
 */
const SUSPICIOUS_PARAMS: ReadonlyArray<{
  field: keyof Character;
  isSuspicious: (value: number) => boolean;
  message: string;
}> = [
  { field: "temperature", isSuspicious: (v) => v > 1, message: "Werte über 1 erzeugen meist unzusammenhängenden Text." },
  { field: "min_p", isSuspicious: (v) => v > 0.1, message: "Werte über 0.1 schneiden in der Regel zu viele Tokens ab." },
  { field: "top_p", isSuspicious: (v) => v < 0.9, message: "Werte unter 0.9 schränken die Wortauswahl meist zu stark ein." },
  { field: "frequency_penalty", isSuspicious: (v) => v > 1, message: "Werte über 1 wirken üblicherweise zu stark." },
  { field: "presence_penalty", isSuspicious: (v) => v > 1, message: "Werte über 1 wirken üblicherweise zu stark." },
  { field: "repeat_penalty", isSuspicious: (v) => v < 1, message: "Werte unter 1 fördern Wiederholungen, statt sie zu bestrafen." },
];

/**
 * Maps each parameter field to its warning message when the current value is
 * valid but likely a mistake, or to ``null`` when the value is unremarkable.
 * Drives both the input highlight and the inline warning hint in the template.
 */
const paramWarnings = computed<Record<string, string | null>>(() => {
  const warnings: Record<string, string | null> = {};
  for (const { field, isSuspicious, message } of SUSPICIOUS_PARAMS) {
    const value = formData.value[field];
    warnings[field] =
      typeof value === "number" && !Number.isNaN(value) && isSuspicious(value) ? message : null;
  }
  return warnings;
});

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

/* Highlights a parameter input whose value is valid but likely a mistake. */
.form-group input.input-warning {
  border: 1px solid #e6a700;
  background-color: #fff8e6;
}

.warning-hint {
  color: #b06f00;
  font-weight: bold;
  display: block;
  margin-top: 5px;
  font-size: 0.85rem;
  line-height: 1.3;
}

/* Header is split into a left (back + title) and right (actions) group so the
   save/delete buttons live in the top bar instead of at the bottom. */
.header-left {
  display: flex;
  align-items: center;
  min-width: 0;
}

.header-title {
  font-weight: bold;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.header-action {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: bold;
  white-space: nowrap;
  transition: background-color 0.2s;
}

.header-action:disabled {
  opacity: 0.6;
  cursor: default;
}

.header-save {
  background-color: #ffffff;
  color: #075e54;
}

.header-save:hover:not(:disabled) {
  background-color: #e6f0ee;
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
  flex-shrink: 0;
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

/* Compact header on phones so the back arrow stays visible next to the actions. */
@media (max-width: 600px) {
  .header {
    padding: 10px;
    gap: 8px;
  }

  .header-back {
    font-size: 1.3rem;
    padding: 0 6px 0 0;
  }

  .header-right {
    gap: 6px;
  }

  .header-action {
    padding: 6px 10px;
    font-size: 0.8rem;
  }

  .header-delete {
    font-size: 1.1rem;
  }
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

/* Wider grid for the multi-line text fields so they line up side by side on
   desktop (roughly two columns) while collapsing to a single column on
   narrow/mobile screens. ``min(70em, 100%)`` keeps the column from overflowing
   the viewport on small screens. */
.prompt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(50em, 100%), 1fr));
  gap: 15px;
  margin-bottom: 20px;
  align-items: start;
}

.prompt-grid .form-group {
  margin-bottom: 0;
}

/* Groups the system prompt with its timestamp checkbox in a single grid cell. */
.system-prompt-cell {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-group {
  display: flex;
  flex-direction: column;
  min-height: 150px;
  transition: min-height 0.25s ease;
}

.prompt-group:focus-within {
  /* Bequemerer Editier-Bereich, sobald der Cursor in der Textarea liegt. */
  min-height: min(70vh, 600px);
}

/* Plain system prompt editor without syntax highlighting for simpler mobile rendering. */
.form-group textarea.prompt-textarea {
  flex: 1;
  resize: none;
  outline: none;
  font-family: "Cascadia Code", "Cascadia Mono", "JetBrains Mono", "Fira Code", "SF Mono", Consolas, Menlo, Monaco, "Ubuntu Mono", "Liberation Mono", monospace;
  font-size: 13px;
  line-height: 1.5;
}

.form-group textarea.intro-textarea {
  min-height: 120px;
  resize: vertical;
  font-family: "Cascadia Code", "Cascadia Mono", "JetBrains Mono", "Fira Code", "SF Mono", Consolas, Menlo, Monaco, "Ubuntu Mono", "Liberation Mono", monospace;
  font-size: 13px;
  line-height: 1.5;
  transition: min-height 0.25s ease;
}

.form-group textarea.intro-textarea:focus {
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

/* Sticky note position sits directly below the sticky note textarea. Label and
   the numeric field share a single row; the shared explanation follows below.
   The input keeps the browser default size so it stays as compact as the other
   numeric parameter fields. */
.sticky-note-pos-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.sticky-note-pos-row label {
  margin-bottom: 0;
}
</style>