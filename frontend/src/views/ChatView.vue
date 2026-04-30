<template>
  <ChatHeader :name="name" :base-timestamp="baseTimestamp" :formatted-virtual-time="formattedVirtualTime"
    :context-tokens="contextTokens" :append-timestamp="appendTimestamp" :enable-thinking="enableThinking"
    :is-debug-mode="isDebugMode"
    @toggle-time-picker="toggleTimePicker" @toggle-timestamp="onAppendTimestampChange"
    @toggle-thinking="onEnableThinkingChange" @toggle-debug="toggleDebug"
    :is-generating-plot="isGeneratingPlot"
    @generate-director-plot="generateDirectorPlot" @cancel-director-plot="cancelDirectorPlot"
    @open-context="openContextPanel"
    @reset-kv-cache="resetKvCache" @clear-history="clearHistory" />

  <div v-if="showTimePicker" class="time-picker-popover">
    <label class="time-picker-label">Basiszeit setzen</label>
    <input type="datetime-local" v-model="timePickerInput" class="time-picker-input" @change="applyBaseTime" />
    <div class="time-picker-actions">
      <button v-if="baseTimestamp !== null" type="button" class="tp-btn tp-btn-danger" @click="clearBaseTime">
        Uhr deaktivieren
      </button>
      <button type="button" class="tp-btn tp-btn-secondary" @click="showTimePicker = false">
        Schließen
      </button>
    </div>
  </div>

  <ContextPanel v-if="showContextPanel" :name="name"
    :base-timestamp="baseTimestamp !== null ? currentVirtualTimestamp : null" @close="showContextPanel = false" />

  <div class="content chat-window" ref="chatContainer">
    <template v-for="(msg, index) in messages" :key="msg.timestamp">
      <div v-if="showDateSeparator(index)" class="date-separator">
        <span>{{ formatDateSeparator(displayTimestamp(msg)) }}</span>
      </div>

      <AgentMessageBubble v-if="msg.is_agent" :message="msg" :debug-mode="isDebugMode" @delete="deleteMsg" />
      <ChatMessageBubble v-else :message="msg" @delete="deleteMsg" @edit="editMsg" @set-time="setVirtualClockTo" @toggle-scene="toggleSceneMsg" />
    </template>
  </div>

  <div class="input-area">
    <div v-if="messages.length > 0" class="action-menu-wrapper">
      <button type="button" class="action-btn" :class="{ 'is-open': showActionsMenu }" @click="toggleActionsMenu"
        title="Antwort-Aktionen" aria-label="Antwort-Aktionen">
        ⋯
      </button>

      <template v-if="showActionsMenu">
        <div class="action-menu-backdrop" @click="showActionsMenu = false"></div>
        <div class="action-menu" role="menu">
          <CancellableButton :action="() => runActionAndClose(recreate)" customClass="action-menu-item">
            <span class="action-menu-icon">↩</span>
            <span>Antworten</span>
          </CancellableButton>
          <CancellableButton
            :action="() => runActionAndClose(requestAdditionalAnswer)" customClass="action-menu-item">
            <span class="action-menu-icon">➕</span>
            <span>Weitere Antwort</span>
          </CancellableButton>
          <AsyncButton :action="() => runActionAndClose(insertAssistantMessage)" :disabled="!newMessage.trim()"
            customClass="action-menu-item">
            <span class="action-menu-icon">🤖</span>
            <span>Als Assistant-Nachricht einfügen</span>
          </AsyncButton>
          <AsyncButton :action="() => runActionAndClose(insertUserMessage)" :disabled="!newMessage.trim()"
            customClass="action-menu-item">
            <span class="action-menu-icon">🙋</span>
            <span>Als User-Nachricht einfügen</span>
          </AsyncButton>
          <AsyncButton :action="() => runActionAndClose(insertDirectorMessage)" :disabled="!newMessage.trim()"
            customClass="action-menu-item">
            <span class="action-menu-icon">🎬</span>
            <span>Director Nachricht einfügen</span>
          </AsyncButton>
        </div>
      </template>
    </div>

    <textarea ref="messageInput" v-model="newMessage"
      @keydown="handleKeydown"
      placeholder="Nachricht..." rows="2"></textarea>

    <CancellableButton ref="sendButtonRef" :action="send" :disabled="!newMessage.trim()"
      customClass="action-btn send-btn" title="Senden">
      ➤
    </CancellableButton>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from "vue";
import { ChatService, ChatMessage } from "../services/ChatService";
import { CharacterFormService } from "../services/CharacterFormService";
import { SystemService } from "../services/SystemService";
import AsyncButton from "../components/AsyncButton.vue";
import CancellableButton from "../components/CancellableButton.vue";
import ChatMessageBubble from "../components/ChatMessageBubble.vue";
import AgentMessageBubble from "../components/AgentMessageBubble.vue";
import ChatHeader from "../components/ChatHeader.vue";
import ContextPanel from "../components/ContextPanel.vue";

const props = defineProps<{ name: string }>();
const chatService = new ChatService(props.name);
const formService = new CharacterFormService();
const systemService = new SystemService();

const messages = ref<ChatMessage[]>([]);
const newMessage = ref("");
const chatContainer = ref<HTMLElement | null>(null);
const messageInput = ref<HTMLTextAreaElement | null>(null);

const sendButtonRef = ref<InstanceType<typeof CancellableButton> | null>(null);

// Reactive state for the debug flag toggling raw history display.
const isDebugMode = ref(false);

// The current plot is a character property (not a stored history entry). The
// backend injects it as a collapsed agent bubble at its real position (before
// the last user entry) carrying this sentinel timestamp, which never collides
// with the positive wall-clock timestamps of real messages. The frontend uses
// it to route a delete of the plot bubble to clearing the plot.
const PLOT_SENTINEL_TS = -1;

// Latest total_tokens reported by the server after an assistant turn. Used to
// surface how full the model context currently is. Null until the first send.
const contextTokens = ref<number | null>(null);

// Mirrors the character's append_timestamp setting; toggling persists via the PATCH endpoint
const appendTimestamp = ref(true);

// Mirrors the character's reasoning setting. Toggling persists via the PATCH
// endpoint and is read at inference time for this character's turns.
const enableThinking = ref(true);

// True while a director plot is being generated, so the burger menu can show an inline spinner.
const isGeneratingPlot = ref(false);

// Controls visibility of the fullscreen context-inspection panel. Opened from the burger submenu.
const showContextPanel = ref(false);

// Controls visibility of the assistant-action popover next to the message input.
const showActionsMenu = ref(false);

// Virtual clock state. baseTimestamp holds the user-defined "in-world" anchor (ms);
// virtualClockRealAnchor is the wall-clock moment that anchor was applied. The displayed
// time advances from this anchor, scaled by timeScale (1 = real time, >1 faster, <1 slower).
const baseTimestamp = ref<number | null>(null);
const virtualClockRealAnchor = ref<number>(0);
const timeScale = ref<number>(1);
const nowTick = ref<number>(Date.now());
const showTimePicker = ref(false);
const timePickerInput = ref<string>("");
let clockInterval: ReturnType<typeof setInterval> | null = null;

/**
 * Persists the active anchor pair in the character settings so the virtual
 * clock survives a page reload and stays in sync across devices. A cleared
 * clock removes the stored anchor entirely. Errors are logged but never block
 * the chat UI.
 */
const persistVirtualClock = async () => {
  try {
    if (baseTimestamp.value === null) {
      await formService.clearVirtualClock(props.name);
      return;
    }
    await formService.updateVirtualClock(props.name, baseTimestamp.value, virtualClockRealAnchor.value);
  } catch (error) {
    console.warn("Failed to persist virtual clock state", error);
  }
};

/** Toggles the debug mode and reloads the chat to fetch unfiltered history. */
const toggleDebug = async () => {
  isDebugMode.value = !isDebugMode.value;
  await loadChat();
};

/** Reveals the fullscreen context-inspection panel. */
const openContextPanel = () => {
  showContextPanel.value = true;
};

/**
 * Clears the model's KV cache on the server. The reset only affects the shared
 * runtime state, so the visible chat history is left untouched. Errors are
 * surfaced to the console without disrupting the chat.
 */
const resetKvCache = async () => {
  try {
    await systemService.resetKvCache();
  } catch (error) {
    console.error("Failed to reset KV cache", error);
  }
};

/**
 * Deletes the character's entire chat history after an explicit confirmation.
 * The irreversible action is guarded by a native confirm dialog; on success the
 * now-empty history is reloaded. Errors are surfaced to the console without
 * disrupting the chat.
 */
const clearHistory = async () => {
  if (!window.confirm("Soll der gesamte Nachrichtenverlauf wirklich gelöscht werden? Diese Aktion kann nicht rückgängig gemacht werden.")) {
    return;
  }
  try {
    await chatService.deleteAllMessages();
  } catch (error) {
    console.error("Failed to clear chat history", error);
    return;
  }
  await loadChat();
};

/**
 * Initializes the chat by loading the character configuration (append-timestamp,
 * reasoning and virtual-clock settings) and then fetching the chat history.
 */
const initChat = async () => {
  try {
    const character = await formService.getCharacter(props.name);
    if (character) {
      appendTimestamp.value = character.append_timestamp;
      // A missing flag defaults to reasoning enabled.
      enableThinking.value = character.enable_thinking ?? true;
      // A missing or non-positive scale means the clock runs in real time.
      timeScale.value = character.time_scale && character.time_scale > 0 ? character.time_scale : 1;
    }
    // Restore the persisted virtual clock from the character settings so the
    // header reflects the saved in-world time across reloads and devices.
    if (character?.virtual_clock) {
      baseTimestamp.value = character.virtual_clock.baseTimestamp;
      virtualClockRealAnchor.value = character.virtual_clock.anchorTimestamp;
    }
  } catch (error) {
    console.error("Failed to fetch character configuration for initialization.", error);
  }
  await loadChat();
};

/**
 * Applies and persists the toggled append_timestamp flag for the character.
 * The new value is supplied by the header's toggle. Reverts the local state if
 * the API call fails so the UI never drifts from the backend.
 *
 * @param newValue The desired append-timestamp value selected by the user.
 */
const onAppendTimestampChange = async (newValue: boolean) => {
  appendTimestamp.value = newValue;
  try {
    await formService.updateAppendTimestamp(props.name, newValue);
  } catch (error) {
    console.error("Failed to update append_timestamp", error);
    appendTimestamp.value = !newValue;
  }
};

/**
 * Applies the toggled reasoning setting by persisting it in the character
 * settings. The flag is read at inference time for this character's turns.
 * Reverts the local state if the request fails so the UI stays in sync.
 *
 * @param newValue The desired reasoning state selected by the user.
 */
const onEnableThinkingChange = async (newValue: boolean) => {
  enableThinking.value = newValue;
  try {
    await formService.updateEnableThinking(props.name, newValue);
  } catch (error) {
    console.error("Failed to update enable_thinking", error);
    enableThinking.value = !newValue;
  }
};

/** Loads the full chat history; the plot bubble is already injected by the server. */
const loadChat = async () => {
  // Always forward the current in-world time so the server resolves the sticky
  // note's ${time} placeholder to the same value the model would see.
  const history = await chatService.getHistory(
    currentVirtualTimestamp.value, 0, isDebugMode.value
  );

  messages.value = history;

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
  // Agent steering messages carry the user role but are rendered as collapsed
  // system notes, so they must not anchor day boundaries.
  if (msg.role !== "user" || msg.is_agent) return false;

  // Locate the most recent prior user message to compare day boundaries against.
  let prevUserMsg: ChatMessage | null = null;
  for (let i = index - 1; i >= 0; i--) {
    if (messages.value[i].role === "user" && !messages.value[i].is_agent) {
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
  // Scale the elapsed real time so the in-world clock can run faster or slower.
  return baseTimestamp.value + (tick - virtualClockRealAnchor.value) * timeScale.value;
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
const applyBaseTime = async () => {
  if (!timePickerInput.value) return;
  const parsed = new Date(timePickerInput.value).getTime();
  if (Number.isNaN(parsed)) return;
  baseTimestamp.value = parsed;
  virtualClockRealAnchor.value = Date.now();
  nowTick.value = virtualClockRealAnchor.value;
  await persistVirtualClock();
};

/**
 * Anchors the virtual clock to a specific message's moment. Triggered by
 * clicking the timestamp in a message bubble so the in-world clock jumps to
 * when that message took place and resumes ticking forward from there.
 */
const setVirtualClockTo = async (timestamp: number) => {
  baseTimestamp.value = timestamp;
  virtualClockRealAnchor.value = Date.now();
  nowTick.value = virtualClockRealAnchor.value;
  await persistVirtualClock();
};

/**
 * Releases the virtual clock so the header reflects the actual system time and
 * outgoing messages no longer carry a base_timestamp.
 */
const clearBaseTime = async () => {
  baseTimestamp.value = null;
  virtualClockRealAnchor.value = 0;
  nowTick.value = Date.now();
  showTimePicker.value = false;
  await persistVirtualClock();
};

/** Handles sending a user message and refreshing the chat state. */
const send = async () => {
  const text = newMessage.value;
  newMessage.value = "";

  if (messageInput.value) messageInput.value.style.height = "auto";

  // Inference always carries the current in-world time.
  const outgoingTs = currentVirtualTimestamp.value;

  // Optimistically update UI before awaiting server response
  const optimisticMessage: ChatMessage = { timestamp: Date.now(), role: "user", content: text, virtual_ts: outgoingTs };
  messages.value.push(optimisticMessage);
  scrollToBottom();

  const result = await chatService.sendMessage(text, outgoingTs);
  contextTokens.value = result.total_tokens;
  await loadChat();
};

/**
 * Inserts the typed text as an assistant message instead of sending it as a user
 * message. No reply is generated; the history is simply extended so the user can
 * steer the conversation. Mirrors the optimistic-update flow of {@link send}.
 */
const insertAssistantMessage = async () => {
  const text = newMessage.value;
  if (!text.trim()) return;
  newMessage.value = "";

  if (messageInput.value) messageInput.value.style.height = "auto";

  const outgoingTs = currentVirtualTimestamp.value;

  // Optimistically render the assistant bubble before awaiting the server.
  const optimisticMessage: ChatMessage = { timestamp: Date.now(), role: "assistant", content: text, virtual_ts: outgoingTs };
  messages.value.push(optimisticMessage);
  scrollToBottom();

  await chatService.addAssistantMessage(text, outgoingTs);
  await loadChat();
};

/**
 * Inserts the typed text as a user message without triggering inference. Lets the
 * user pre-seed their own turn to steer the next generated response. Mirrors the
 * optimistic-update flow of {@link send} but never awaits a reply.
 */
const insertUserMessage = async () => {
  const text = newMessage.value;
  if (!text.trim()) return;
  newMessage.value = "";

  if (messageInput.value) messageInput.value.style.height = "auto";

  const outgoingTs = currentVirtualTimestamp.value;
  const optimisticMessage: ChatMessage = { timestamp: Date.now(), role: "user", content: text, virtual_ts: outgoingTs };
  messages.value.push(optimisticMessage);
  scrollToBottom();

  await chatService.addUserMessage(text, outgoingTs);
  await loadChat();
};

/**
 * Inserts the typed text as a director instruction that steers the roleplay
 * without producing a reply or appearing as a regular message. Mirrors the
 * draft-clearing flow of {@link insertUserMessage} but routes through the
 * director endpoint, so the new entry only surfaces in debug mode.
 */
const insertDirectorMessage = async () => {
  const text = newMessage.value.trim();
  if (!text) return;
  newMessage.value = "";

  if (messageInput.value) messageInput.value.style.height = "auto";

  await chatService.sendDirectorMessage(text, currentVirtualTimestamp.value);
  await loadChat();
};

/**
 * Removes a message by timestamp. The server-injected sticky note bubble is
 * cleared via the plot endpoint, while regular chat messages go through the
 * chat-history delete endpoint.
 */
const deleteMsg = async (timestamp: number) => {
  // The server-injected sticky note bubble is a character property, not a stored
  // message: clear the sticky_note instead of deleting a history entry. It is
  // recognized by its sentinel timestamp.
  if (timestamp === PLOT_SENTINEL_TS) {
    try {
      await chatService.clearPlot();
    } catch (error) {
      console.error("Failed to clear plot", error);
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

/**
 * Toggles the scene-boundary flag of a message via PATCH and refreshes the chat
 * list so the updated flag state is reflected in the bubble.
 */
const toggleSceneMsg = async (timestamp: number, lastSceneMessage: boolean) => {
  try {
    await chatService.setLastSceneMessage(timestamp, lastSceneMessage);
  } catch (error) {
    console.error("Failed to update scene boundary", error);
    return;
  }
  await loadChat();
};

/** Triggers regeneration of the most recent assistant message. */
const recreate = async () => {
  const result = await chatService.requestAssistantMessage(true, currentVirtualTimestamp.value);
  contextTokens.value = result.total_tokens;
  await loadChat();
};

/** Requests an additional assistant message without removing the existing one. */
const requestAdditionalAnswer = async () => {
  const result = await chatService.requestAssistantMessage(false, currentVirtualTimestamp.value);
  contextTokens.value = result.total_tokens;
  await loadChat();
};

/**
 * Triggers backend generation of a director plot. The agent creates the plot and
 * stores it as the character's sticky_note without producing a reply, so the
 * plot bubble and chat history are refreshed afterwards.
 */
const generateDirectorPlot = async () => {
  isGeneratingPlot.value = true;
  try {
    await chatService.generateDirectorPlot(currentVirtualTimestamp.value);
    await loadChat();
  } catch (error) {
    console.error("Failed to generate director plot", error);
  } finally {
    isGeneratingPlot.value = false;
  }
};

/**
 * Aborts an in-flight plot generation by resetting the server-side KV cache,
 * which makes the backend stop the current turn immediately. The pending
 * generateDirectorPlot call then settles and clears the generating state.
 */
const cancelDirectorPlot = async () => {
  try {
    await systemService.resetKvCache();
  } catch (error) {
    console.error("Failed to cancel director plot generation", error);
  }
};

/** Toggles the assistant-action popover anchored above the input area. */
const toggleActionsMenu = () => {
  showActionsMenu.value = !showActionsMenu.value;
};

/**
 * Runs a popover action and closes the menu once it resolves. The menu stays
 * open while the action runs so the triggering item keeps showing its spinner;
 * on failure it remains open so the user can see the error and retry.
 *
 * @param action - The async assistant-request handler to execute.
 */
const runActionAndClose = async (action: () => Promise<void>) => {
  await action();
  showActionsMenu.value = false;
};

// Start the initialization sequence on mount
onMounted(() => {
  // initChat restores the persisted virtual clock from the character settings.
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

/* Positioning context for the action popover that opens above the toggle. */
.action-menu-wrapper {
  position: relative;
  flex-shrink: 0;
}

.action-btn.is-open {
  background-color: #128c7e;
}

/* Transparent layer that closes the popover when the user taps outside of it. */
.action-menu-backdrop {
  position: fixed;
  inset: 0;
  background: transparent;
  z-index: 20;
}

/* Popover anchored above the toggle button, mirroring the header's burger menu. */
.action-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  min-width: 200px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  z-index: 30;
}

/* AsyncButton rendered as a full-width menu row. The compound selector keeps
   these rules ahead of AsyncButton's own .async-btn base styles. */
.action-menu .action-menu-item {
  display: flex;
  align-items: center;
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

.action-menu .action-menu-item:hover {
  background: #f0f0f0;
}

/* Align the slot content (icon + label) to the row start instead of centering. */
.action-menu .action-menu-item :deep(.content) {
  justify-content: flex-start;
  width: 100%;
  gap: 10px;
}

/* Keep the loading spinner tinted against the light popover background. */
.action-menu .action-menu-item :deep(.spinner) {
  border-color: rgba(7, 94, 84, 0.25);
  border-top-color: #075e54;
}

.action-menu-icon {
  font-size: 1.1rem;
  width: 1.4rem;
  text-align: center;
  flex-shrink: 0;
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