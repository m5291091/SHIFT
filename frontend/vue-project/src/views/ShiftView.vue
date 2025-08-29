<script setup>
import { ref, computed, onMounted, watch, inject } from 'vue'
import OtherAssignmentModal from '@/components/OtherAssignmentModal.vue'
import ShiftControlHeader from '@/components/ShiftControlHeader.vue'

const axios = inject('axios'); // Inject the provided axios instance

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
const paidLeaves = ref([]) // New
const selectedCells = ref({}) // New reactive property for multi-selection
const solverSettings = ref({}) // Current solver settings being displayed/edited
const solverPatterns = ref([]) // All saved solver patterns for the department
const selectedSolverPatternId = ref(null) // ID of the currently selected pattern in the dropdown
const newPatternName = ref('') // For saving a new pattern

// Modal state
const isOtherAssignmentModalVisible = ref(false)
const selectedMemberForModal = ref(null)
const selectedDateForModal = ref('')

// Descriptions for solver settings
const settingDescriptions = {
  headcount_penalty_cost: '時間帯の最低必要人数が不足した場合のペナルティ。高いほど人数充足を優先します。',
  unavailable_day_penalty: '従業員が勤務不可曜日への割り当てペナルティ。高いほど曜日制約を優先します。',
  incompatible_penalty: '相性の悪いメンバーが同時に勤務した場合のペナルティ。高いほど同時勤務を避けます。',
  holiday_violation_penalty: '月の最低公休日数を下回った場合のペナルティ。高いほど休日制約を優先します。',
  consecutive_work_violation_penalty: '連続勤務数上限を超過した場合のペナルティ。高いほど連続勤務制約を優先します。',
  salary_too_low_penalty: '時給制メンバーの給与が目標最低額を下回った場合のペナルティ。高いほど最低給与を優先します。',
  salary_too_high_penalty: '時給制メンバーの給与が目標最高額を上回る場合のペナルティ。高いほど最高給与を避けます。',
  difficulty_bonus_weight: '希望休が多い困難な日にシフトを割り当てた場合のボーナス。高いほど困難な日を埋めることを優先します。',
  work_day_deviation_penalty: '勤務日数に偏りがある場合のペナルティ。高いほど勤務日数の均等化を優先します。',
  pairing_bonus: 'ペアリングメンバーが同時に勤務した場合のボーナス。高いほどペアリングを優先します。',
  shift_preference_bonus: '従業員のシフト希望を尊重した場合のボーナス。高いほど希望を優先します。',
}

onMounted(async () => {
  try {
    const deptResponse = await axios.get('/api/v1/departments/')
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
      const response = await axios.get(`/shift-patterns/`, { params: { department_id: newDepartmentId } })
      shiftPatterns.value = response.data
    } catch (error) {
      console.error('シフトパターンの取得に失敗しました:', error)
    }
    await fetchScheduleData(true)
    await fetchAllSolverPatterns(newDepartmentId) // Fetch all patterns for the department
  }
})

const fetchAllSolverPatterns = async (departmentId) => {
  try {
    const response = await axios.get(`/solver-settings/`, { params: { department: departmentId } })
    solverPatterns.value = response.data
    if (solverPatterns.value.length > 0) {
      // Try to find a default pattern, otherwise select the first one
      const defaultPattern = solverPatterns.value.find(p => p.is_default)
      selectedSolverPatternId.value = defaultPattern ? defaultPattern.id : solverPatterns.value[0].id
      loadSolverPattern() // Load the selected pattern into solverSettings
    } else {
      // If no patterns exist, initialize with default values
      solverSettings.value = {
        headcount_penalty_cost: 10000000,
        holiday_violation_penalty: 50000,
        incompatible_penalty: 60000,
        consecutive_work_violation_penalty: 45000,
        salary_too_low_penalty: 40000,
        salary_too_high_penalty: 30000,
        difficulty_bonus_weight: 10000,
        work_day_deviation_penalty: 7000,
        pairing_bonus: 5000,
        shift_preference_bonus: 100,
        unavailable_day_penalty: 70000,
      }
      selectedSolverPatternId.value = null
    }
  } catch (error) {
    console.error('ソルバー設定パターンの取得に失敗しました:', error)
    // Fallback to default values if API call fails
    solverSettings.value = {
      headcount_penalty_cost: 10000000,
      holiday_violation_penalty: 50000,
      incompatible_penalty: 60000,
      consecutive_work_violation_penalty: 45000,
      salary_too_low_penalty: 40000,
      salary_too_high_penalty: 30000,
      difficulty_bonus_weight: 10000,
      work_day_deviation_penalty: 7000,
      pairing_bonus: 5000,
      shift_preference_bonus: 100,
      unavailable_day_penalty: 70000,
    }
    selectedSolverPatternId.value = null
  }
}

const loadSolverPattern = () => {
  const selectedPattern = solverPatterns.value.find(p => p.id === selectedSolverPatternId.value)
  if (selectedPattern) {
    // Copy all relevant fields from the selected pattern to solverSettings
    for (const key in selectedPattern) {
      if (key !== 'id' && key !== 'department' && key !== 'name' && key !== 'is_default') {
        solverSettings.value[key] = selectedPattern[key]
      }
    }
  }
}

const saveCurrentSolverSettings = async () => {
  isLoading.value = true
  message.value = 'ソルバー設定を保存中...'
  try {
    if (selectedSolverPatternId.value) {
      // Update existing pattern
      await axios.put(`/solver-settings/${selectedSolverPatternId.value}/`, solverSettings.value)
      message.value = 'ソルバー設定が更新されました。'
    } else {
      // This case should ideally not happen if a pattern is always selected/created
      message.value = '保存するパターンが選択されていません。'
    }
    await fetchAllSolverPatterns(selectedDepartment.value) // Refresh patterns
  } catch (error) {
    message.value = 'ソルバー設定の保存に失敗しました。'
    console.error('Error saving solver settings:', error)
  } finally {
    isLoading.value = false
  }
}

const saveNewSolverPattern = async () => {
  if (!newPatternName.value.trim()) {
    message.value = '新しいパターン名を入力してください。'
    return
  }
  isLoading.value = true
  message.value = '新しいソルバーパターンを保存中...'
  try {
    const newPatternData = {
      ...solverSettings.value, // Copy current settings
      department: selectedDepartment.value,
      name: newPatternName.value.trim(),
      is_default: false // New patterns are not default by default
    }
    const response = await axios.post(`/solver-settings/`, newPatternData)
    message.value = `新しいパターン「${newPatternName.value}」が保存されました。`
    newPatternName.value = '' // Clear input
    await fetchAllSolverPatterns(selectedDepartment.value) // Refresh patterns
    selectedSolverPatternId.value = response.data.id // Select the newly created pattern
    loadSolverPattern() // Load it into the form
  } catch (error) {
    message.value = '新しいソルバーパターンの保存に失敗しました。'
    console.error('Error saving new solver pattern:', error)
  } finally {
    isLoading.value = false
  }
}

const setDefaultPattern = async () => {
  if (!selectedSolverPatternId.value) {
    message.value = 'デフォルトに設定するパターンを選択してください。'
    return
  }
  isLoading.value = true
  message.value = 'デフォルトパターンを設定中...'
  try {
    // First, set all patterns for this department to not default
    for (const pattern of solverPatterns.value) {
      if (pattern.is_default && pattern.id !== selectedSolverPatternId.value) {
        await axios.put(`/solver-settings/${pattern.id}/`, { is_default: false })
      }
    }
    // Then, set the selected pattern as default
    await axios.put(`/solver-settings/${selectedSolverPatternId.value}/`, { is_default: true })
    message.value = 'デフォルトパターンが設定されました。'
    await fetchAllSolverPatterns(selectedDepartment.value) // Refresh patterns to reflect changes
  } catch (error) {
    message.value = 'デフォルトパターンの設定に失敗しました。'
    console.error('Error setting default pattern:', error)
  } finally {
    isLoading.value = false
  }
}

const getAssignablePatternsForMember = (member) => {
  if (!member.assignable_patterns || member.assignable_patterns.length === 0) {
    return shiftPatterns.value
  }
  return shiftPatterns.value.filter((p) => member.assignable_patterns.includes(p.id))
}

const formatDate = (dateObj) => {
  const y = dateObj.getFullYear()
  const m = String(dateObj.getMonth() + 1).padStart(2, '0')
  const d = String(dateObj.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const dateHeaders = computed(() => {
  if (!startDate.value || !endDate.value) return []
  const dates = []
  let currentDate = new Date(startDate.value + 'T00:00:00')
  const lastDate = new Date(endDate.value + 'T00:00:00')
  const weekdays = ['日', '月', '火', '水', '木', '火', '金', '土']
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
  if (totalDays === 0) return stats

  members.value.forEach((member) => {
    const workDates = new Set()
    assignments.value.forEach((a) => {
      if (a.member_id === member.id) {
        workDates.add(a.shift_date)
      }
    })
    otherAssignments.value.forEach((a) => {
      if (a.member === member.id) {
        workDates.add(a.shift_date)
      }
    })
    fixedAssignments.value.forEach((a) => {
      if (a.member_id === member.id) {
        workDates.add(a.shift_date)
      }
    })
    paidLeaves.value.forEach((pl) => { // Added
      if (pl.member === member.id) {
        workDates.add(pl.date)
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
  dateHeaders.value.forEach((header) => {
    counts[header.date] = {}
    shiftPatterns.value.forEach((p) => {
      counts[header.date][p.pattern_name] = 0
    })
  })

  const uniqueAssignments = new Map()

  // assignments をまず Map に登録
  assignments.value.forEach((a) => {
    if (a && a.shift_date && a.member_id) {
      const key = `${a.shift_date}-${a.member_id}`
      uniqueAssignments.set(key, a)
    }
  })

  // fixedAssignments を登録（重複していれば上書きされるが、内容は同じはず）
  fixedAssignments.value.forEach((a) => {
    if (a && a.shift_date && a.member_id) {
      const key = `${a.shift_date}-${a.member_id}`
      uniqueAssignments.set(key, a)
    }
  })

  // Map の値（ユニークなアサインメント）をループしてカウント
  uniqueAssignments.forEach((a) => {
    if (a && a.shift_pattern_name && counts[a.shift_date] && counts[a.shift_date][a.shift_pattern_name] !== undefined) {
      counts[a.shift_date][a.shift_pattern_name]++
    }
  })

  return counts
})

const scheduleGrid = computed(() => {
  const grid = {}
  members.value.forEach((member) => {
    grid[member.id] = {}
    dateHeaders.value.forEach((header) => {
      // Default to empty cell
      let cell = { text: '', type: 'empty', patternId: null }

      // Check for availability (overrides default empty)
      const dayOfWeek = new Date(header.date + 'T00:00:00').getDay()
      const dayOfWeekForDjango = (dayOfWeek + 6) % 7
      const isAvailable = availabilities.value.some(
        (avail) => avail.member === member.id && avail.day_of_week === dayOfWeekForDjango
      )
      if (isAvailable) {
        cell = { text: '-', type: 'available', patternId: null }
      }

      // Check for day-level infeasibility (overrides empty/available if present)
      if (infeasibleDays.value[header.date]) {
        // Only apply infeasible type if it's an empty or available cell
        if (cell.type === 'empty' || cell.type === 'available') {
          cell = { text: '', type: 'infeasible', patternId: null, reason: infeasibleDays.value[header.date] }
        }
      }
      grid[member.id][header.date] = cell
    })
  })
  leaveRequests.value.forEach((req) => {
    if (grid[req.member_id]) {
      grid[req.member_id][req.leave_date] = { text: '希望休', type: 'leave', patternId: null }
    }
  })
  designatedHolidays.value.forEach((holiday) => {
    if (grid[holiday.member]) {
      grid[holiday.member][holiday.date] = { text: '指定休日', type: 'designated-holiday', patternId: null }
    }
  })
  paidLeaves.value.forEach((pl) => { // Added
    if (grid[pl.member]) {
      grid[pl.member][pl.date] = { text: '有給', type: 'paid-leave', patternId: null }
    }
  })
  assignments.value.forEach((a) => {
    if (grid[a.member_id]) {
      grid[a.member_id][a.shift_date] = { text: a.shift_pattern_name, type: 'assigned', patternId: a.shift_pattern }
    }
  })
  otherAssignments.value.forEach((a) => {
    if (grid[a.member]) {
      grid[a.member][a.shift_date] = { text: a.activity_name, type: 'other', patternId: 'other' }
    }
  })
  fixedAssignments.value.forEach((a) => {
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

const handleShiftChange = async (memberId, date, event) => {
  const selectedValue = event.target.value

  if (selectedValue === '') {
    await deleteShift(memberId, date)
    return
  }

  if (selectedValue === 'other') {
    selectedMemberForModal.value = members.value.find((m) => m.id === memberId)
    selectedDateForModal.value = date
    isOtherAssignmentModalVisible.value = true
    // The select box visually changes to "その他...".
    // We need to refresh the data to revert it back to its original state
    // while the modal is open.
    await fetchScheduleData(true)
    return
  }

  isLoading.value = true
  message.value = '手動変更を保存中...'

  try {
    if (selectedValue === 'designated-holiday') {
      await axios.post('/designated-holiday/', {
        member_id: memberId,
        date: date,
      })
    } else if (selectedValue === 'paid-leave') { // Added
      await axios.post('/paid-leave/', {
        member_id: memberId,
        date: date,
      })
    } else {
      const patternId = selectedValue
      await axios.post('/fixed-assignment/', {
        member_id: memberId,
        shift_date: date,
        pattern_id: patternId,
      })
    }
    message.value = '手動変更が保存されました。'
    await fetchScheduleData(true)
  } catch (error) {
    message.value = '手動変更の保存に失敗しました。'
    console.error('Error saving shift change:', error)
    // エラー時もUIを最新の状態に保つ
    await fetchScheduleData(true)
  } finally {
    isLoading.value = false
  }
}

const handleCloseModal = () => {
  isOtherAssignmentModalVisible.value = false
}

const handleSaveOtherAssignment = async (activityName) => {
  isOtherAssignmentModalVisible.value = false
  isLoading.value = true
  message.value = '「その他」の割り当てを保存中...'

  try {
    await axios.post('/other-assignment/', {
      member_id: selectedMemberForModal.value.id,
      shift_date: selectedDateForModal.value,
      activity_name: activityName,
    })
    message.value = '保存されました。'
    await fetchScheduleData(true)
  } catch (error) {
    message.value = '保存に失敗しました。'
    console.error('Error saving other assignment:', error)
  } finally {
    isLoading.value = false
  }
}

const generateShifts = async () => {
  if (!startDate.value || !endDate.value || !selectedDepartment.value) {
    message.value = '部署、開始日、終了日を選択してください。'
    return
  }

  if (!confirm('未確定のシフトは上書きされます。よろしいですか？')) {
    return
  }

  isLoading.value = true
  message.value = 'シフトを生成中です...'

  try {
    const response = await axios.post('/generate-shifts/', {
      department_id: selectedDepartment.value,
      start_date: startDate.value,
      end_date: endDate.value,
    })

    infeasibleDays.value = response.data.infeasible_days || {}
    assignments.value = response.data.assignments || []

    if (Object.keys(infeasibleDays.value).length > 0) {
      message.value = '人員不足のため一部の日付が生成できませんでした。'
    } else if (response.data.success) {
      message.value = '生成が完了しました。'
    } else {
      message.value = 'シフト生成に失敗しました。ルールが厳しすぎる可能性があります。'
    }
    await fetchScheduleData(true) // 全データを再取得
  } catch (error) {
    console.error('リクエストエラー:', error)
    message.value = 'サーバーとの通信中にエラーが発生しました。'
  } finally {
    isLoading.value = false
  }
}

const fetchScheduleData = async (shouldFetchAssignments = true) => {
  if (!selectedDepartment.value) return
  try {
    const response = await axios.get('/schedule-data/', {
      params: {
        department_id: selectedDepartment.value,
        start_date: startDate.value,
        end_date: endDate.value,
      },
    })
    if (shouldFetchAssignments) {
      assignments.value = response.data.assignments
    }
    leaveRequests.value = response.data.leave_requests
    members.value = response.data.members
    availabilities.value = response.data.availabilities
    earnings.value = response.data.earnings
    otherAssignments.value = response.data.other_assignments
    fixedAssignments.value = response.data.fixed_assignments
    designatedHolidays.value = response.data.designated_holidays
    paidLeaves.value = response.data.paid_leaves // Added
  } catch (error) {
    console.error('スケジュールデータの読み込みに失敗しました:', error)
  }
}

const toggleCellSelection = (memberId, date) => {
  const key = `${memberId}_${date}`
  selectedCells.value[key] = !selectedCells.value[key]
}

const isCellSelected = (memberId, date) => {
  const key = `${memberId}_${date}`
  return selectedCells.value[key]
}

const toggleDaySelection = (date) => {
  const dayShifts = []
  members.value.forEach((member) => {
    const cell = scheduleGrid.value[member.id]?.[date]
    if (cell && (cell.type === 'assigned' || cell.type === 'fixed')) {
      dayShifts.push({ memberId: member.id, date })
    }
  })

  const allSelected = dayShifts.every((shift) => isCellSelected(shift.memberId, shift.date))

  dayShifts.forEach((shift) => {
    const key = `${shift.memberId}_${shift.date}`
    selectedCells.value[key] = !allSelected
  })
}

const isDaySelected = (date) => {
  const dayShifts = []
  members.value.forEach((member) => {
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

const toggleMemberSelection = (memberId) => {
  const memberShifts = []
  dateHeaders.value.forEach((header) => {
    const cell = scheduleGrid.value[memberId]?.[header.date]
    if (cell && (cell.type === 'assigned' || cell.type === 'fixed')) {
      memberShifts.push({ memberId: memberId, date: header.date })
    }
  })

  const allSelected = isMemberSelected(memberId)

  memberShifts.forEach((shift) => {
    const key = `${shift.memberId}_${shift.date}`
    selectedCells.value[key] = !allSelected
  })
}

const isMemberSelected = (memberId) => {
  const memberShifts = []
  dateHeaders.value.forEach((header) => {
    const cell = scheduleGrid.value[memberId]?.[header.date]
    if (cell && (cell.type === 'assigned' || cell.type === 'fixed')) {
      memberShifts.push({ memberId: memberId, date: header.date })
    }
  })

  if (memberShifts.length === 0) {
    return false
  }

  return memberShifts.every((shift) => isCellSelected(shift.memberId, shift.date))
}

const confirmSelectedShifts = async () => {
  const assignmentsToFix = []
  for (const key in selectedCells.value) {
    if (selectedCells.value[key]) {
      const [memberId, date] = key.split('_')
      const cell = scheduleGrid.value[memberId]?.[date]
      // Only assigned or already fixed shifts can be confirmed
      if (cell && (cell.type === 'assigned' || cell.type === 'fixed') && cell.patternId) {
        assignmentsToFix.push({
          member_id: parseInt(memberId),
          shift_pattern_id: cell.patternId,
          shift_date: date,
        })
      }
    }
  }

  if (assignmentsToFix.length === 0) {
    message.value = '確定するシフトが選択されていません。（生成済みのシフトセルをクリックして選択してください）'
    return
  }

  isLoading.value = true
  message.value = '選択されたシフトを固定中...'

  try {
    await axios.post('/bulk-fixed-assignments/', {
      assignments: assignmentsToFix,
    })
    message.value = 'シフトが正常に固定されました。'
    selectedCells.value = {} // Clear selection
    await fetchScheduleData(true) // Refresh all data
  } catch (error) {
    message.value = 'シフトの固定に失敗しました。'
    if (error.response) {
      console.error('Error fixing shifts:', error.response.data)
      const errorDetail = JSON.stringify(error.response.data)
      message.value = `シフトの固定に失敗しました。サーバーエラー: ${errorDetail}`
    } else {
      console.error('Error fixing shifts:', error.message)
    }
  } finally {
    isLoading.value = false
  }
}

const deleteSelectedShifts = async () => {
  const assignmentIdsToDelete = []
  const fixedAssignmentIdsToDelete = []

  for (const key in selectedCells.value) {
    if (selectedCells.value[key]) {
      const [memberId, date] = key.split('_')
      const cell = scheduleGrid.value[memberId]?.[date]

      if (cell) {
        if (cell.type === 'assigned') {
          const assignment = assignments.value.find(a => a.member_id == memberId && a.shift_date == date)
          if (assignment) {
            assignmentIdsToDelete.push(assignment.id)
          }
        } else if (cell.type === 'fixed') {
          const fixedAssignment = fixedAssignments.value.find(a => a.member_id == memberId && a.shift_date == date)
          if (fixedAssignment) {
            fixedAssignmentIdsToDelete.push(fixedAssignment.id)
          }
        }
      }
    }
  }

  if (assignmentIdsToDelete.length === 0 && fixedAssignmentIdsToDelete.length === 0) {
    message.value = '削除するシフトが選択されていません。（シフトセルをクリックして選択してください）'
    return
  }

  if (!confirm('選択されたシフトを削除してもよろしいですか？')) {
    return
  }

  isLoading.value = true
  message.value = '選択されたシフトを削除中...'

  try {
    const deletePromises = []
    if (assignmentIdsToDelete.length > 0) {
      deletePromises.push(axios.post('/bulk-delete-assignments/', { assignment_ids: assignmentIdsToDelete }))
    }
    if (fixedAssignmentIdsToDelete.length > 0) {
      deletePromises.push(axios.post('/bulk-delete-fixed-assignments/', { fixed_assignment_ids: fixedAssignmentIdsToDelete }))
    }

    await Promise.all(deletePromises)

    message.value = '選択されたシフトが削除されました。'
    selectedCells.value = {} // Clear selection
    await fetchScheduleData(true) // Refresh all data
  } catch (error) {
    message.value = 'シフトの削除に失敗しました。'
    console.error('Error deleting shifts:', error)
  } finally {
    isLoading.value = false
  }
}

const deleteShift = async (memberId, date) => {
  if (!confirm('このシフトを削除してもよろしいですか？')) {
    // ユーザーがキャンセルした場合、セレクトボックスの表示を元に戻すためにデータを再取得
    await fetchScheduleData(true)
    return
  }
  isLoading.value = true
  message.value = 'シフトを削除中...'
  try {
    await axios.post('/fixed-assignment/', {
      member_id: memberId,
      shift_date: date,
      pattern_id: null,
    })
    message.value = 'シフトが削除されました。'
    await fetchScheduleData(true)
  } catch (error) {
    message.value = 'シフトの削除に失敗しました。'
    console.error('Error deleting shift:', error)
  } finally {
    isLoading.value = false
  }
}

const fetchSolverSettings = async (departmentId) => {
  try {
    const response = await axios.get(`/solver-settings/${departmentId}/`)
    solverSettings.value = response.data
  } catch (error) {
    console.error('ソルバー設定の取得に失敗しました:', error)
    // If settings don't exist, initialize with default values or an empty object
    solverSettings.value = {
      headcount_penalty_cost: 10000000,
      holiday_violation_penalty: 50000,
      incompatible_penalty: 60000,
      consecutive_work_violation_penalty: 45000,
      salary_too_low_penalty: 40000,
      salary_too_high_penalty: 30000,
      difficulty_bonus_weight: 10000,
      work_day_deviation_penalty: 7000,
      pairing_bonus: 5000,
      shift_preference_bonus: 100,
      unavailable_day_penalty: 70000,
    }
  }
}

const saveSolverSettings = async () => {
  isLoading.value = true
  message.value = 'ソルバー設定を保存中...'
  try {
    await axios.put(`/solver-settings/${selectedDepartment.value}/`, solverSettings.value)
    message.value = 'ソルバー設定が保存されました。'
  } catch (error) {
    message.value = 'ソルバー設定の保存に失敗しました。'
    console.error('Error saving solver settings:', error)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div>
    <h1>シフト自動生成</h1>
    <ShiftControlHeader
      :departments="departments"
      :selectedDepartment="selectedDepartment"
      @update:selectedDepartment="selectedDepartment = $event"
      :startDate="startDate"
      @update:startDate="startDate = $event"
      :endDate="endDate"
      @update:endDate="endDate = $event"
      :isLoading="isLoading"
      @generate-shifts="generateShifts"
      @confirm-selected-shifts="confirmSelectedShifts"
      @delete-selected-shifts="deleteSelectedShifts"
    />

    <p>{{ message }}</p>
    <hr />

    <div class="solver-settings-section">
      <h2>ソルバー設定</h2>
      <div class="pattern-controls">
        <label for="solverPatternSelect">保存されたパターン:</label>
        <select id="solverPatternSelect" v-model="selectedSolverPatternId" @change="loadSolverPattern">
          <option v-if="solverPatterns.length === 0" :value="null" disabled>パターンがありません</option>
          <option v-for="pattern in solverPatterns" :key="pattern.id" :value="pattern.id">
            {{ pattern.name }} {{ pattern.is_default ? '(デフォルト)' : '' }}
          </option>
        </select>
        <button @click="setDefaultPattern" :disabled="!selectedSolverPatternId || isLoading">デフォルトに設定</button>
      </div>

      <div class="settings-grid">
        <div v-for="(value, key) in solverSettings" :key="key" class="setting-item">
          <label :for="key">{{ settingDescriptions[key] || key }}</label>
          <input type="number" :id="key" v-model.number="solverSettings[key]" />
        </div>
      </div>
      <button @click="saveCurrentSolverSettings" :disabled="isLoading || !selectedSolverPatternId">現在の設定を更新</button>
      <div class="new-pattern-save">
        <input type="text" v-model="newPatternName" placeholder="新しいパターン名" :disabled="isLoading">
        <button @click="saveNewSolverPattern" :disabled="isLoading || !newPatternName.trim()">新しいパターンとして保存</button>
      </div>
    </div>
    <hr />

    <h2>生成結果</h2>
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
                  @change="toggleDaySelection(header.date)"
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
              <div>
                <input
                  type="checkbox"
                  :checked="isMemberSelected(member.id)"
                  @change="toggleMemberSelection(member.id)"
                  class="member-header-checkbox"
                />
                {{ member.name }}
              </div>
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
                @change="toggleCellSelection(member.id, header.date)"
                class="shift-checkbox"
              />

              <button
                v-if="scheduleGrid[member.id]?.[header.date]?.type === 'assigned' || scheduleGrid[member.id]?.[header.date]?.type === 'fixed'"
                @click="deleteShift(member.id, header.date)"
                class="delete-shift-btn"
              >
                ✖️
              </button>

              <select
                v-if="scheduleGrid[member.id] && scheduleGrid[member.id][header.date] && scheduleGrid[member.id][header.date].type !== 'leave' && scheduleGrid[member.id][header.date].type !== 'paid-leave'"
                :value="scheduleGrid[member.id][header.date].type === 'assigned' || scheduleGrid[member.id][header.date].type === 'fixed' ? scheduleGrid[member.id][header.date].patternId : scheduleGrid[member.id][header.date].type"
                @change="handleShiftChange(member.id, header.date, $event)"
              >
                <option 
                  :value="scheduleGrid[member.id][header.date].type === 'assigned' || scheduleGrid[member.id][header.date].type === 'fixed' ? scheduleGrid[member.id][header.date].patternId : scheduleGrid[member.id][header.date].type" 
                  selected disabled
                >
                  {{ scheduleGrid[member.id][header.date].text }}
                </option>
                <option v-if="scheduleGrid[member.id]?.[header.date]?.patternId" value="">（削除）</option>
                <option v-for="pattern in getAssignablePatternsForMember(member)" :key="pattern.id" :value="pattern.id">
                  {{ pattern.pattern_name }}
                </option>
                <option value="other">その他...</option>
                <option value="designated-holiday">指定休日</option>
                <option value="paid-leave">有給</option> <!-- Added -->
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
    <OtherAssignmentModal
      :show="isOtherAssignmentModalVisible"
      :member="selectedMemberForModal"
      :date="selectedDateForModal"
      @close="handleCloseModal"
      @save="handleSaveOtherAssignment"
    />
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
.member-header-checkbox {
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
td.designated-holiday {
  background-color: #e8daff;
  color: #581c87;
  font-weight: bold;
}
td.paid-leave { /* Added */
  background-color: #d4edda;
  color: #155724;
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

.solver-settings-section {
  margin-top: 20px;
  padding: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
  background-color: #f9f9f9;
}

.solver-settings-section h2 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.setting-item label {
  font-weight: bold;
  color: #555;
  font-size: 0.9em;
}

.setting-item input[type="number"] {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  width: 100%;
  box-sizing: border-box;
}

.pattern-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.pattern-controls select {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.pattern-controls button {
  padding: 8px 15px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 0.9em;
}

.pattern-controls button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.setting-item label {
  font-weight: bold;
  color: #555;
  font-size: 0.9em;
}

.setting-item input[type="number"] {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  width: 100%;
  box-sizing: border-box;
}

.new-pattern-save {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #eee;
}

.new-pattern-save input[type="text"] {
  flex-grow: 1;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.new-pattern-save button {
  padding: 8px 15px;
  background-color: #28a745; /* Green for save new */
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 0.9em;
}

.new-pattern-save button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.solver-settings-section > button { /* This targets the "Update current settings" button */
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 1em;
}

.solver-settings-section > button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}
</style>

