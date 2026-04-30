<template>
  <div class="context-panel">
    <div class="context-header">
      <span class="context-title">🔎 Context</span>
      <div class="context-actions">
        <button type="button" class="context-copy-btn" :disabled="context === null" @click="copyContext"
          title="Context in die Zwischenablage kopieren" aria-label="Context kopieren">
          {{ copied ? "✓ Kopiert" : "📋 Kopieren" }}
        </button>
        <button type="button" class="context-close-btn" @click="$emit('close')" title="Schließen"
          aria-label="Schließen">✕</button>
      </div>
    </div>
    <textarea class="context-textarea" readonly spellcheck="false" :value="contextDisplay"></textarea>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { ChatService } from "../services/ChatService";

/**
 * Fullscreen overlay that shows the assembled chat context (optional intro and
 * the rolling-summary history, optionally prefixed with the virtual point in
 * time) in a read-only textarea for debugging and analysis. It owns the fetch
 * itself; the parent only toggles visibility and reacts to the close event.
 */
const props = defineProps<{
  /** Character name used to scope the context request to the right chat. */
  name: string;
  /**
   * Optional virtual time (ms since epoch) of the user-set "in-world" clock.
   * Forwarded to the backend so the context is prefixed with the matching point
   * in time. Null when no virtual clock is active.
   */
  baseTimestamp: number | null;
}>();

defineEmits<{
  /** Requests the panel be closed. */
  (e: "close"): void;
}>();

const chatService = new ChatService(props.name);

// Fetched context; null while loading. Errors are kept separately so the
// textarea can surface a notice instead of a blank panel.
const context = ref<string | null>(null);
const errorMessage = ref<string | null>(null);

// Toggles the copy button label to a short success hint after copying.
const copied = ref(false);
let copiedResetTimer: ReturnType<typeof setTimeout> | undefined;

// Resolves to a loading hint, the error notice, or the fetched context string.
const contextDisplay = computed(() => {
  if (errorMessage.value !== null) return errorMessage.value;
  if (context.value === null) return "Lade Context …";
  return context.value;
});

onMounted(async () => {
  try {
    context.value = await chatService.getContext(props.baseTimestamp);
  } catch (error) {
    console.error("Failed to load chat context", error);
    errorMessage.value = "Context konnte nicht geladen werden.";
  }
});

/**
 * Copies the fetched context to the clipboard, briefly flipping the button
 * label to a success hint. Falls back to a temporary textarea + execCommand
 * for non-secure contexts where the async Clipboard API is unavailable.
 */
async function copyContext(): Promise<void> {
  if (context.value === null) return;
  const text = context.value;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const helper = document.createElement("textarea");
      helper.value = text;
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      document.body.removeChild(helper);
    }
    copied.value = true;
    clearTimeout(copiedResetTimer);
    copiedResetTimer = setTimeout(() => (copied.value = false), 2000);
  } catch (error) {
    console.error("Failed to copy chat context", error);
  }
}
</script>

<style scoped>
/* Fullscreen panel filling the entire viewport, since the context is large */
.context-panel {
  position: fixed;
  inset: 0;
  background: #fff;
  display: flex;
  flex-direction: column;
  z-index: 50;
}

/* Header bar matching the app's primary color, hosting the close button */
.context-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 15px;
  background: #075e54;
  color: #fff;
  flex-shrink: 0;
}

.context-title {
  font-weight: bold;
  font-size: 1rem;
}

/* Right-aligned cluster holding the copy and close buttons */
.context-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.context-copy-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 4px;
  color: #fff;
  font-size: 0.8rem;
  line-height: 1;
  cursor: pointer;
  padding: 6px 10px;
  opacity: 0.9;
}

.context-copy-btn:hover:not(:disabled) {
  opacity: 1;
  background: rgba(255, 255, 255, 0.25);
}

.context-copy-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.context-close-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0.85;
  padding: 0 4px;
}

.context-close-btn:hover {
  opacity: 1;
}

/* Read-only textarea consuming all remaining space below the header */
.context-textarea {
  flex: 1;
  width: 100%;
  box-sizing: border-box;
  border: none;
  outline: none;
  resize: none;
  padding: 12px 15px;
  font-family: "Consolas", "Menlo", "Courier New", monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #222;
  background: #fafafa;
  white-space: pre-wrap;
  overflow: auto;
}
</style>
