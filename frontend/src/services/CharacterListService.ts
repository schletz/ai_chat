import { api } from '../api';

/**
 * Defines the structure for a generated chat history summary.
 */
export interface SummaryEntry {
    text: string;
    timestamp: number;
}

/**
 * Represents a character configuration for the application.
 */
export interface Character {
    name: string;
    system_prompt: string;
    intro?: string;
    plot?: string;
    send_with_timestamp: boolean;
    idle_threshold_ms: number;
    temperature?: number | null;
    min_p?: number | null;
    top_p?: number | null;
    repeat_penalty?: number | null;
    max_tokens?: number | null;
    auto_summarize_tokens?: number | null;
    summary?: SummaryEntry;
}

/**
 * Service responsible for managing and retrieving character data.
 */
export class CharacterListService {
    /**
     * Fetches the complete list of characters from the backend API.
     * @returns A promise resolving to an array of Character objects.
     */
    async getCharacters(): Promise<Character[]> {
        const response = await api.get('/characters');
        return response.data.characters;
    }
}