import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import axiosInstance from './api/axios'; // Import the configured axios instance

const app = createApp(App)

app.use(router)
app.config.globalProperties.$axios = axiosInstance; // Make axios available globally via $axios
app.provide('axios', axiosInstance); // Provide it for Composition API injection

app.mount('#app')
