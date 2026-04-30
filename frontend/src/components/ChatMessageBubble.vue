<template>
  <div
    ref="bubbleRef"
    :class="['bubble', message.role, { 'is-editing': isEditing }]"
    :style="lockedWidth !== null ? { width: lockedWidth } : undefined"
    @dblclick="onActivateEdit"
    @touchstart="onTouchStart"
    @touchend="onTouchEnd"
    @touchcancel="onTouchEnd"
    @touchmove="onTouchEnd"
  >
    <template v-if="isEditing">
      <textarea
        ref="editorRef"
        v-model="draft"
        class="edit-textarea"
        @keydown="onEditorKeydown"
        @input="resizeEditor"
      ></textarea>
      <div class="msg-footer edit-footer">
        <button
          class="icon-btn cancel-btn"
          @click="cancelEdit"
          title="Abbrechen"
        >
          ✖
        </button>
        <button
          class="icon-btn save-btn"
          :disabled="!isDraftValid"
          @click="saveEdit"
          title="Speichern"
        >
          ✔
        </button>
      </div>
    </template>
    <template v-else>
      <div class="msg-content" v-html="formattedContent"></div>

      <div class="msg-footer">
        <span class="time">{{ formattedTime }}</span>
        <button
          v-if="canDelete"
          class="icon-btn delete-btn"
          @click="$emit('delete', message.timestamp)"
          :title="message.role === 'summary' ? 'Zusammenfassung löschen' : 'Delete message'"
        >
          🗑️
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from "vue";
import type { ChatMessage } from "../services/ChatService";

const props = defineProps<{
  message: ChatMessage;
}>();

const emit = defineEmits<{
  (e: "delete", timestamp: number): void;
  (e: "edit", timestamp: number, content: string): void;
}>();

const isEditing = ref(false);
const draft = ref("");
const editorRef = ref<HTMLTextAreaElement | null>(null);
const bubbleRef = ref<HTMLElement | null>(null);
// Pixel width captured from the rendered bubble before switching to edit mode.
// Locking it prevents the bubble from collapsing to the textarea's intrinsic size.
const lockedWidth = ref<string | null>(null);

// Tracks the timer used to detect a long press on touch devices so we can
// open the editor without requiring a hardware double-click.
const LONG_PRESS_MS = 500;
let longPressTimer: ReturnType<typeof setTimeout> | null = null;

/** Only user and assistant turns are editable; the summary has its own dedicated flow. */
const canEdit = computed(() => props.message.role === "user" || props.message.role === "assistant");

/** User messages and the synthetic summary bubble expose a delete affordance. */
const canDelete = computed(() => props.message.role === "user" || props.message.role === "summary");

const isDraftValid = computed(() => draft.value.trim().length > 0);

/**
 * Processes raw message content by escaping HTML and applying basic markdown formatting.
 */
const formattedContent = computed(() => {
  let text = props.message.content;

  // Escape HTML entities to prevent injection when rendering with v-html
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Apply markdown-like transformations for bold, italic, and inline code
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*(.*?)\*/g, "<em>$1</em>");
  text = text.replace(/`(.*?)`/g, "<code>$1</code>");

  // Normalize multiple consecutive newlines into a single newline for pre-wrap rendering
  return text.replace(/\n+/g, "\n");
});

/**
 * Formats the message timestamp into a localized time string. Prefers the
 * virtual (in-world) timestamp when one was recorded, falling back to the
 * real wall-clock timestamp otherwise. Assistant messages always reflect
 * real time and are tagged with "(RTC)" to make that explicit.
 */
const formattedTime = computed(() => {
  const displayTs = props.message.virtual_ts ?? props.message.timestamp;
  const date = new Date(displayTs);
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return props.message.role === "assistant" ? `${time} (RTC)` : time;
});

/** Sizes the textarea to fit its current content so the user sees the full message while editing. */
const resizeEditor = () => {
  const el = editorRef.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight}px`;
};

/** Switches the bubble into edit mode and primes the textarea with the current message text. */
const enterEditMode = async () => {
  if (!canEdit.value || isEditing.value) return;
  // Capture the rendered display width so the bubble keeps its size while the
  // textarea (with its narrow intrinsic width) takes over.
  if (bubbleRef.value) {
    lockedWidth.value = `${bubbleRef.value.offsetWidth}px`;
  }
  draft.value = props.message.content;
  isEditing.value = true;
  await nextTick();
  resizeEditor();
  editorRef.value?.focus();
};

const onActivateEdit = () => {
  enterEditMode();
};

const clearLongPressTimer = () => {
  if (longPressTimer !== null) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
};

const onTouchStart = () => {
  if (!canEdit.value || isEditing.value) return;
  clearLongPressTimer();
  longPressTimer = setTimeout(() => {
    longPressTimer = null;
    enterEditMode();
  }, LONG_PRESS_MS);
};

const onTouchEnd = () => {
  clearLongPressTimer();
};

const cancelEdit = () => {
  isEditing.value = false;
  lockedWidth.value = null;
  draft.value = "";
};

const saveEdit = () => {
  if (!isDraftValid.value) return;
  const trimmed = draft.value;
  isEditing.value = false;
  lockedWidth.value = null;
  if (trimmed === props.message.content) {
    return;
  }
  emit("edit", props.message.timestamp, trimmed);
};

const onEditorKeydown = (e: KeyboardEvent) => {
  if (e.key === "Escape") {
    e.preventDefault();
    cancelEdit();
    return;
  }
  // Ctrl/Cmd+Enter commits the edit; a bare Enter is allowed for newlines.
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    saveEdit();
  }
};

onBeforeUnmount(clearLongPressTimer);
</script>

<style scoped>
.bubble {
  max-width: 80%;
  padding: 10px 15px;
  border-radius: 15px;
  position: relative;
  word-wrap: break-word;
  user-select: text;
}

.user {
  align-self: flex-end;
  background-color: #dcf8c6;
  border-bottom-right-radius: 0;
}

.assistant {
  align-self: flex-start;
  background-color: white;
  border-bottom-left-radius: 0;
}

/* Styling for the injected summary bubble */
.summary {
  align-self: center;
  background-color: #e5e5ea;
  color: #333;
  border-radius: 12px;
  max-width: 90%;
  font-size: 0.9rem;
  box-shadow: inset 0 1px 2px rgba(255,255,255,0.5);
  border: 1px solid #d1d1d6;
}

.msg-content {
  white-space: pre-wrap;
  line-height: 1.2;
  color: black;
  font-weight: 500;
}

.summary .msg-content {
  color: #444;
  font-style: italic;
}

/* Vue :deep() selector required to style elements injected via v-html */
:deep(code) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
  color: #d63384;
}

:deep(strong) {
  font-weight: bold;
}

:deep(em) {
  font-style: italic;
}

.msg-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 0.75rem;
}

.user .msg-footer {
  color: #5b8c5a;
}

.assistant .msg-footer {
  color: #999;
}

.summary .msg-footer {
  color: #8e8e93;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
  font-size: 1rem;
  padding: 0;
}

.icon-btn:hover {
  opacity: 1;
}

.icon-btn:disabled {
  opacity: 0.25;
  cursor: default;
}

.delete-btn {
  font-size: 0.85rem;
  margin: 0;
}

.is-editing {
  outline: 2px solid #075e54;
  outline-offset: -2px;
}

.edit-textarea {
  width: 100%;
  min-height: 48px;
  resize: vertical;
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 6px 8px;
  font: inherit;
  line-height: 1.2;
  background: rgba(255, 255, 255, 0.85);
  color: black;
  box-sizing: border-box;
}

.edit-footer {
  margin-top: 6px;
}

.save-btn {
  color: #075e54;
}

.cancel-btn {
  color: #b34141;
}
</style>
