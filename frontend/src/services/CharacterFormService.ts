import { api } from '../api';
import { Character } from './CharacterListService';

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
}