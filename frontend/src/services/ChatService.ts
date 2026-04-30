import { api } from '../api';

export interface ChatMessage {
    timestamp: number;
    role: 'user' | 'assistant';
    content: string;
}

export class ChatService {
    private characterName: string;

    constructor(characterName: string) {
        this.characterName = characterName;
    }

    async getHistory(fromTimestamp: number = 0): Promise<ChatMessage[]> {
        try {
            const response = await api.get(`/characters/${this.characterName}/chat`, {
                params: { fromTimestamp }
            });
            const chatArray = response.data;
            return Array.isArray(chatArray) ? chatArray : [];
        } catch (error) {
            console.error("Fehler beim Laden des Chatverlaufs:", error);
            return [];
        }
    }

    async sendMessage(message: string): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat`, { message });
    }

    async deleteMessage(timestamp: number): Promise<void> {
        await api.delete(`/characters/${this.characterName}/chat/${timestamp}`);
    }

    async recreateAnswer(): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/recreate`);
    }
}