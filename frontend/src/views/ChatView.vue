<template>
  <div class="header">
    <button class="icon-btn header-back" @click="$router.push('/')" title="Zurück" aria-label="Zurück">←</button>
    <div class="header-title">
      <span class="header-name">{{ name }}</span>
      <button class="clock-display" :class="{ 'is-virtual': baseTimestamp !== null }"
        @click="toggleTimePicker" :title="baseTimestamp !== null ? 'Virtuelle Zeit aktiv – klicken zum Anpassen' : 'Basiszeit setzen'">
        <span class="clock-icon">{{ baseTimestamp !== null ? "⏱" : "🕒" }}</span>
        <span class="clock-text">{{ formattedVirtualTime }}</span>
      </button>
    </div>

    <div class="header-right">
      <span v-if="contextTokens !== null" class="token-display"
        :title="`Tokens im aktuellen Kontext: ${contextTokens.toLocaleString('de-DE')}`">
        <span class="token-icon">🧮</span>
        <span class="token-text">{{ contextTokens.toLocaleString('de-DE') }}</span>
      </span>
      <label class="timestamp-toggle" title="Zeitstempel bei Nachrichten mitsenden">
        <input type="checkbox" v-model="sendWithTimestamp" @change="onSendWithTimestampChange" />
        <span class="timestamp-toggle-label">TS</span>
      </label>
      <button @click="toggleDebug" :class="['icon-btn', 'debug-btn', { 'is-active': isDebugMode }]"
        title="Toggle Debug Messages">
        🐛
      </button>
      <button class="icon-btn" style="color: white" @click="exportChat" title="Chatverlauf als XML exportieren"
        aria-label="Chatverlauf exportieren">💾</button>
      <button class="icon-btn" style="color: white" @click="$router.push(`/character/${name}/edit`)">⚙️</button>
    </div>
  </div>

  <div v-if="showTimePicker" class="time-picker-popover">
    <label class="time-picker-label">Basiszeit setzen</label>
    <input type="datetime-local" v-model="timePickerInput" class="time-picker-input" />
    <div class="time-picker-actions">
      <button type="button" class="tp-btn tp-btn-primary" @click="applyBaseTime" :disabled="!timePickerInput">
        Übernehmen
      </button>
      <button v-if="baseTimestamp !== null" type="button" class="tp-btn tp-btn-danger" @click="clearBaseTime">
        Uhr deaktivieren
      </button>
      <button type="button" class="tp-btn tp-btn-secondary" @click="showTimePicker = false">
        Schließen
      </button>
    </div>
  </div>

  <div class="content chat-window" ref="chatContainer">
    <template v-for="(msg, index) in messages" :key="msg.timestamp">
      <div v-if="showDateSeparator(index)" class="date-separator">
        <span>{{ formatDateSeparator(displayTimestamp(msg)) }}</span>
      </div>

      <ChatMessageBubble :message="msg" @delete="deleteMsg" @edit="editMsg" />
    </template>
  </div>

  <div class="input-area">
    <AsyncButton v-if="messages.length > 0" :action="recreate" customClass="action-btn" :title="messages[messages.length - 1].role === 'assistant'
      ? 'Neu generieren'
      : 'Antworten'
      ">
      {{ messages[messages.length - 1].role === "assistant" ? "↻" : "↩" }}
    </AsyncButton>

    <textarea ref="messageInput" v-model="newMessage"
      @keydown="handleKeydown"
      placeholder="Nachricht..." rows="2"></textarea>

    <AsyncButton ref="sendButtonRef" :action="send" :disabled="!newMessage.trim()" customClass="action-btn send-btn"
      title="Senden">
      ➤
    </AsyncButton>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { ChatService, ChatMessage } from "../services/ChatService";
import { CharacterFormService } from "../services/CharacterFormService";
import AsyncButton from "../components/AsyncButton.vue";
import ChatMessageBubble from "../components/ChatMessageBubble.vue";

const props = defineProps<{ name: string }>();
const chatService = new ChatService(props.name);
const formService = new CharacterFormService();

const messages = ref<ChatMessage[]>([]);
const newMessage = ref("");
const chatContainer = ref<HTMLElement | null>(null);
const messageInput = ref<HTMLTextAreaElement | null>(null);

const sendButtonRef = ref<InstanceType<typeof AsyncButton> | null>(null);

// Reactive state for debug flag, base timestamp for rolling window, and the injected summary message
const isDebugMode = ref(false);
const summaryBaseTimestamp = ref(0);
const summaryMessage = ref<ChatMessage | null>(null);

// Latest total_tokens reported by the server after an assistant turn. Used to
// surface how full the model context currently is. Null until the first send.
const contextTokens = ref<number | null>(null);

// Mirrors the character's send_with_timestamp setting; toggling persists via the PATCH endpoint
const sendWithTimestamp = ref(true);

// Virtual clock state. baseTimestamp holds the user-defined "in-world" anchor (ms);
// virtualClockRealAnchor is the wall-clock moment that anchor was applied. The displayed
// time advances in real time from this anchor.
const baseTimestamp = ref<number | null>(null);
const virtualClockRealAnchor = ref<number>(0);
const nowTick = ref<number>(Date.now());
const showTimePicker = ref(false);
const timePickerInput = ref<string>("");
let clockInterval: ReturnType<typeof setInterval> | null = null;

// LocalStorage key scoped per-character, so each chat keeps its own virtual clock.
const virtualClockStorageKey = `virtualClock:${props.name}`;

interface StoredVirtualClock {
  baseTimestamp: number;
  anchorTimestamp: number;
}

/**
 * Restores a previously persisted virtual clock for this chat from localStorage.
 * Silently ignores malformed payloads so a corrupted entry never blocks the chat UI.
 */
const restoreVirtualClock = () => {
  try {
    const raw = localStorage.getItem(virtualClockStorageKey);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Partial<StoredVirtualClock>;
    if (typeof parsed?.baseTimestamp === "number" && typeof parsed?.anchorTimestamp === "number") {
      baseTimestamp.value = parsed.baseTimestamp;
      virtualClockRealAnchor.value = parsed.anchorTimestamp;
    }
  } catch (error) {
    console.warn("Failed to restore virtual clock state", error);
  }
};

/** Persists the active anchor pair so the virtual clock survives a page reload. */
const persistVirtualClock = () => {
  if (baseTimestamp.value === null) {
    localStorage.removeItem(virtualClockStorageKey);
    return;
  }
  const payload: StoredVirtualClock = {
    baseTimestamp: baseTimestamp.value,
    anchorTimestamp: virtualClockRealAnchor.value,
  };
  localStorage.setItem(virtualClockStorageKey, JSON.stringify(payload));
};

/** Toggles the debug mode and reloads the chat to fetch unfiltered history. */
const toggleDebug = async () => {
  isDebugMode.value = !isDebugMode.value;
  await loadChat();
};

/**
 * Initializes the chat by first checking if a summary exists to set the starting timestamp, 
 * preventing the loading of old summarized messages, and creating the synthetic summary message.
 */
const initChat = async () => {
  try {
    const character = await formService.getCharacter(props.name);
    if (character) {
      sendWithTimestamp.value = character.send_with_timestamp;
    }
    if (character?.summary?.timestamp) {
      summaryBaseTimestamp.value = character.summary.timestamp;

      // Create a synthetic message to display the summary at the top of the chat
      summaryMessage.value = {
        timestamp: character.summary.timestamp,
        role: "summary",
        content: `**Zusammenfassung des vorherigen Verlaufs:**\n\n${character.summary.text}`
      };
    }
  } catch (error) {
    console.error("Failed to fetch character configuration for initialization.", error);
  }
  await loadChat();
};

/**
 * Persists the toggled send_with_timestamp flag for the character. Reverts the
 * checkbox state if the API call fails so the UI never drifts from the backend.
 */
const onSendWithTimestampChange = async () => {
  const newValue = sendWithTimestamp.value;
  try {
    await formService.updateSendWithTimestamp(props.name, newValue);
  } catch (error) {
    console.error("Failed to update send_with_timestamp", error);
    sendWithTimestamp.value = !newValue;
  }
};

/** Loads the chat history respecting the rolling window base timestamp and prepends the summary. */
const loadChat = async () => {
  const history = await chatService.getHistory(summaryBaseTimestamp.value, isDebugMode.value);
  
  // Prepend the synthetic summary message if it exists
  if (summaryMessage.value) {
    messages.value = [summaryMessage.value, ...history];
  } else {
    messages.value = history;
  }
  
  scrollToBottom();
};

/** Handles keyboard events, triggering the send action on Enter. */
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();

    // Programmatically trigger the send button when text is present
    if (newMessage.value.trim() && sendButtonRef.value) {
      const btnElement = sendButtonRef.value.$el as HTMLButtonElement;
      if (btnElement && !btnElement.disabled) {
        btnElement.click();
      }
    }
  }
};

/** Dynamically adjusts the textarea height to fit content up to a maximum. */
const autoResize = () => {
  if (!messageInput.value) return;
  const el = messageInput.value;
  const maxHeight = 120;

  // Once the textarea has hit max-height and the content overflows, every
  // keystroke only makes scrollHeight grow further. Skipping the reset-and-
  // measure cycle here avoids a visible layout jump on mobile, where the
  // intermediate "auto" state can briefly render before the final height is
  // re-applied. Shrinking is still handled because scrollHeight drops back
  // to clientHeight as soon as the content fits again.
  if (el.scrollHeight > el.clientHeight && el.style.height === `${maxHeight}px`) {
    return;
  }

  el.style.height = "auto";
  const newHeight = Math.min(el.scrollHeight, maxHeight);
  el.style.height = `${newHeight}px`;
};

/** Scrolls the chat container to the bottom after a DOM update cycle. */
const scrollToBottom = async () => {
  await nextTick();
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
};

/** Returns the timestamp used for display (virtual when present, real otherwise). */
const displayTimestamp = (msg: ChatMessage) => msg.virtual_ts ?? msg.timestamp;

/**
 * Determines whether to render a date separator for the given message index.
 * Separators are anchored to user messages only — assistant timestamps run on
 * the real clock and would otherwise cause spurious day-flips when the user
 * runs the conversation on a virtual clock.
 */
const showDateSeparator = (index: number) => {
  const msg = messages.value[index];
  if (msg.role !== "user") return false;

  // Locate the most recent prior user message to compare day boundaries against.
  let prevUserMsg: ChatMessage | null = null;
  for (let i = index - 1; i >= 0; i--) {
    if (messages.value[i].role === "user") {
      prevUserMsg = messages.value[i];
      break;
    }
  }
  if (prevUserMsg === null) return true;

  const currentDate = new Date(displayTimestamp(msg)).setHours(0, 0, 0, 0);
  const prevDate = new Date(displayTimestamp(prevUserMsg)).setHours(0, 0, 0, 0);

  return currentDate !== prevDate;
};

/** Formats a message timestamp into a localized date header string. */
const formatDateSeparator = (timestamp: number) => {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) {
    return "Heute";
  } else if (date.toDateString() === yesterday.toDateString()) {
    return "Gestern";
  } else {
    return date.toLocaleDateString("de-DE", {
      weekday: "long",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }
};

/**
 * Computes the current virtual time. Returns the user-anchored time advanced by the
 * elapsed real-time delta since anchoring, or the system clock when no anchor is set.
 * Reads nowTick to remain reactive against the per-second tick.
 */
const currentVirtualTimestamp = computed<number>(() => {
  const tick = nowTick.value;
  if (baseTimestamp.value === null) {
    return tick;
  }
  return baseTimestamp.value + (tick - virtualClockRealAnchor.value);
});

/** Formats the virtual clock for display in the header. */
const formattedVirtualTime = computed<string>(() => {
  const d = new Date(currentVirtualTimestamp.value);
  return d.toLocaleString("de-DE", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
});

/**
 * Converts an absolute ms timestamp into the format consumed by the
 * native datetime-local input ("YYYY-MM-DDTHH:mm").
 */
const tsToInputString = (ts: number): string => {
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/** Toggles the visibility of the time picker popover, prefilling the current value. */
const toggleTimePicker = () => {
  if (!showTimePicker.value) {
    timePickerInput.value = tsToInputString(currentVirtualTimestamp.value);
  }
  showTimePicker.value = !showTimePicker.value;
};

/** Anchors the virtual clock to the user-selected datetime and starts ticking forward. */
const applyBaseTime = () => {
  if (!timePickerInput.value) return;
  const parsed = new Date(timePickerInput.value).getTime();
  if (Number.isNaN(parsed)) return;
  baseTimestamp.value = parsed;
  virtualClockRealAnchor.value = Date.now();
  nowTick.value = virtualClockRealAnchor.value;
  persistVirtualClock();
  showTimePicker.value = false;
};

/**
 * Releases the virtual clock so the header reflects the actual system time and
 * outgoing messages no longer carry a base_timestamp.
 */
const clearBaseTime = () => {
  baseTimestamp.value = null;
  virtualClockRealAnchor.value = 0;
  nowTick.value = Date.now();
  persistVirtualClock();
  showTimePicker.value = false;
};

/** Handles sending a user message and refreshing the chat state. */
const send = async () => {
  const text = newMessage.value;
  newMessage.value = "";

  if (messageInput.value) messageInput.value.style.height = "auto";

  const outgoingTs = baseTimestamp.value !== null ? currentVirtualTimestamp.value : null;

  // Optimistically update UI before awaiting server response
  const optimisticMessage: ChatMessage = { timestamp: Date.now(), role: "user", content: text };
  if (outgoingTs !== null) {
    optimisticMessage.virtual_ts = outgoingTs;
  }
  messages.value.push(optimisticMessage);
  scrollToBottom();

  const result = await chatService.sendMessage(text, outgoingTs);
  contextTokens.value = result.total_tokens;
  await loadChat();
};

/**
 * Removes a message by timestamp. The synthetic summary bubble is cleared via a
 * PATCH to the character endpoint, while regular chat messages go through the
 * chat-history delete endpoint.
 */
const deleteMsg = async (timestamp: number) => {
  if (summaryMessage.value && summaryMessage.value.timestamp === timestamp) {
    try {
      await formService.updateSummary(props.name, "");
      summaryMessage.value = null;
      summaryBaseTimestamp.value = 0;
    } catch (error) {
      console.error("Failed to clear summary", error);
      return;
    }
    await loadChat();
    return;
  }

  await chatService.deleteMessage(timestamp);
  await loadChat();
};

/** Persists an edited message via PATCH and refreshes the chat list. */
const editMsg = async (timestamp: number, content: string) => {
  try {
    await chatService.updateMessage(timestamp, content);
  } catch (error) {
    console.error("Failed to update message", error);
    return;
  }
  await loadChat();
};

/** Triggers regeneration of the most recent assistant message. */
const recreate = async () => {
  const result = await chatService.recreateAnswer();
  contextTokens.value = result.total_tokens;
  await loadChat();
};

/**
 * Escapes the CDATA terminator inside a payload by splitting it across two CDATA
 * sections. Without this, a literal "]]>" in user content would close the section
 * prematurely and produce invalid XML.
 */
const escapeCdata = (text: string): string => text.replace(/]]>/g, "]]]]><![CDATA[>");

/** Builds the XML document for the export, including only user and assistant turns. */
const buildChatXml = (history: ChatMessage[]): string => {
  const lines: string[] = ['<?xml version="1.0" encoding="UTF-8"?>', "<chat>"];
  for (const msg of history) {
    if (msg.role !== "user" && msg.role !== "assistant") continue;
    lines.push(`    <${msg.role}>`);
    lines.push("    <![CDATA[");
    lines.push(escapeCdata(msg.content));
    lines.push("    ]]>");
    lines.push(`    </${msg.role}>`);
  }
  lines.push("</chat>");
  return lines.join("\n");
};

/** Sanitizes a string so it can safely appear in a filename across operating systems. */
const sanitizeFilename = (value: string): string => value.replace(/[\\/:*?"<>|]+/g, "_");

/**
 * Persists the XML to disk via the native "Save As" dialog. Falls back to a
 * download anchor when the File System Access API is unavailable (Firefox/Safari).
 */
const saveXmlToFile = async (xml: string, suggestedName: string): Promise<void> => {
  const fsWindow = window as Window & {
    showSaveFilePicker?: (options: {
      suggestedName?: string;
      types?: Array<{ description?: string; accept: Record<string, string[]> }>;
    }) => Promise<{
      createWritable: () => Promise<{ write: (data: BlobPart) => Promise<void>; close: () => Promise<void> }>;
    }>;
  };

  if (typeof fsWindow.showSaveFilePicker === "function") {
    try {
      const handle = await fsWindow.showSaveFilePicker({
        suggestedName,
        types: [{ description: "XML-Datei", accept: { "application/xml": [".xml"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(xml);
      await writable.close();
      return;
    } catch (error) {
      // User cancelled the picker — silently abort the export.
      if ((error as DOMException)?.name === "AbortError") return;
      console.warn("File System Access API unavailable, falling back to download.", error);
    }
  }

  const blob = new Blob([xml], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = suggestedName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
};

/** Fetches the full chat history (including debug entries) and exports it as XML. */
const exportChat = async () => {
  try {
    const history = await chatService.getHistory(0, true);
    const xml = buildChatXml(history);
    const datePart = new Date().toISOString().slice(0, 10);
    const suggestedName = sanitizeFilename(`chat-${props.name}-${datePart}.xml`);
    await saveXmlToFile(xml, suggestedName);
  } catch (error) {
    console.error("Failed to export chat history", error);
  }
};

// Start the initialization sequence on mount
onMounted(() => {
  // Restore any persisted clock first so the header reflects the saved state immediately.
  restoreVirtualClock();
  initChat();
  // Drive the virtual-clock display once per second.
  clockInterval = setInterval(() => {
    nowTick.value = Date.now();
  }, 1000);
});

onBeforeUnmount(() => {
  if (clockInterval !== null) {
    clearInterval(clockInterval);
    clockInterval = null;
  }
});
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-area {
  padding: 10px;
  background: #f0f0f0;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-area input {
  flex: 1;
  padding: 12px 15px;
  border-radius: 25px;
  border: 1px solid #ccc;
  font-size: 1rem;
  outline: none;
}

/* Neue Button Styles */
.action-btn {
  width: 45px;
  height: 45px;
  box-sizing: border-box;
  border-radius: 50%;
  border: none;
  background-color: #075e54;
  color: white;
  font-size: 1.2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background-color 0.2s;
}

.action-btn:disabled {
  background-color: #a0a0a0;
  cursor: default;
}

.action-btn:active:not(:disabled) {
  background-color: #128c7e;
}

.send-btn {
  font-size: 1.4rem;
  padding-left: 4px;
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

/* Compact checkbox pill that lives in the chat header next to the icon buttons */
.timestamp-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: white;
  font-size: 0.75rem;
  cursor: pointer;
  user-select: none;
  padding: 2px 6px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  transition: background-color 0.2s;
}

.timestamp-toggle:hover {
  background: rgba(255, 255, 255, 0.22);
}

.timestamp-toggle input {
  margin: 0;
  width: 14px;
  height: 14px;
  accent-color: #ffc800;
  cursor: pointer;
}

.timestamp-toggle-label {
  font-weight: bold;
  letter-spacing: 0.5px;
}

/* Token counter pill, matches the visual language of the other header chips */
.token-display {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: white;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  user-select: none;
  white-space: nowrap;
}

.token-icon {
  font-size: 0.85rem;
}

.token-text {
  font-variant-numeric: tabular-nums;
  font-weight: bold;
  letter-spacing: 0.3px;
}

.msg-actions {
  font-size: 0.8rem;
  margin-top: 5px;
  text-align: right;
}

/* Neues Textarea-Styling */
.input-area textarea {
  flex: 1;
  padding: 10px 15px;
  border-radius: 20px;
  border: 1px solid #ccc;
  font-size: 1rem;
  outline: none;
  resize: none;
  font-family: inherit;
  line-height: 1.4;
  overflow-y: auto;
  box-sizing: border-box;
  scrollbar-width: thin;
}

/* Dezentere Farben für die Uhrzeit je nach Blase */
.user {
  color: #5b8c5a;
}

.assistant {
  color: #999;
}

/* Back arrow rendered as a chunky chevron, matching the form view's header-back styling */
.header-back {
  color: white;
  font-size: 1.6rem;
  line-height: 1;
  padding: 0 6px 0 0;
  opacity: 1;
}

.header-back:hover {
  opacity: 0.75;
}

/* Header layout: title block grows so the clock can sit next to the name and wraps below on narrow viewports */
.header-title {
  flex: 1;
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 10px;
  min-width: 0;
  margin-left: 4px;
}

.header-name {
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* Clock pill displayed beneath the character name */
.clock-display {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-family: inherit;
  cursor: pointer;
  transition: background-color 0.2s;
  max-width: 100%;
}

.clock-display:hover {
  background: rgba(255, 255, 255, 0.22);
}

.clock-display.is-virtual {
  background: rgba(255, 200, 0, 0.25);
}

.clock-icon {
  font-size: 0.85rem;
}

.clock-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Popover below the header that hosts the datetime input */
.time-picker-popover {
  background: #fff;
  border-bottom: 1px solid #ddd;
  padding: 12px 15px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.time-picker-label {
  font-size: 0.85rem;
  color: #555;
  font-weight: bold;
}

.time-picker-input {
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 1rem;
  font-family: inherit;
}

.time-picker-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tp-btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  font-family: inherit;
}

.tp-btn-primary {
  background-color: #075e54;
  color: white;
}

.tp-btn-primary:hover:not(:disabled) {
  background-color: #128c7e;
}

.tp-btn-primary:disabled {
  background-color: #a0a0a0;
  cursor: default;
}

.tp-btn-secondary {
  background-color: #e0e0e0;
  color: #333;
}

.tp-btn-secondary:hover {
  background-color: #cccccc;
}

.tp-btn-danger {
  background-color: #f3dada;
  color: #8a2a2a;
}

.tp-btn-danger:hover {
  background-color: #ecc8c8;
}

/* Der Container zentriert die Pille */
.date-separator {
  display: flex;
  justify-content: center;
  margin: 15px 0 10px 0;
  width: 100%;
}

/* Die WhatsApp-typische Datums-Pille */
.date-separator span {
  background-color: #e1f3fb;
  color: #555;
  font-size: 0.8rem;
  font-weight: bold;
  padding: 6px 14px;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>