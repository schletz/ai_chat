import { api } from '../api';

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
    /** English translation of ``system_prompt``, maintained by the backend on save. */
    system_prompt_en?: string;
    /** English translation of ``intro``, maintained by the backend on save. */
    intro_en?: string;
    /** Uses the English translations of system prompt and intro for inference. */
    translate_to_english?: boolean;
    plot?: string;
    /** System prompt of the plot generation; empty falls back to the backend default. */
    plot_generation_system_prompt?: string;
    /** User content of the plot generation, sent after the context; empty falls back to the backend default. */
    plot_generation_content?: string;
    sticky_note?: string;
    sticky_note_pos?: number | null;
    /** Instruction triggering the summary; empty falls back to the backend default. */
    summarize_prompt?: string;
    /** System prompt turning a user idea into an instruction; empty falls back to the backend default. */
    idea_generation_system_prompt?: string;
    /** User content placed between the context and the user's idea; empty falls back to the backend default. */
    idea_generation_content?: string;
    append_timestamp: boolean;
    enable_thinking?: boolean;
    answer_count?: number | null;
    full_history_for_last_n?: number | null;
    cap_history?: number | null;
    idle_threshold_ms: number;
    time_scale?: number | null;
    temperature?: number | null;
    min_p?: number | null;
    top_p?: number | null;
    top_k?: number | null;
    repeat_penalty?: number | null;
    frequency_penalty?: number | null;
    presence_penalty?: number | null;
    max_tokens?: number | null;
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