<template>
  <div
    ref="bubbleRef"
    :class="['bubble', message.role, { 'is-editing': isEditing, 'is-scene-boundary': isLastSceneMessage }]"
    :style="lockedWidth !== null ? { width: lockedWidth } : undefined"
    @dblclick="onActivateEdit"
    @contextmenu.prevent="openContextMenu"
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

      <!-- Long-press / right-click context menu offering edit and scene-boundary actions. -->
      <template v-if="showContextMenu">
        <div class="context-menu-overlay" @click="closeContextMenu" @touchstart.stop.prevent="closeContextMenu"></div>
        <div class="context-menu" @click.stop>
          <button class="context-menu-item" @click="onMenuEdit">Editieren</button>
          <button
            class="context-menu-item"
            :class="{ active: isLastSceneMessage }"
            @click="onMenuToggleScene"
          >
            <span class="check">{{ isLastSceneMessage ? "✔" : "" }}</span>
            Letzte Szenennachricht
          </button>
        </div>
      </template>

      <div class="msg-footer">
        <span
          class="time"
          role="button"
          tabindex="0"
          title="Virtuelle Uhr auf diesen Zeitpunkt setzen"
          @click="onTimeClick"
          @keydown.enter="onTimeClick"
        >{{ formattedTime }}</span>
        <button
          v-if="canDelete"
          class="icon-btn delete-btn"
          @click="$emit('delete', message.timestamp)"
          title="Delete message"
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
  (e: "set-time", timestamp: number): void;
  (e: "toggle-scene", timestamp: number, lastSceneMessage: boolean): void;
}>();

const isEditing = ref(false);
// Whether the long-press / right-click context menu is currently shown.
const showContextMenu = ref(false);
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

/** Only user and assistant turns are editable. */
const canEdit = computed(() => props.message.role === "user" || props.message.role === "assistant");

/** User and assistant bubbles expose a delete affordance. */
const canDelete = computed(
  () => props.message.role === "user" || props.message.role === "assistant"
);

const isDraftValid = computed(() => draft.value.trim().length > 0);

/** Reflects whether this message is currently flagged as the scene boundary. */
const isLastSceneMessage = computed(() => props.message.last_scene_message === true);

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

/**
 * Sets the virtual clock to this message's displayed moment. Uses the same
 * timestamp the footer renders (virtual time when present, real time otherwise).
 */
const onTimeClick = () => {
  emit("set-time", props.message.virtual_ts ?? props.message.timestamp);
};

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
  if (!canEdit.value || isEditing.value || showContextMenu.value) return;
  clearLongPressTimer();
  longPressTimer = setTimeout(() => {
    longPressTimer = null;
    openContextMenu();
  }, LONG_PRESS_MS);
};

const onTouchEnd = () => {
  clearLongPressTimer();
};

/** Opens the context menu, unless the bubble is not editable or already in edit mode. */
const openContextMenu = () => {
  if (!canEdit.value || isEditing.value) return;
  showContextMenu.value = true;
};

const closeContextMenu = () => {
  showContextMenu.value = false;
};

/** Context menu action: switch the bubble into edit mode. */
const onMenuEdit = () => {
  closeContextMenu();
  enterEditMode();
};

/** Context menu action: toggle this message's scene-boundary flag. */
const onMenuToggleScene = () => {
  closeContextMenu();
  emit("toggle-scene", props.message.timestamp, !isLastSceneMessage.value);
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

.msg-content {
  white-space: pre-wrap;
  line-height: 1.2;
  color: black;
  font-weight: 500;
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

.time {
  cursor: pointer;
}

.time:hover {
  text-decoration: underline;
}

.user .msg-footer {
  color: #5b8c5a;
}

.assistant .msg-footer {
  color: #999;
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

/* Marks the message the current scene starts after, with a bold bottom border. */
.is-scene-boundary {
  border-bottom: 4px solid #075e54;
}

/* Transparent full-screen catcher that closes the menu on an outside tap. */
.context-menu-overlay {
  position: fixed;
  inset: 0;
  z-index: 10;
}

.context-menu {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 11;
  display: flex;
  flex-direction: column;
  min-width: 180px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: none;
  border: none;
  text-align: left;
  font: inherit;
  color: #222;
  cursor: pointer;
  white-space: nowrap;
}

.context-menu-item:hover {
  background: rgba(0, 0, 0, 0.06);
}

.context-menu-item.active {
  font-weight: 600;
  color: #075e54;
}

.context-menu-item .check {
  display: inline-block;
  width: 1em;
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
