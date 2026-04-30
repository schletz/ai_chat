<template>
  <!-- Transparent layer that closes the menu when the user clicks outside of it -->
  <div class="menu-backdrop" @click="$emit('close')"></div>
  <div class="header-menu" role="menu">
    <label class="menu-item menu-toggle" title="Zeitstempel bei Nachrichten mitsenden">
      <input type="checkbox" :checked="appendTimestamp"
        @change="$emit('toggle-timestamp', ($event.target as HTMLInputElement).checked)" />
      <span>Zeitstempel mitsenden</span>
    </label>
    <label class="menu-item menu-toggle" title="Reasoning-/Denk-Ausgabe des Modells aktivieren">
      <input type="checkbox" :checked="enableThinking"
        @change="$emit('toggle-thinking', ($event.target as HTMLInputElement).checked)" />
      <span>Reasoning aktivieren</span>
    </label>
    <button type="button" class="menu-item" :class="{ 'is-active': isDebugMode }" @click="$emit('toggle-debug')">
      <span class="menu-icon">🐛</span>
      <span>Debug-Nachrichten</span>
    </button>
    <button type="button" class="menu-item"
      :class="{ 'menu-item-cancel': isGeneratingPlot }"
      :title="isGeneratingPlot ? 'Plot-Generierung abbrechen' : 'Plot erzeugen'"
      @click="isGeneratingPlot ? $emit('cancel-director-plot') : $emit('generate-director-plot')">
      <span class="menu-icon">{{ isGeneratingPlot ? '🛑' : '🪄' }}</span>
      <span>{{ isGeneratingPlot ? 'Plot abbrechen' : 'Plot erzeugen' }}</span>
      <span v-if="isGeneratingPlot" class="menu-spinner" aria-hidden="true"></span>
    </button>
    <button type="button" class="menu-item" @click="$emit('open-context')">
      <span class="menu-icon">🔎</span>
      <span>Context anzeigen</span>
    </button>
    <button type="button" class="menu-item" @click="$emit('reset-kv-cache')">
      <span class="menu-icon">🧹</span>
      <span>KV Cache leeren</span>
    </button>
    <button type="button" class="menu-item menu-item-danger" @click="$emit('clear-history')">
      <span class="menu-icon">🗑️</span>
      <span>Verlauf löschen</span>
    </button>
    <button type="button" class="menu-item" @click="$emit('open-settings')">
      <span class="menu-icon">⚙️</span>
      <span>Einstellungen</span>
    </button>
  </div>
</template>

<script setup lang="ts">
/**
 * Burger submenu overlaid on the chat window. Purely presentational: it renders
 * the toggle and action items and forwards every interaction to the parent
 * header via events, leaving open/close state and side effects to the parent.
 */
defineProps<{
  /** Current append-timestamp flag, reflected by the toggle checkbox. */
  appendTimestamp: boolean;
  /** Current reasoning state, reflected by the thinking toggle checkbox. */
  enableThinking: boolean;
  /** Whether debug message mode is active, highlighting the debug item. */
  isDebugMode: boolean;
  /** Whether a director plot is currently being generated, showing an inline spinner. */
  isGeneratingPlot: boolean;
}>();

defineEmits<{
  /** Carries the desired new append-timestamp value after the user toggled it. */
  (e: "toggle-timestamp", value: boolean): void;
  /** Carries the desired new reasoning state after the user toggled it. */
  (e: "toggle-thinking", value: boolean): void;
  (e: "toggle-debug"): void;
  /** Requests generation of a single director plot. */
  (e: "generate-director-plot"): void;
  /** Requests aborting an in-flight director plot generation. */
  (e: "cancel-director-plot"): void;
  (e: "open-context"): void;
  /** Requests clearing of the model's KV cache on the server. */
  (e: "reset-kv-cache"): void;
  /** Requests deletion of the character's entire chat history. */
  (e: "clear-history"): void;
  (e: "open-settings"): void;
  (e: "close"): void;
}>();
</script>

<style scoped>
/* Transparent layer that closes the menu when the user clicks outside of it */
.menu-backdrop {
  position: fixed;
  inset: 0;
  background: transparent;
  z-index: 20;
}

/* Dropdown submenu overlaid on the chat window, anchored below the header */
.header-menu {
  position: absolute;
  top: 100%;
  right: 8px;
  min-width: 230px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  z-index: 30;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: none;
  background: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  color: #222;
  text-align: left;
  cursor: pointer;
}

.menu-item:hover {
  background: #f0f0f0;
}

.menu-item.is-active {
  background: #e1f3fb;
  color: #075e54;
  font-weight: 600;
}

/* Destructive action tinted red to warn before clearing the whole history. */
.menu-item-danger {
  color: #b3261e;
}

.menu-item-danger:hover {
  background: #fbeaea;
}

/* While the plot is generating the item turns into a cancel control, tinted to
   signal that clicking now aborts the running generation. */
.menu-item-cancel {
  color: #b3261e;
}

.menu-item-cancel:hover {
  background: #fbeaea;
}

/* While the plot is generating the item is inert; suppress the hover affordance. */
.menu-item:disabled {
  cursor: default;
}

.menu-item:disabled:hover {
  background: none;
}

/* Trailing loading indicator next to the "Plot erzeugen" label, tinted to stay
   visible on the light menu background. */
.menu-spinner {
  width: 16px;
  height: 16px;
  margin-left: auto;
  border: 2px solid rgba(7, 94, 84, 0.25);
  border-top-color: #075e54;
  border-radius: 50%;
  animation: menu-spin 1s linear infinite;
  flex-shrink: 0;
}

@keyframes menu-spin {
  to {
    transform: rotate(360deg);
  }
}

.menu-icon {
  font-size: 1.1rem;
  width: 1.4rem;
  text-align: center;
  flex-shrink: 0;
}

/* The timestamp toggle reuses the menu-item layout but hosts a native checkbox */
.menu-toggle {
  user-select: none;
}

.menu-toggle input {
  margin: 0;
  width: 16px;
  height: 16px;
  accent-color: #075e54;
  cursor: pointer;
  flex-shrink: 0;
}
</style>
