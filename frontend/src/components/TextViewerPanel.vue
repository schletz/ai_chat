<template>
  <div class="viewer-panel">
    <div class="viewer-header">
      <span class="viewer-title">{{ title }}</span>
      <div class="viewer-actions">
        <button type="button" class="viewer-copy-btn" :disabled="!copyable" @click="copyText"
          title="In die Zwischenablage kopieren" aria-label="Kopieren">
          {{ copied ? "✓ Kopiert" : "📋 Kopieren" }}
        </button>
        <button type="button" class="viewer-close-btn" @click="$emit('close')" title="Schließen"
          aria-label="Schließen">✕</button>
      </div>
    </div>
    <textarea class="viewer-textarea" readonly spellcheck="false" :value="text"></textarea>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

/**
 * Fullscreen overlay that shows a text in a read-only textarea with a copy and
 * a close button. It only renders what it is given; loading and visibility are
 * up to the parent, which reacts to the close event.
 */
const props = withDefaults(defineProps<{
  /** Caption shown in the header bar. */
  title: string;
  /** Text displayed in the read-only textarea. */
  text: string;
  /**
   * Whether the copy button is enabled. Parents disable it while ``text`` only
   * holds a loading or error notice instead of real content.
   */
  copyable?: boolean;
}>(), {
  copyable: true,
});

defineEmits<{
  /** Requests the panel be closed. */
  (e: "close"): void;
}>();

// Toggles the copy button label to a short success hint after copying.
const copied = ref(false);
let copiedResetTimer: ReturnType<typeof setTimeout> | undefined;

/**
 * Copies the displayed text to the clipboard, briefly flipping the button
 * label to a success hint. Falls back to a temporary textarea + execCommand
 * for non-secure contexts where the async Clipboard API is unavailable.
 */
async function copyText(): Promise<void> {
  if (!props.copyable) return;
  const text = props.text;
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
    console.error("Failed to copy text", error);
  }
}
</script>

<style scoped>
/* Fullscreen panel filling the entire viewport, since the texts are large */
.viewer-panel {
  position: fixed;
  inset: 0;
  background: #fff;
  display: flex;
  flex-direction: column;
  z-index: 50;
}

/* Header bar matching the app's primary color, hosting the close button */
.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 15px;
  background: #075e54;
  color: #fff;
  flex-shrink: 0;
}

.viewer-title {
  font-weight: bold;
  font-size: 1rem;
}

/* Right-aligned cluster holding the copy and close buttons */
.viewer-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.viewer-copy-btn {
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

.viewer-copy-btn:hover:not(:disabled) {
  opacity: 1;
  background: rgba(255, 255, 255, 0.25);
}

.viewer-copy-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.viewer-close-btn {
  background: none;
  border: none;
  color: #fff;
  font-size: 1.2rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0.85;
  padding: 0 4px;
}

.viewer-close-btn:hover {
  opacity: 1;
}

/* Read-only textarea consuming all remaining space below the header */
.viewer-textarea {
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
