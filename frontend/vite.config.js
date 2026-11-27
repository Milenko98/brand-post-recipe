import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
    plugins: [vue(), tailwindcss()],
    server: {
        host: '0.0.0.0',
        port: 5175,
        // The FastAPI backend; inside docker compose it is reachable as http://api:8000
        proxy: { '/api': process.env.API_URL || 'http://localhost:8001' },
    },
    test: {
        environment: 'jsdom',
        include: ['src/**/*.test.js'],
        restoreMocks: true,
    },
});
