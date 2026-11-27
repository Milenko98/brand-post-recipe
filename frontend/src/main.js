import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import RunsView from './views/RunsView.vue';
import NewRunView from './views/NewRunView.vue';
import RunView from './views/RunView.vue';
import './style.css';

const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/', component: RunsView },
        { path: '/new', component: NewRunView },
        { path: '/runs/:id/:phase?', component: RunView, props: true },
    ],
});

createApp(App).use(router).mount('#app');
