import { api } from '../api';

/**
 * Represents a character configuration for the application.
 */
export interface Character {
    name: string;
    system_prompt: string;
    send_with_timestamp: boolean;
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