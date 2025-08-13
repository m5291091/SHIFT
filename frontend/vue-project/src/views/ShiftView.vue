<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const startDate = ref('')
const endDate = ref('')
const isLoading = ref(false)
const message = ref('')

const members = ref([])
const assignments = ref([])
const leaveRequests = ref([])
const availabilities = ref([])
const shiftPatterns = ref([])
const infeasibleDays = ref([])

onMounted(async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/v1/shift-patterns/')
    shiftPatterns.value = response.data
  } catch (error) {
    console.error('シフトパターンの取得に失敗しました:', error)
  }
})

const formatDate = (dateObj) => {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, '0');
  const d = String(dateObj.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

const dateHeaders = computed(() => {
  if (!startDate.value || !endDate.value) return []
  
  const dates = []
  let currentDate = new Date(startDate.value + 'T00:00:00')
  const lastDate = new Date(endDate.value + 'T00:00:00')
  const weekdays = ['日', '月', '火', '水', '木', '金', '土']

  while (currentDate <= lastDate) {
    dates.push({
      date: formatDate(currentDate),
      weekday: weekdays[currentDate.getDay()],
    })
    currentDate.setDate(currentDate.getDate() + 1)
  }
  return dates
})

const memberStats = computed(() => {
  const stats = {}
  const totalDays = dateHeaders.value.length
  if (totalDays === 0) return stats;

  members.value.forEach(member => {
    const workDays = assignments.value.filter(a => a.member_id === member.id).length
    stats[member.id] = {
      holidays: totalDays - workDays,
    }
  })
  return stats
})

const scheduleGrid = computed(() => {
  const grid = {}
  members.value.forEach(member => {
    grid[member.id] = {}
    dateHeaders.value.forEach(header => {
      if (infeasibleDays.value.includes(header.date)) {
        grid[member.id][header.date] = { text: '人員不足', type: 'infeasible' }
      } else {
        grid[member.id][header.date] = { text: '/', type: 'empty' }
        const dayOfWeek = new Date(header.date + 'T00:00:00').getDay()
        const dayOfWeekForDjango = (dayOfWeek === 0) ? 6 : dayOfWeek - 1;
        const isAvailable = availabilities.value.some(avail => 
          avail.member === member.id && avail.day_of_week === dayOfWeekForDjango
        )
        if(isAvailable) {
          grid[member.id][header.date] = { text: '-', type: 'available' }
        }
      }
    })
  })
  leaveRequests.value.forEach(req => {
    if (grid[req.member_id]) {
      grid[req.member_id][req.leave_date] = { text: '✖︎', type: 'leave' }
    }
  })
  assignments.value.forEach(a => {
    if (grid[a.member_id]) {
      grid[a.member_id][a.shift_date] = { text: a.shift_pattern_name, type: 'assigned' }
    }
  })
  return grid
})

const generateShifts = async () => {
  if (!startDate.value || !endDate.value) {
    message.value = '開始日と終了日を選択してください。'
    return
  }
  isLoading.value = true
  message.value = 'シフトを生成中です...'
  infeasibleDays.value = []
  
  try {
    const response = await axios.post('http://127.0.0.1:8000/api/v1/generate-shifts/', {
      start_date: startDate.value,
      end_date: endDate.value,
    })
    
    infeasibleDays.value = response.data.infeasible_days || []
    if (infeasibleDays.value.length > 0) {
      message.value = '人員不足のため一部の日付が生成できませんでした。'
    } else if (response.data.success) {
      message.value = '生成が完了しました。'
    } else {
      message.value = 'シフト生成に失敗しました。ルールを見直してください。'
    }
    
    await fetchScheduleData()

  } catch (error) {
    console.error('リクエストエラー:', error)
    message.value = 'サーバーとの通信中にエラーが発生しました。'
  } finally {
    isLoading.value = false
  }
}

const fetchScheduleData = async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/v1/schedule-data/', {
      params: { start_date: startDate.value, end_date: endDate.value },
    })
    assignments.value = response.data.assignments
    leaveRequests.value = response.data.leave_requests
    members.value = response.data.members
    availabilities.value = response.data.availabilities
  } catch (error) {
    console.error('スケジュールデータの読み込みに失敗しました:', error)
  }
}
</script>

<template>
  <div>
    <h1>シフト自動生成</h1>
    <div>
      <label for="start">開始日:</label>
      <input type="date" id="start" v-model="startDate" />
      <label for="end">終了日:</label>
      <input type="date" id="end" v-model="endDate" />
      <button @click="generateShifts" :disabled="isLoading">
        {{ isLoading ? '生成中...' : 'シフトを生成' }}
      </button>
    </div>

    <p>{{ message }}</p>
    <hr />

    <h2>生成結果</h2>
    <div class="table-container">
      <table v-if="members.length > 0">
        <thead>
          <tr>
            <th class="sticky-col">従業員 (期間内休日)</th>
            <th v-for="header in dateHeaders" :key="header.date">
              <div>{{ header.date.slice(5).replace('-', '/') }}</div>
              <div>({{ header.weekday }})</div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="member in members" :key="member.id">
            <td class="sticky-col">
              {{ member.name }}
              <span v-if="memberStats[member.id]" style="font-size: 0.8em; color: #555;">
                (休{{ memberStats[member.id].holidays }})
              </span>
            </td>
            <td v-for="header in dateHeaders" :key="header.date" 
                :class="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].type : 'empty'">
              <select v-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] && scheduleGrid[member.id][header.date].type !== 'infeasible'" v-model="scheduleGrid[member.id][header.date].text">
                <option :value="scheduleGrid[member.id][header.date].text">{{ scheduleGrid[member.id][header.date].text }}</option>
                <option v-if="scheduleGrid[member.id][header.date].type === 'assigned' || scheduleGrid[member.id][header.date].type === 'available'" value="-">（削除）</option>
                <option v-for="pattern in shiftPatterns" :key="pattern.id" :value="pattern.pattern_name">
                  {{ pattern.pattern_name }}
                </option>
              </select>
              <span v-else-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date]">{{ scheduleGrid[member.id][header.date].text }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.table-container {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #ccc;
}
table {
  min-width: 1200px;
  border-collapse: collapse;
  white-space: nowrap;
}
th, td {
  border: 1px solid #ccc;
  padding: 0;
  text-align: center;
  min-width: 100px;
  height: 40px;
}
th {
  background-color: #f4f4f4;
  padding: 8px 4px;
}
td select {
  width: 100%;
  height: 100%;
  padding: 8px 4px;
  border: none;
  background-color: transparent;
  text-align: center;
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
  cursor: pointer;
}
.sticky-col {
  position: sticky;
  left: 0;
  background-color: #fdfdfd;
  font-weight: bold;
  z-index: 1;
  min-width: 150px;
}
td.leave { background-color: #fce4e4; color: #9b2c2c; }
td.leave select { font-weight: bold; }
td.assigned { background-color: #e6fffa; }
td.available { background-color: #f7fafc; }
td.empty { background-color: #edf2f7; color: #a0aec0; }
td.infeasible { background-color: #fff5e6; color: #b7791f; font-weight: bold; font-size: 0.9em; }
</style>