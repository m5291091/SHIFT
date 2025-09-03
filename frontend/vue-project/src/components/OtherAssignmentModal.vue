<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  member: Object,
  date: String,
})

const emit = defineEmits(['close', 'save'])

const activityName = ref('')

// モーダルが表示されたときにテキストエリアをリセット
watch(() => props.show, (newVal) => {
  if (newVal) {
    activityName.value = ''
  }
})

const save = () => {
  if (activityName.value.trim()) {
    emit('save', activityName.value)
  }
}

const close = () => {
  emit('close')
}
</script>

<template>
  <div v-if="show" class="modal-overlay" @click.self="close">
    <div class="modal-content">
      <h3>その他の割り当て</h3>
      <p v-if="member && date">
        <strong>従業員:</strong> {{ member.name }}<br>
        <strong>日付:</strong> {{ date }}
      </p>
      <textarea
        v-model="activityName"
        placeholder="業務内容を入力してください（例：研修）"
        rows="4"
      ></textarea>
      <div class="modal-actions">
        <button @click="close">キャンセル</button>
        <button @click="save" :disabled="!activityName.trim()">保存</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

h3 {
  margin-top: 0;
}

textarea {
  width: 100%;
  padding: 10px;
  margin-top: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}

.modal-actions {
  margin-top: 20px;
  text-align: right;
}

.modal-actions button {
  margin-left: 10px;
  padding: 8px 16px;
  border-radius: 4px;
  border: 1px solid #ccc;
  cursor: pointer;
}

.modal-actions button:last-child {
  background-color: #007bff;
  color: white;
  border-color: #007bff;
}

.modal-actions button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
</style>
