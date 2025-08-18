<script setup>
defineProps({
  departments: Array,
  selectedDepartment: [Number, String],
  startDate: String,
  endDate: String,
  isLoading: Boolean,
})

const emit = defineEmits([
  'update:selectedDepartment',
  'update:startDate',
  'update:endDate',
  'generate-shifts',
  'confirm-selected-shifts',
])

const handleDepartmentChange = (event) => {
  emit('update:selectedDepartment', Number(event.target.value))
}

const handleStartDateChange = (event) => {
  emit('update:startDate', event.target.value)
}

const handleEndDateChange = (event) => {
  emit('update:endDate', event.target.value)
}

const onGenerateShifts = () => {
  emit('generate-shifts')
}

const onConfirmSelectedShifts = () => {
  emit('confirm-selected-shifts')
}
</script>

<template>
  <div>
    <label for="department">部署:</label>
    <select id="department" :value="selectedDepartment" @change="handleDepartmentChange">
      <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
    </select>
    <label for="start">開始日:</label>
    <input type="date" id="start" :value="startDate" @change="handleStartDateChange" />
    <label for="end">終了日:</label>
    <input type="date" id="end" :value="endDate" @change="handleEndDateChange" />
    <button @click="onGenerateShifts" :disabled="isLoading">
      {{ isLoading ? '処理中...' : 'シフトを生成' }}
    </button>
    <button @click="onConfirmSelectedShifts" :disabled="isLoading" style="margin-left: 10px;">
      選択したシフトを確定
    </button>
  </div>
</template>

<style scoped>
div {
  margin-bottom: 1rem;
}
label {
  margin-left: 10px;
  margin-right: 5px;
}
button {
  margin-left: 10px;
}
</style>
