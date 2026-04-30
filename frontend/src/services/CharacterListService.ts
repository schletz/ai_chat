import { api } from '../api';

export interface Character {
    name: string;
    system_prompt: string;
    send_with_timestamp: boolean;
}

export class CharacterListService {
    async getCharacters(): Promise<Character[]> {
        const response = await api.get('/characters');
        return response.data.characters;
    }
}