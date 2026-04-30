import { api } from '../api';

export interface ChatMessage {
    /** Real wall-clock timestamp assigned by the server. Used for storage operations (e.g. delete). */
    timestamp: number;
    /** Optional virtual timestamp (in-world clock) supplied by the client when sending. Display only. */
    virtual_ts?: number;
    role: 'user' | 'assistant';
    content: string;
    /** True for agent-initiated steering messages (director/plot/agent). Rendered collapsed behind an icon. */
    is_agent?: boolean;
    /** Marks the start of the current scene; history may be read only from here onwards (excluding this message). */
    last_scene_message?: boolean;
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
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) used for the injected
     *   timestamp metadata so the rendered history matches what the model sees.
     * @param fromTimestamp - The Unix timestamp to fetch messages after (defaults to 0).
     * @param debug - If true, fetches unfiltered internal system/agent messages.
     */
    async getHistory(baseTimestamp: number, fromTimestamp: number = 0, debug: boolean = false): Promise<ChatMessage[]> {
        try {
            const response = await api.get(`/characters/${this.characterName}/chat`, {
                params: { fromTimestamp, debug, base_timestamp: baseTimestamp }
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
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) representing the
     *     current in-world clock; always sent so the server never guesses a clock.
     * @returns The assistant's reply along with the total token count of the
     *     latest inference call.
     */
    async sendMessage(message: string, baseTimestamp: number): Promise<ChatSendResponse> {
        const payload = { message, base_timestamp: baseTimestamp };
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
     * Sets or clears the ``last_scene_message`` flag of a chat message. The flag
     * marks the boundary from which the current scene's history is read.
     * @param timestamp - The unique identifier/timestamp of the target message.
     * @param lastSceneMessage - True to mark the message as the scene boundary,
     *     false to clear the flag.
     */
    async setLastSceneMessage(timestamp: number, lastSceneMessage: boolean): Promise<void> {
        await api.patch(`/characters/${this.characterName}/chat/${timestamp}/scene`, {
            last_scene_message: lastSceneMessage,
        });
    }

    /**
     * Deletes the entire chat history for the character in a single request.
     * Leaves an empty history; no reply is produced.
     */
    async deleteAllMessages(): Promise<void> {
        await api.delete(`/characters/${this.characterName}/chat/messages`);
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
     * Sends a director instruction that steers the roleplay like a stage direction.
     * The backend stores it as an agent message and uses it to shape the next
     * generated assistant response; it does not produce an immediate reply.
     * @param message - The director instruction text.
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) recorded as
     *     the message's virtual timestamp and appended as timestamp metadata.
     */
    async sendDirectorMessage(message: string, baseTimestamp: number): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/director`, { message, base_timestamp: baseTimestamp });
    }

    /**
     * Clears the character's current plot so nothing is injected into the
     * context anymore. Routes through the plot-insert endpoint with an empty
     * message, which the backend interprets as a clear.
     */
    async clearPlot(): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/plot/insert`, { message: "" });
    }

    /**
     * Asks the backend to generate a director plot and store it as the
     * character's current plot. The plot is derived from the current session
     * context; it does not produce an immediate assistant reply and only shapes
     * the next generated response.
     */
    async generateDirectorPlot(): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/plot/generate`);
    }

    /**
     * Asks the backend to summarize the current session. The summary is appended
     * to the history as an agent message and the entry before it becomes the
     * scene boundary, so the following turns are inferred from the summary
     * onwards instead of the full history. Nothing is deleted and no assistant
     * reply is produced.
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) representing the
     *     current in-world clock; always sent so the server never guesses a clock.
     * @returns The generated summary text.
     */
    async generateSummary(baseTimestamp: number): Promise<string> {
        const response = await api.post<{ message: string; summary: string }>(
            `/characters/${this.characterName}/chat/summary/generate`,
            { base_timestamp: baseTimestamp }
        );
        return response.data.summary;
    }

    /**
     * Requests an assistant turn from the backend, reusing the exact existing
     * chat history.
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) representing
     *     the current in-world clock; always sent so the server never guesses a
     *     clock.
     * @returns The assistant reply along with the total token count of the
     *     inference call.
     */
    async requestAssistantMessage(baseTimestamp: number): Promise<ChatSendResponse> {
        const response = await api.post<ChatSendResponse>(
            `/characters/${this.characterName}/chat/assistant`,
            { base_timestamp: baseTimestamp }
        );
        return response.data;
    }

    /**
     * Asks the backend to turn a user idea into a plot instruction. Only the
     * character intro is sent to the model as context, not the chat history; it is
     * inserted as a director message without triggering an assistant turn.
     * @param idea - The user's idea the instruction should implement.
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) recorded as
     *     the director message's virtual timestamp.
     * @returns The generated instruction.
     */
    async generateIdea(idea: string, baseTimestamp: number): Promise<string> {
        const response = await api.post<{ message: string; idea: string }>(
            `/characters/${this.characterName}/chat/idea/generate`,
            { idea, base_timestamp: baseTimestamp }
        );
        return response.data.idea;
    }

    /**
     * Inserts a manually authored assistant message into the chat history. Lets
     * the user steer the roleplay by providing an assistant turn directly. The
     * backend appends it as a regular assistant message without triggering
     * inference, so no reply is produced.
     * @param message - The assistant message text to append.
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) recorded as
     *     the message's virtual timestamp.
     */
    async addAssistantMessage(message: string, baseTimestamp: number): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/assistant/insert`, { message, base_timestamp: baseTimestamp });
    }

    /**
     * Inserts a user message into the chat history without triggering inference.
     * Lets the user pre-seed the conversation to steer the next generated
     * response; no reply is produced.
     * @param message - The user message text to append.
     * @param baseTimestamp - Mandatory virtual time (ms since epoch) recorded as
     *     the message's virtual timestamp.
     */
    async addUserMessage(message: string, baseTimestamp: number): Promise<void> {
        await api.post(`/characters/${this.characterName}/chat/user/insert`, { message, base_timestamp: baseTimestamp });
    }

    /**
     * Fetches the assembled context of the current chat session (optional intro
     * and the rolling-summary chat history) as a single string. Intended for
     * debugging and analysis in the UI; the backend triggers no inference.
     * Errors are propagated so the caller can surface them.
     * @param baseTimestamp - Optional virtual time (ms since epoch) representing
     *     the user-set "in-world" clock. When provided the corresponding in-world
     *     time is prepended to the context, mirroring what plot generation sees.
     *     When omitted no timestamp is added.
     * @returns The context string mirroring what the model effectively sees.
     */
    async getContext(baseTimestamp: number | null = null): Promise<string> {
        const params: { base_timestamp?: number } = {};
        if (baseTimestamp !== null) {
            params.base_timestamp = baseTimestamp;
        }
        const response = await api.get<{ context: string }>(
            `/characters/${this.characterName}/chat/context`,
            { params }
        );
        return response.data.context;
    }
}