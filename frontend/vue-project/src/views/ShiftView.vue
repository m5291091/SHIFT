<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'

const departments = ref([])
const selectedDepartment = ref(null)
const startDate = ref('')
const endDate = ref('')
const isLoading = ref(false)
const message = ref('')
const members = ref([])
const assignments = ref([])
const fixedAssignments = ref([])
const leaveRequests = ref([])
const availabilities = ref([])
const shiftPatterns = ref([])
const infeasibleDays = ref({})
const earnings = ref({})
const otherAssignments = ref([])
const designatedHolidays = ref([]) // New
const selectedCells = ref({}) // New reactive property for multi-selection

// Descriptions for solver settings
const settingDescriptions = {
  headcount_penalty_cost: '時間帯の最低必要人数が不足した場合のペナルティ。高いほど人数充足を優先します。',
  headcount_surplus_penalty: '時間帯の最高人数を超過した場合のペナルティ。高いほど人数超過を避けます。',
  unavailable_day_penalty: '従業員が勤務不可曜日への割り当てペナルティ。高いほど曜日制約を優先します。',
  incompatible_penalty: '相性の悪いメンバーが同時に勤務した場合のペナルティ。高いほど同時勤務を避けます。',
  holiday_violation_penalty: '月の最低公休日数を下回った場合のペナルティ。高いほど休日制約を優先します。',
  salary_too_low_penalty: '時給制メンバーの給与が目標最低額を下回った場合のペナルティ。高いほど最低給与を優先します。',
  salary_too_high_penalty: '時給制メンバーの給与が目標最高額を上回る場合のペナルティ。高いほど最高給与を避けます。',
  difficulty_bonus_weight: '希望休が多い困難な日にシフトを割り当てた場合のボーナス。高いほど困難な日を埋めることを優先します。',
  pairing_bonus: 'ペアリングメンバーが同時に勤務した場合のボーナス。高いほどペアリングを優先します。',
  shift_preference_bonus: '従業員のシフト希望を尊重した場合のボーナス。高いほど希望を優先します。',
}


onMounted(async () => {
  try {
    const deptResponse = await axios.get('http://127.0.0.1:8000/api/v1/departments/')
    departments.value = deptResponse.data
    if (departments.value.length > 0) {
      selectedDepartment.value = departments.value[0].id
    }
  } catch (error) {
    console.error('データ取得に失敗しました:', error)
  }
})

watch(selectedDepartment, async (newDepartmentId) => {
  if (newDepartmentId) {
    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/v1/shift-patterns/`, { params: { department_id: newDepartmentId } })
      shiftPatterns.value = response.data
    } catch (error) {
      console.error('シフトパターンの取得に失敗しました:', error)
    }
    await fetchScheduleData(true);
  }
});

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
      // Default to empty cell
      let cell = { text: '/', type: 'empty', patternId: null };

      // Check for availability (overrides default empty)
      const dayOfWeek = new Date(header.date + 'T00:00:00').getDay()
      const dayOfWeekForDjango = (dayOfWeek + 6) % 7;
      const isAvailable = availabilities.value.some(avail => 
        avail.member === member.id && avail.day_of_week === dayOfWeekForDjango
      )
      if(isAvailable) {
        cell = { text: '-', type: 'available', patternId: null };
      }

      // Check for day-level infeasibility (overrides empty/available if present)
      if (infeasibleDays.value[header.date]) {
        // Only apply infeasible type if it's an empty or available cell
        if (cell.type === 'empty' || cell.type === 'available') {
          cell = { text: '', type: 'infeasible', patternId: null, reason: infeasibleDays.value[header.date] };
        }
      }
      grid[member.id][header.date] = cell;
    })
  })
  leaveRequests.value.forEach(req => {
    if (grid[req.member_id]) {
      grid[req.member_id][req.leave_date] = { text: '希望休', type: 'leave', patternId: null }
    }
  })
  designatedHolidays.value.forEach(holiday => {
    if (grid[holiday.member]) {
      grid[holiday.member][holiday.date] = { text: '指定休日', type: 'designated-holiday', patternId: null }
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
    } else if (selectedValue === 'designated-holiday') {
      await axios.post('http://127.0.0.1:8000/api/v1/designated-holiday/', {
        member_id: memberId,
        date: date,
      });
    } else {
      const patternId = selectedValue === '' ? null : selectedValue;
      await axios.post('http://127.0.0.1:8000/api/v1/fixed-assignment/', {
        member_id: memberId, shift_date: date, pattern_id: patternId,
      });
    }
    message.value = '手動変更が保存されました。';
    await fetchScheduleData(true);
  } catch (error) {
    message.value = '手動変更の保存に失敗しました。';
    console.error('Error saving shift change:', error);
  } finally {
    isLoading.value = false;
  }
}

const generateShifts = async () => {
  if (!startDate.value || !endDate.value || !selectedDepartment.value) {
    message.value = '部署、開始日、終了日を選択してください。';
    return;
  }
  isLoading.value = true;
  message.value = 'シフトを生成中です...';
  
  try {
    const response = await axios.post('http://127.0.0.1:8000/api/v1/generate-shifts/', {
      department_id: selectedDepartment.value,
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
  if (!selectedDepartment.value) return;
  try {
    const response = await axios.get('http://127.0.0.1:8000/api/v1/schedule-data/', {
      params: { 
        department_id: selectedDepartment.value,
        start_date: startDate.value, 
        end_date: endDate.value 
      },
    });
    if (shouldFetchAssignments) {
        assignments.value = response.data.assignments;
    }
    leaveRequests.value = response.data.leave_requests;
    members.value = response.data.members;
    availabilities.value = response.data.availabilities;
    earnings.value = response.data.earnings;
    otherAssignments.value = response.data.other_assignments;
    fixedAssignments.value = response.data.fixed_assignments;
    designatedHolidays.value = response.data.designated_holidays;
  } catch (error) {
    console.error('スケジュールデータの読み込みに失敗しました:', error);
  }
}

const toggleCellSelection = (memberId, date) => {
  const key = `${memberId}-${date}`;
  selectedCells.value[key] = !selectedCells.value[key];
};

const isCellSelected = (memberId, date) => {
  const key = `${memberId}-${date}`;
  return selectedCells.value[key];
};

const confirmSelectedShifts = async () => {
  const assignmentsToFix = [];
  for (const key in selectedCells.value) {
    if (selectedCells.value[key]) {
      const [memberId, date] = key.split('-');
      const cell = scheduleGrid.value[memberId]?.[date];
      // Only assigned or already fixed shifts can be confirmed
      if (cell && (cell.type === 'assigned' || cell.type === 'fixed') && cell.patternId) {
        assignmentsToFix.push({
          member_id: parseInt(memberId),
          shift_pattern_id: cell.patternId,
          shift_date: date,
        });
      }
    }
  }

  if (assignmentsToFix.length === 0) {
    message.value = '確定するシフトが選択されていません。（生成済みのシフトセルをクリックして選択してください）';
    return;
  }

  isLoading.value = true;
  message.value = '選択されたシフトを固定中...';

  try {
    await axios.post('http://127.0.0.1:8000/api/v1/bulk-fixed-assignments/', {
      assignments: assignmentsToFix,
    });
    message.value = 'シフトが正常に固定されました。';
    selectedCells.value = {}; // Clear selection
    await fetchScheduleData(true); // Refresh all data
  } catch (error) {
    message.value = 'シフトの固定に失敗しました。';
    if (error.response) {
      console.error('Error fixing shifts:', error.response.data);
      const errorDetail = JSON.stringify(error.response.data);
      message.value = `シフトの固定に失敗しました。サーバーエラー: ${errorDetail}`;
    } else {
      console.error('Error fixing shifts:', error.message);
    }
  } finally {
    isLoading.value = false;
  }
};

const deleteShift = async (memberId, date) => {
  isLoading.value = true;
  message.value = 'シフトを削除中...';
  try {
    await axios.post('http://127.0.0.1:8000/api/v1/fixed-assignment/', {
      member_id: memberId, shift_date: date, pattern_id: null,
    });
    message.value = 'シフトが削除されました。';
    await fetchScheduleData(true);
  } catch (error) {
    message.value = 'シフトの削除に失敗しました。';
    console.error('Error deleting shift:', error);
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <div>
    <h1>シフト自動生成</h1>
    <div>
      <label for="department">部署:</label>
      <select id="department" v-model="selectedDepartment">
        <option v-for="dept in departments" :key="dept.id" :value="dept.id">{{ dept.name }}</option>
      </select>
      <label for="start">開始日:</label>
      <input type="date" id="start" v-model="startDate" />
      <label for="end">終了日:</label>
      <input type="date" id="end" v-model="endDate" />
      <button @click="generateShifts" :disabled="isLoading">
        {{ isLoading ? '生成中...' : 'シフトを生成' }}
      </button>
      <button @click="confirmSelectedShifts" :disabled="isLoading" style="margin-left: 10px;">
        選択したシフトを確定
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
            <td v-for="header in dateHeaders" :key="`${member.id}-${header.date}`" 
                :class="[scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].type : 'empty', { 'selected-cell': isCellSelected(member.id, header.date) }]"
                :title="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].reason : ''">
              
              <input 
                type="checkbox"
                v-if="scheduleGrid[member.id]?.[header.date]?.type === 'assigned' || scheduleGrid[member.id]?.[header.date]?.type === 'fixed'"
                :checked="isCellSelected(member.id, header.date)"
                @change="toggleCellSelection(member.id, header.date)"
                class="shift-checkbox"
              />

              <button 
                v-if="scheduleGrid[member.id]?.[header.date]?.type === 'assigned' || scheduleGrid[member.id]?.[header.date]?.type === 'fixed'"
                @click="deleteShift(member.id, header.date)"
                class="delete-shift-btn"
              >✖️</button>

              <select 
                v-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] && scheduleGrid[member.id][header.date].type !== 'leave'" 
                :value="scheduleGrid[member.id][header.date].patternId"
                @change="handleShiftChange(member.id, header.date, $event)"
              >
                <option :value="scheduleGrid[member.id][header.date].patternId" selected disabled>{{ scheduleGrid[member.id][header.date].text }}</option>
                <option v-if="scheduleGrid[member.id]?.[header.date]?.patternId" value="">（削除）</option>
                <option v-for="pattern in getAssignablePatternsForMember(member)" :key="pattern.id" :value="pattern.id">
                  {{ pattern.pattern_name }}
                </option>
                <option value="other">その他...</option>
                <option value="designated-holiday">指定休日</option>
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
  position: relative; /* For checkbox positioning */
}
th {
  background-color: #f4f4f4;
  padding: 8px 4px;
}
.shift-checkbox {
  position: absolute;
  top: 5px;
  left: 5px;
  z-index: 2;
}
.delete-shift-btn {
  position: absolute;
  top: 1px;
  right: 1px;
  z-index: 3;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #999;
  font-size: 14px;
  padding: 2px;
  line-height: 1;
}
.delete-shift-btn:hover {
  color: #000;
}
td select {
  width: 100%;
  height: 100%;
  padding: 8px 4px 8px 25px; /* Make space for checkbox */
  border: none;
  background-color: transparent;
  text-align: center;
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
  cursor: pointer;
  box-sizing: border-box;
}
td > span {
  display: inline-block;
  width: 100%;
  padding: 8px 4px 8px 25px; /* Make space for checkbox */
  box-sizing: border-box;
  text-align: center;
}
.sticky-col {
  position: sticky;
  left: 0;
  background-color: #fdfdfd;
  font-weight: bold;
  z-index: 1;
  min-width: 150px;
}
td.leave { background-color: #fce4e4; color: #9b2c2c; font-weight: bold; }
td.other { background-color: #dbeafe; color: #1e40af; }
td.assigned { background-color: #e6fffa; }
td.available { background-color: #edf2f7; }
td.empty { background-color: #edf2f7; color: #a0aec0; }
td.infeasible { background-color: #edf2f7; color: #b7791f; font-weight: bold; font-size: 0.9em; }
td.fixed { background-color: #cfe2f3; color: #000; font-weight: bold; }
.designated-holiday { background-color: #e8daff; color: #581c87; font-weight: bold; }

.selected-cell {
  border: 2px solid #007bff !important; /* Blue border for selected cells */
  box-shadow: 0 0 5px rgba(0, 123, 255, 0.5); /* Subtle glow */
}

/* Ensure select element doesn't hide the border */
td.selected-cell select {
  border: none !important;
  box-shadow: none !important;
}

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
