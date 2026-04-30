import { api } from '../api';

export interface ChatMessage {
    /** Real wall-clock timestamp assigned by the server. Used for storage operations (e.g. delete). */
    timestamp: number;
    /** Optional virtual timestamp (in-world clock) supplied by the client when sending. Display only. */
    virtual_ts?: number;
    role: 'user' | 'assistant' | 'summary';
    content: string;
}

/**
 * Payload returned by the POST /chat endpoint after the assistant has produced
 * a reply. ``total_tokens`` reports the combined prompt + completion token
 * count of the last inference call and approximates how full the model
 * context window currently is.
 */
export interface ChatSendResponse {
    role: 'assistant';
    content: string;
    total_tokens: number;
}

export class ChatService {
    private characterName: string;

    constructor(characterName: string) {
        this.characterName = characterName;
    }

    /**
     * Retrieves chat history starting from a given timestamp, optionally including raw debug messages.
     * @param fromTimestamp - The Unix timestamp to fetch messages after (defaults to 0).
     * @param debug - If true, fetches unfiltered internal system/agent messages.
     */
    async getHistory(fromTimestamp: number = 0, debug: boolean = false): Promise<ChatMessage[]> {
        try {
            const response = await api.get(`/characters/${this.characterName}/chat`, {
                params: { fromTimestamp, debug }
            });

            const chatArray = response.data;
            return Array.isArray(chatArray) ? chatArray : [];
        } catch (error) {
            console.error("Error loading chat history:", error);
            return [];
        }
    }

    /**
     * Sends a user message to the character.
     * @param message - The text content of the message.
     * @param baseTimestamp - Optional virtual time (ms since epoch) representing the
     *     user-set "in-world" clock. When omitted the server uses the system clock.
     * @returns The assistant's reply along with the total token count of the
     *     latest inference call.
     */
    async sendMessage(message: string, baseTimestamp: number | null = null): Promise<ChatSendResponse> {
        const payload: { message: string; base_timestamp?: number } = { message };
        if (baseTimestamp !== null) {
            payload.base_timestamp = baseTimestamp;
        }
        const response = await api.post<ChatSendResponse>(`/characters/${this.characterName}/chat`, payload);
        return response.data;
    }

    /**
     * Deletes a specific chat message by its timestamp.
     * @param timestamp - The unique identifier/timestamp of the target message.
     */
    async deleteMessage(timestamp: number): Promise<void> {
        await api.delete(`/characters/${this.characterName}/chat/${timestamp}`);
    }

    /**
     * Updates the textual content of an existing chat message.
     * @param timestamp - The unique identifier/timestamp of the target message.
     * @param content - The new content to persist for the message.
     */
    async updateMessage(timestamp: number, content: string): Promise<void> {
        await api.patch(`/characters/${this.characterName}/chat/${timestamp}`, { content });
    }

    /**
     * Requests regeneration of the last assistant response. The backend reuses the
     * exact existing chat history, so no virtual timestamp is sent.
     * @returns The regenerated reply along with the total token count of the
     *     inference call.
     */
    async recreateAnswer(): Promise<ChatSendResponse> {
        const response = await api.post<ChatSendResponse>(`/characters/${this.characterName}/chat/recreate`);
        return response.data;
    }
}