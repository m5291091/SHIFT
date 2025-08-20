<script setup>
import { ref, onMounted, inject } from 'vue'

const axios = inject('axios'); // Inject the provided axios instance

const members = ref([]) // 従業員リストを保存する場所

// 画面が表示された時に実行する処理
onMounted(async () => {
  try {
    // DjangoのAPIにアクセスしてデータを取得
    const response = await axios.get('/members/')
    members.value = response.data // 取得したデータを保存
  } catch (error) {
    console.error('データの取得に失敗しました:', error)
  }
})
</script>

<template>
  <div class="about">
    <h1>従業員リスト</h1>
    <ul>
      <li v-for="member in members" :key="member.id">
        {{ member.name }} (時給: {{ member.hourly_wage }}円)
      </li>
    </ul>
  </div>
</template>

<style>
@media (min-width: 1024px) {
  .about {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    padding-top: 2rem;
  }
}
</style>