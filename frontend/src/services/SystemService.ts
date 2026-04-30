import { api } from '../api';

/**
 * Wraps the server-wide ``/system`` endpoints that are not bound to a specific
 * character, such as runtime maintenance actions on the shared LLM instance.
 */
export class SystemService {
    /**
     * Clears the model's KV cache and resets its internal state on the server.
     * The backend serializes this with ongoing inference, so the call may block
     * briefly until the current turn finishes.
     */
    async resetKvCache(): Promise<void> {
        await api.post('/system/reset-cache');
    }
}
