import { api } from '../api';
import { Character } from './CharacterListService';

export class CharacterFormService {
    async getCharacter(name: string): Promise<Character | undefined> {
        const response = await api.get('/characters');
        const characters: Character[] = response.data.characters;
        return characters.find(c => c.name === name);
    }

    async createCharacter(data: Character): Promise<void> {
        await api.post('/characters', data);
    }

    async updateCharacter(name: string, data: Partial<Character>): Promise<void> {
        await api.put(`/characters/${name}`, data);
    }

    async deleteCharacter(name: string): Promise<void> {
        await api.delete(`/characters/${name}`);
    }
}