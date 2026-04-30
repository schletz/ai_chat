import { api } from '../api';
import { Character } from './CharacterListService';

/**
 * Payload returned by the POST /chat/summarize endpoint. ``total_tokens``
 * is the token count of the summarization inference call, or ``null`` when
 * the call was skipped because the history was still short enough.
 */
export interface SummarizeResponse {
    message: string;
    total_tokens: number | null;
}

/**
 * Service for managing character form operations including retrieval and persistence.
 */
export class CharacterFormService {
    /**
     * Retrieves a specific character by name from the API.
     * @param name - The name of the character to find.
     * @returns The matching character object, or undefined if not found.
     */
    async getCharacter(name: string): Promise<Character | undefined> {
        const response = await api.get('/characters');
        const characters: Character[] = response.data.characters;
        return characters.find(c => c.name === name);
    }

    /**
     * Creates a new character via the API.
     * @param data - The character data to create.
     */
    async createCharacter(data: Character): Promise<void> {
        await api.post('/characters', data);
    }

    /**
     * Updates an existing character by name via the API.
     * @param name - The name of the character to update.
     * @param data - Partial character data containing updates.
     */
    async updateCharacter(name: string, data: Partial<Character>): Promise<void> {
        await api.put(`/characters/${name}`, data);
    }

    /**
     * Deletes a character by name via the API.
     * @param name - The name of the character to delete.
     */
    async deleteCharacter(name: string): Promise<void> {
        await api.delete(`/characters/${name}`);
    }

    /**
     * Updates only the append_timestamp flag for a character via the API.
     * @param name - The name of the character to update.
     * @param appendTimestamp - The new value for the append_timestamp flag.
     */
    async updateAppendTimestamp(name: string, appendTimestamp: boolean): Promise<void> {
        await api.patch(`/characters/${name}/append-timestamp`, {
            append_timestamp: appendTimestamp,
        });
    }

    /**
     * Updates only the per-character reasoning (thinking) flag via the API.
     * @param name - The name of the character to update.
     * @param enableThinking - The new value for the enable_thinking flag.
     */
    async updateEnableThinking(name: string, enableThinking: boolean): Promise<void> {
        await api.patch(`/characters/${name}/thinking`, {
            enable_thinking: enableThinking,
        });
    }

    /**
     * Persists the virtual clock anchor pair for a character via the API.
     * @param name - The name of the character whose clock should be stored.
     * @param baseTimestamp - The in-world anchor in milliseconds.
     * @param anchorTimestamp - The wall-clock moment the anchor was applied.
     */
    async updateVirtualClock(name: string, baseTimestamp: number, anchorTimestamp: number): Promise<void> {
        await api.patch(`/characters/${name}/virtual-clock`, {
            baseTimestamp,
            anchorTimestamp,
        });
    }

    /**
     * Clears the stored virtual clock anchor for a character so the chat view
     * falls back to the system clock.
     * @param name - The name of the character whose clock should be cleared.
     */
    async clearVirtualClock(name: string): Promise<void> {
        await api.patch(`/characters/${name}/virtual-clock`, {
            baseTimestamp: null,
            anchorTimestamp: null,
        });
    }

    /**
     * Triggers the generation of a context window summary for the character.
     * @param name - The name of the character to summarize.
     * @returns The server payload, including the token count of the
     *     summarization call (or ``null`` when no summary was produced).
     */
    async createSummary(name: string): Promise<SummarizeResponse> {
        const response = await api.post<SummarizeResponse>(`/characters/${name}/chat/summarize`);
        return response.data;
    }

    /**
     * Updates the rolling chat summary for a character. Passing an empty string
     * removes the stored summary entirely.
     * @param name - The name of the character whose summary should change.
     * @param text - The new summary text, or an empty string to clear it.
     */
    async updateSummary(name: string, text: string): Promise<void> {
        await api.patch(`/characters/${name}/summary`, { text });
    }
}