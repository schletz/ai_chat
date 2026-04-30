import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { viteSingleFile } from 'vite-plugin-singlefile';

export default defineConfig({
    plugins: [vue(), viteSingleFile()],
    build: {
        target: 'esnext',
        outDir: '../docs', // Gibt das übergeordnete Verzeichnis als Ziel an
        emptyOutDir: true  // Wichtig: Erlaubt Vite, den Ordner vor dem Build zu leeren
    },
});