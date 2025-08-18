<script setup>
import { computed } from 'vue'

const props = defineProps({
  members: Array,
  dateHeaders: Array,
  assignments: Array,
  fixedAssignments: Array,
  leaveRequests: Array,
  availabilities: Array,
  shiftPatterns: Array,
  infeasibleDays: Object,
  otherAssignments: Array,
  designatedHolidays: Array,
  selectedCells: Object,
  earnings: Object, // earningsもpropsとして渡す
})

const emit = defineEmits([
  'shift-change',
  'delete-shift',
  'toggle-cell-selection',
  'toggle-day-selection',
])

const getAssignablePatternsForMember = (member) => {
  if (!member.assignable_patterns || member.assignable_patterns.length === 0) {
    return props.shiftPatterns
  }
  return props.shiftPatterns.filter((p) => member.assignable_patterns.includes(p.id))
}

const memberStats = computed(() => {
  const stats = {}
  const totalDays = props.dateHeaders.length
  if (totalDays === 0) return stats

  props.members.forEach((member) => {
    const workDates = new Set()
    props.assignments.forEach((a) => {
      if (a.member_id === member.id) {
        workDates.add(a.shift_date)
      }
    })
    props.otherAssignments.forEach((a) => {
      if (a.member === member.id) {
        workDates.add(a.shift_date)
      }
    })
    props.fixedAssignments.forEach((a) => {
      if (a.member_id === member.id) {
        workDates.add(a.shift_date)
      }
    })

    stats[member.id] = {
      holidays: totalDays - workDates.size,
    }
  })
  return stats
})

const dailyHeadcounts = computed(() => {
  const counts = {}
  props.dateHeaders.forEach((header) => {
    counts[header.date] = {}
    props.shiftPatterns.forEach((p) => {
      counts[header.date][p.pattern_name] = 0
    })
  })

  const uniqueAssignments = new Map()

  props.assignments.forEach((a) => {
    if (a && a.shift_date && a.member_id) {
      const key = `${a.shift_date}-${a.member_id}`
      uniqueAssignments.set(key, a)
    }
  })

  props.fixedAssignments.forEach((a) => {
    if (a && a.shift_date && a.member_id) {
      const key = `${a.shift_date}-${a.member_id}`
      uniqueAssignments.set(key, a)
    }
  })

  uniqueAssignments.forEach((a) => {
    if (a && a.shift_pattern_name && counts[a.shift_date] && counts[a.shift_date][a.shift_pattern_name] !== undefined) {
      counts[a.shift_date][a.shift_pattern_name]++
    }
  })

  return counts
})

const scheduleGrid = computed(() => {
  const grid = {}
  props.members.forEach((member) => {
    grid[member.id] = {}
    props.dateHeaders.forEach((header) => {
      let cell = { text: '/', type: 'empty', patternId: null }

      const dayOfWeek = new Date(header.date + 'T00:00:00').getDay()
      const dayOfWeekForDjango = (dayOfWeek + 6) % 7
      const isAvailable = props.availabilities.some(
        (avail) => avail.member === member.id && avail.day_of_week === dayOfWeekForDjango
      )
      if (isAvailable) {
        cell = { text: '-', type: 'available', patternId: null }
      }

      if (props.infeasibleDays[header.date]) {
        if (cell.type === 'empty' || cell.type === 'available') {
          cell = { text: '', type: 'infeasible', patternId: null, reason: props.infeasibleDays[header.date] }
        }
      }
      grid[member.id][header.date] = cell
    })
  })
  props.leaveRequests.forEach((req) => {
    if (grid[req.member_id]) {
      grid[req.member_id][req.leave_date] = { text: '希望休', type: 'leave', patternId: null }
    }
  })
  props.designatedHolidays.forEach((holiday) => {
    if (grid[holiday.member]) {
      grid[holiday.member][holiday.date] = { text: '指定休日', type: 'designated-holiday', patternId: null }
    }
  })
  props.assignments.forEach((a) => {
    if (grid[a.member_id]) {
      grid[a.member_id][a.shift_date] = { text: a.shift_pattern_name, type: 'assigned', patternId: a.shift_pattern }
    }
  })
  props.otherAssignments.forEach((a) => {
    if (grid[a.member]) {
      grid[a.member][a.shift_date] = { text: a.activity_name, type: 'other', patternId: 'other' }
    }
  })
  props.fixedAssignments.forEach((a) => {
    if (grid[a.member_id]) {
      grid[a.member_id][a.shift_date] = { text: a.shift_pattern_name, type: 'fixed', patternId: a.shift_pattern }
    }
  })
  return grid
})

const getHeadcountClass = (date, pattern) => {
  const count = dailyHeadcounts.value[date]?.[pattern.pattern_name]
  if (count === undefined) return ''
  if (pattern.min_headcount > 0 && count < pattern.min_headcount) {
    return 'headcount-shortage'
  }
  if (pattern.max_headcount !== null && count > pattern.max_headcount) {
    return 'headcount-surplus'
  }
  return ''
}

const onShiftChange = (memberId, date, event) => {
  emit('shift-change', memberId, date, event)
}

const onDeleteShift = (memberId, date) => {
  emit('delete-shift', memberId, date)
}

const onToggleCellSelection = (memberId, date) => {
  emit('toggle-cell-selection', memberId, date)
}

const onToggleDaySelection = (date) => {
  emit('toggle-day-selection', date)
}

const isCellSelected = (memberId, date) => {
  const key = `${memberId}_${date}`
  return props.selectedCells[key]
}

const isDaySelected = (date) => {
  const dayShifts = []
  props.members.forEach((member) => {
    const cell = scheduleGrid.value[member.id]?.[date]
    if (cell && (cell.type === 'assigned' || cell.type === 'fixed')) {
      dayShifts.push({ memberId: member.id, date })
    }
  })

  if (dayShifts.length === 0) {
    return false
  }

  return dayShifts.every((shift) => isCellSelected(shift.memberId, shift.date))
}
</script>

<template>
  <div class="table-container">
    <table v-if="members.length > 0">
      <thead>
        <tr>
          <th class="sticky-col">従業員 (休日 / 給与)</th>
          <th v-for="header in dateHeaders" :key="header.date">
            <div>
              <input
                type="checkbox"
                :checked="isDaySelected(header.date)"
                @change="onToggleDaySelection(header.date)"
                class="header-checkbox"
              />
              {{ header.date.slice(5).replace('-', '/') }} ({{ header.weekday }})
            </div>
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
          <td
            v-for="header in dateHeaders"
            :key="`${member.id}-${header.date}`"
            :class="[
              scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].type : 'empty',
              { 'selected-cell': isCellSelected(member.id, header.date) },
            ]"
            :title="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] ? scheduleGrid[member.id][header.date].reason : ''"
          >
            <input
              type="checkbox"
              v-if="scheduleGrid[member.id]?.[header.date]?.type === 'assigned' || scheduleGrid[member.id]?.[header.date]?.type === 'fixed'"
              :checked="isCellSelected(member.id, header.date)"
              @change="onToggleCellSelection(member.id, header.date)"
              class="shift-checkbox"
            />

            <button
              v-if="scheduleGrid[member.id]?.[header.date]?.type === 'assigned' || scheduleGrid[member.id]?.[header.date]?.type === 'fixed'"
              @click="onDeleteShift(member.id, header.date)"
              class="delete-shift-btn"
            >
              ✖️
            </button>

            <select
              v-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] && scheduleGrid[member.id][header.date].type !== 'leave'"
              :value="scheduleGrid[member.id][header.date].patternId"
              @change="onShiftChange(member.id, header.date, $event)"
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
th,
td {
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
.header-checkbox {
  margin-right: 5px;
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
td.leave {
  background-color: #fce4e4;
  color: #9b2c2c;
  font-weight: bold;
}
td.other {
  background-color: #dbeafe;
  color: #1e40af;
}
td.assigned {
  background-color: #e6fffa;
}
td.available {
  background-color: #edf2f7;
}
td.empty {
  background-color: #edf2f7;
  color: #a0aec0;
}
td.infeasible {
  background-color: #edf2f7;
  color: #b7791f;
  font-weight: bold;
  font-size: 0.9em;
}
td.fixed {
  background-color: #cfe2f3;
  color: #000;
  font-weight: bold;
}
.designated-holiday {
  background-color: #e8daff;
  color: #581c87;
  font-weight: bold;
}

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
