<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const startDate = ref('')
const endDate = ref('')
const isLoading = ref(false)
const message = ref('')
const members = ref([])
const assignments = ref([])
const fixedAssignments = ref([]) // 追加
const leaveRequests = ref([])
const availabilities = ref([])
const shiftPatterns = ref([])
const infeasibleDays = ref({})
const earnings = ref({})
const otherAssignments = ref([])

onMounted(async () => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/v1/shift-patterns/')
    shiftPatterns.value = response.data
  } catch (error) {
    console.error('シフトパターンの取得に失敗しました:', error)
  }
  await fetchScheduleData(true);
})

const getAssignablePatternsForMember = (member) => {
  if (!member.assignable_patterns || member.assignable_patterns.length === 0) {
    return shiftPatterns.value;
  }
  return shiftPatterns.value.filter(p => member.assignable_patterns.includes(p.id));
}

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
    const workDates = new Set();
    assignments.value.forEach(a => {
      if (a.member_id === member.id) {
        workDates.add(a.shift_date);
      }
    });
    otherAssignments.value.forEach(a => {
      if (a.member === member.id) {
        workDates.add(a.shift_date);
      }
    });
    fixedAssignments.value.forEach(a => {
      if (a.member_id === member.id) {
        workDates.add(a.shift_date);
      }
    });
    
    stats[member.id] = {
      holidays: totalDays - workDates.size,
    }
  })
  return stats
})

const dailyHeadcounts = computed(() => {
  const counts = {}
  dateHeaders.value.forEach(header => {
    counts[header.date] = {}
    shiftPatterns.value.forEach(p => {
      counts[header.date][p.pattern_name] = 0
    })
  })

  const uniqueAssignments = new Map();

  // assignments をまず Map に登録
  assignments.value.forEach(a => {
    if (a && a.shift_date && a.member_id) {
      const key = `${a.shift_date}-${a.member_id}`;
      uniqueAssignments.set(key, a);
    }
  });

  // fixedAssignments を登録（重複していれば上書きされるが、内容は同じはず）
  fixedAssignments.value.forEach(a => {
    if (a && a.shift_date && a.member_id) {
      const key = `${a.shift_date}-${a.member_id}`;
      uniqueAssignments.set(key, a);
    }
  });

  // Map の値（ユニークなアサインメント）をループしてカウント
  uniqueAssignments.forEach(a => {
    if (a && a.shift_pattern_name && counts[a.shift_date] && counts[a.shift_date][a.shift_pattern_name] !== undefined) {
      counts[a.shift_date][a.shift_pattern_name]++;
    }
  });

  return counts
})

const scheduleGrid = computed(() => {
  const grid = {}
  members.value.forEach(member => {
    grid[member.id] = {}
    dateHeaders.value.forEach(header => {
      if (infeasibleDays.value[header.date]) {
        grid[member.id][header.date] = { text: '人員不足', type: 'infeasible', patternId: null, reason: infeasibleDays.value[header.date] }
      } else {
        grid[member.id][header.date] = { text: '/', type: 'empty', patternId: null }
        const dayOfWeek = new Date(header.date + 'T00:00:00').getDay()
        const dayOfWeekForDjango = (dayOfWeek + 6) % 7;
        const isAvailable = availabilities.value.some(avail => 
          avail.member === member.id && avail.day_of_week === dayOfWeekForDjango
        )
        if(isAvailable) {
          grid[member.id][header.date] = { text: '-', type: 'available', patternId: null }
        }
      }
    })
  })
  leaveRequests.value.forEach(req => {
    if (grid[req.member_id]) {
      grid[req.member_id][req.leave_date] = { text: '✖︎', type: 'leave', patternId: null }
    }
  })
  assignments.value.forEach(a => {
    if (grid[a.member_id]) {
      grid[a.member_id][a.shift_date] = { text: a.shift_pattern_name, type: 'assigned', patternId: a.shift_pattern }
    }
  })
  otherAssignments.value.forEach(a => {
    if (grid[a.member]) {
      grid[a.member][a.shift_date] = { text: a.activity_name, type: 'other', patternId: 'other' }
    }
  })
  fixedAssignments.value.forEach(a => {
    if (grid[a.member_id]) {
      grid[a.member_id][a.shift_date] = { text: a.shift_pattern_name, type: 'fixed', patternId: a.shift_pattern }
    }
  })
  return grid
})

const getHeadcountClass = (date, pattern) => {
  const count = dailyHeadcounts.value[date]?.[pattern.pattern_name];
  if (count === undefined) return '';
  if (pattern.min_headcount > 0 && count < pattern.min_headcount) {
    return 'headcount-shortage';
  }
  if (pattern.max_headcount !== null && count > pattern.max_headcount) {
    return 'headcount-surplus';
  }
  return '';
}

const handleShiftChange = async (memberId, date, event) => {
  const selectedValue = event.target.value
  isLoading.value = true;
  message.value = '手動変更を保存中...';
  
  try {
    if (selectedValue === 'other') {
      const activityName = prompt('業務内容を入力してください（例：研修）');
      if (activityName) {
        await axios.post('http://127.0.0.1:8000/api/v1/other-assignment/', {
          member_id: memberId, shift_date: date, activity_name: activityName,
        });
      }
    } else {
      const patternId = selectedValue === 'delete' ? null : selectedValue;
      await axios.post('http://127.0.0.1:8000/api/v1/manual-assignment/', {
        member_id: memberId, shift_date: date, pattern_id: patternId,
      });
    }
    await fetchScheduleData(true);
    message.value = '手動変更が保存されました。';
  } catch (error) {
    message.value = '手動変更の保存に失敗しました。';
    console.error(error);
  } finally {
    isLoading.value = false;
  }
}

const generateShifts = async () => {
  if (!startDate.value || !endDate.value) {
    message.value = '開始日と終了日を選択してください。';
    return;
  }
  isLoading.value = true;
  message.value = 'シフトを生成中です...';
  
  try {
    const response = await axios.post('http://127.0.0.1:8000/api/v1/generate-shifts/', {
      start_date: startDate.value,
      end_date: endDate.value,
    });
    
    infeasibleDays.value = response.data.infeasible_days || {};
    assignments.value = response.data.assignments || [];
    
    if (Object.keys(infeasibleDays.value).length > 0) {
      message.value = '人員不足のため一部の日付が生成できませんでした。';
    } else if (response.data.success) {
      message.value = '生成が完了しました。';
    } else {
      message.value = 'シフト生成に失敗しました。ルールが厳しすぎる可能性があります。';
    }
    await fetchScheduleData(false); // assignments以外を再取得
  } catch (error) {
    console.error('リクエストエラー:', error);
    message.value = 'サーバーとの通信中にエラーが発生しました。';
  } finally {
    isLoading.value = false;
  }
}

const fetchScheduleData = async (shouldFetchAssignments = true) => {
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/v1/schedule-data/', {
      params: { start_date: startDate.value, end_date: endDate.value },
    });
    if (shouldFetchAssignments) {
        assignments.value = response.data.assignments;
    }
    leaveRequests.value = response.data.leave_requests;
    members.value = response.data.members;
    availabilities.value = response.data.availabilities;
    earnings.value = response.data.earnings;
    otherAssignments.value = response.data.other_assignments;
    fixedAssignments.value = response.data.fixed_assignments; // 追加
  } catch (error) {
    console.error('スケジュールデータの読み込みに失敗しました:', error);
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
            <th class="sticky-col">従業員 (休日 / 給与)</th>
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
              <div class="stats">
                <span v-if="memberStats[member.id]">(休{{ memberStats[member.id].holidays }})</span>
                <span v-if="earnings[member.id]">(¥{{ earnings[member.id].toLocaleString() }})</span>
              </div>
            </td>
            <td v-for="header in dateHeaders" :key="header.date" 
                :class="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].type : 'empty'"
                :title="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].reason : ''">
              <select 
                v-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] && scheduleGrid[member.id][header.date].type !== 'infeasible' && scheduleGrid[member.id][header.date].type !== 'leave' && scheduleGrid[member.id][header.date].type !== 'fixed'" 
                :value="scheduleGrid[member.id][header.date].patternId"
                @change="handleShiftChange(member.id, header.date, $event)"
              >
                <option :value="scheduleGrid[member.id][header.date].patternId" selected disabled>{{ scheduleGrid[member.id][header.date].text }}</option>
                <option v-if="scheduleGrid[member.id][header.date].type !== 'empty' && scheduleGrid[member.id][header.date].type !== 'available'" value="delete">（削除）</option>
                <option v-for="pattern in getAssignablePatternsForMember(member)" :key="pattern.id" :value="pattern.id">
                  {{ pattern.pattern_name }}
                </option>
                <option value="other">その他...</option>
              </select>
              <span v-else-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date]">{{ scheduleGrid[member.id][header.date].text }}</span>
            </td>
          </tr>
        </tbody>
        <tfoot v-if="shiftPatterns.length > 0">
          <tr v-for="pattern in shiftPatterns" :key="pattern.id">
            <td class="sticky-col summary-header">{{ pattern.pattern_name }} 人数</td>
            <td v-for="header in dateHeaders" :key="header.date" :class="getHeadcountClass(header.date, pattern)">
              {{ dailyHeadcounts[header.date] ? dailyHeadcounts[header.date][pattern.pattern_name] : 0 }}
            </td>
          </tr>
        </tfoot>
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
  vertical-align: middle;
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
td.leave { background-color: #fce4e4; color: #9b2c2c; font-weight: bold; padding: 8px 4px; }
td.other { background-color: #dbeafe; color: #1e40af; }
td.assigned { background-color: #e6fffa; }
td.available { background-color: #f7fafc; }
td.empty { background-color: #edf2f7; color: #a0aec0; }
td.infeasible { background-color: #fff5e6; color: #b7791f; font-weight: bold; font-size: 0.9em; padding: 8px 4px;}
td.fixed { background-color: #cfe2f3; color: #000; font-weight: bold; padding: 8px 4px; }
.stats {
  font-size: 0.8em;
  color: #555;
  font-weight: normal;
}
tfoot {
  font-weight: bold;
  background-color: #f0f8ff;
}
.summary-header {
  background-color: #e6f4ff;
  position: sticky;
  left: 0;
  z-index: 2;
}
.headcount-shortage {
  background-color: #ffebee;
  color: #c62828;
}
.headcount-surplus {
  background-color: #fff3e0;
  color: #ef6c00;
}
</style>