<template>
  <div class="login-container">
    <div class="login-box">
      <h2>ログイン</h2>
      <form @submit.prevent="handleLogin">
        <div class="input-group">
          <label for="username">ユーザー名</label>
          <input type="text" id="username" v-model="username" required>
        </div>
        <div class="input-group">
          <label for="password">パスワード</label>
          <input type="password" id="password" v-model="password" required>
        </div>
        <button type="submit" :disabled="isLoading">{{ isLoading ? 'ログイン中...' : 'ログイン' }}</button>
        <p v-if="error" class="error-message">{{ error }}</p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, inject } from 'vue';
import { useRouter } from 'vue-router';

const username = ref('');
const password = ref('');
const error = ref('');
const isLoading = ref(false);

const axios = inject('axios');
const router = useRouter();

const handleLogin = async () => {
  isLoading.value = true;
  error.value = '';
  try {
    const response = await axios.post('/api/v1/token/', {
      username: username.value,
      password: password.value
    });
    
    // トークンをlocalStorageに保存
    localStorage.setItem('access_token', response.data.access);
    localStorage.setItem('refresh_token', response.data.refresh);

    // シフトページにリダイレクト
    router.push('/');

  } catch (err) {
    if (err.response && err.response.status === 401) {
      error.value = 'ユーザー名またはパスワードが正しくありません。';
    } else {
      error.value = 'ログイン中にエラーが発生しました。ネットワーク接続を確認してください。';
    }
    console.error('Login failed:', err);
  } finally {
    isLoading.value = false;
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f4f4f4;
}
.login-box {
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}
h2 {
  text-align: center;
  margin-bottom: 20px;
}
.input-group {
  margin-bottom: 15px;
}
.input-group label {
  display: block;
  margin-bottom: 5px;
}
.input-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}
button {
  width: 100%;
  padding: 10px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}
button:disabled {
  background-color: #ccc;
}
.error-message {
  color: red;
  text-align: center;
  margin-top: 15px;
}
</style>
