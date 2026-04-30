import { api } from '../api';

/**
 * Defines the structure for a generated chat history summary.
 */
export interface SummaryEntry {
    text: string;
    timestamp: number;
}

/**
 * Persisted anchor pair for a character's virtual clock. ``baseTimestamp`` is
 * the in-world anchor in milliseconds and ``anchorTimestamp`` the wall-clock
 * moment that anchor was applied.
 */
export interface VirtualClockEntry {
    baseTimestamp: number;
    anchorTimestamp: number;
}

/**
 * Represents a character configuration for the application.
 */
export interface Character {
    name: string;
    character_name?: string;
    user_name?: string;
    system_prompt: string;
    intro?: string;
    plot_generation_prompt?: string;
    sticky_note?: string;
    sticky_note_pos?: number | null;
    append_timestamp: boolean;
    enable_thinking?: boolean;
    full_history_for_last_n?: number | null;
    full_history_for_last_n_plot_generation?: number | null;
    idle_threshold_ms: number;
    time_scale?: number | null;
    temperature?: number | null;
    min_p?: number | null;
    top_p?: number | null;
    repeat_penalty?: number | null;
    frequency_penalty?: number | null;
    presence_penalty?: number | null;
    max_tokens?: number | null;
    summary?: SummaryEntry;
    virtual_clock?: VirtualClockEntry;
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