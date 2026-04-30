import { api } from '../api';

export interface ChatMessage {
    timestamp: number;
    role: 'user' | 'assistant';
    content: string;
}

/**
 * Service for managing chat interactions with a specific character.
 */
export class ChatService {
    private characterName: string;

    /**
     * Initializes the service with the target character's name.
     * @param characterName - The identifier or display name of the character.
     */
    constructor(characterName: string) {
        this.characterName = characterName;
    }

    /**
     * Retrieves chat history starting from a given timestamp.
     * @param fromTimestamp - The Unix timestamp to fetch messages after (defaults to 0).
     * @returns A promise resolving to an array of chat messages.
     */
    async getHistory(fromTimestamp: number = 0): Promise<ChatMessage[]> {
        try {
            const response = await api.get(`/characters/${this.characterName}/chat`, {
                params: { fromTimestamp }
            });

            // Validate response structure to ensure an array is returned.
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
     */
    async sendMessage(message: string): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat`, { message });
    }

    /**
     * Deletes a specific chat message by its timestamp.
     * @param timestamp - The unique identifier/timestamp of the target message.
     */
    async deleteMessage(timestamp: number): Promise<void> {
        await api.delete(`/characters/${this.characterName}/chat/${timestamp}`);
    }

    /**
     * Requests regeneration of the last assistant response.
     */
    async recreateAnswer(): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/recreate`);
    }
}