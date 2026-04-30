<template>
  <button
    :type="type || 'button'"
    :class="['cancellable-btn', customClass, { 'is-running': isInternalLoading }]"
    :disabled="isCancelling || (disabled && !isInternalLoading)"
    :title="isInternalLoading ? cancelTitle : title"
    @click="handleClick"
  >
    <!-- While cancelling the abort request itself is in flight: show a neutral spinner. -->
    <span v-if="isCancelling" class="spinner"></span>
    <!-- While the action runs the button doubles as a cancel control: the spinner
         signals progress and the stop glyph is revealed on hover/focus. -->
    <span v-else-if="isInternalLoading" class="running">
      <span class="spinner"></span>
      <span class="cancel-icon" aria-hidden="true">✕</span>
    </span>
    <span v-else class="content"><slot></slot></span>
  </button>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { SystemService } from "../services/SystemService";

/**
 * Button that runs an async action and, while it is in flight, turns into a
 * cancel control. A second click aborts the running inference by resetting the
 * server-side KV cache, which the backend handles by stopping the current turn
 * immediately. Mirrors {@link AsyncButton} but adds the cancel affordance.
 */
const props = defineProps<{
  /** Action to execute on the first click. Must return a Promise. */
  action: () => Promise<void>;
  /** Disables the button when true. Ignored while the action runs so it stays cancellable. */
  disabled?: boolean;
  /** Title attribute shown while the button is idle. */
  title?: string;
  /** Title attribute shown while the action runs, hinting at the cancel action. */
  cancelTitle?: string;
  /** Additional CSS classes applied to the button element. */
  customClass?: string;
  /** HTML button type (button, submit, reset). Defaults to 'button'. */
  type?: "button" | "submit" | "reset";
}>();

const systemService = new SystemService();

const isInternalLoading = ref(false);
const isCancelling = ref(false);

/** Title shown while running; falls back to a German default. */
const cancelTitle = props.cancelTitle ?? "Abbrechen";

/**
 * Routes clicks depending on the current state: starts the action when idle,
 * or requests a cancel when the action is already running.
 */
const handleClick = async () => {
  if (isInternalLoading.value) {
    await cancel();
    return;
  }
  if (props.disabled) return;

  isInternalLoading.value = true;
  try {
    await props.action();
  } catch (error) {
    // A user-initiated cancel aborts the in-flight request, which surfaces here
    // as an error; suppress the alert in that case since the abort was intended.
    if (!isCancelling.value) {
      console.error("Error during action execution:", error);
      alert("Action failed. Please check your connection.");
    }
  } finally {
    isInternalLoading.value = false;
    isCancelling.value = false;
  }
};

/**
 * Aborts the running action by resetting the server-side KV cache. The aborted
 * action promise then settles, which clears the loading state in handleClick's
 * finally block. Errors are logged without disrupting the UI.
 */
const cancel = async () => {
  if (isCancelling.value) return;
  isCancelling.value = true;
  try {
    await systemService.resetKvCache();
  } catch (error) {
    console.error("Failed to cancel the running action:", error);
    // The abort request failed, so the action keeps running: leave the cancel
    // state so the user can try again instead of locking the button.
    isCancelling.value = false;
  }
};
</script>

<style scoped>
.cancellable-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  line-height: 1;
  padding: 0;
  appearance: none;
  -webkit-appearance: none;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: inherit;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  line-height: 1;
}

/* Wrapper stacking the progress spinner and the hover-revealed stop glyph. */
.running {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* The stop glyph overlays the spinner and only appears on hover/focus so the
   running state stays calm until the user intends to cancel. */
.cancel-icon {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95em;
  opacity: 0;
  transition: opacity 0.15s;
}

.is-running:hover .cancel-icon,
.is-running:focus-visible .cancel-icon {
  opacity: 1;
}

/* Fade the spinner out on hover so the stop glyph reads clearly. */
.is-running:hover .running .spinner,
.is-running:focus-visible .running .spinner {
  opacity: 0.25;
}
</style>
