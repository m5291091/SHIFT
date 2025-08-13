from ortools.sat.python import cp_model
from .models import Member, ShiftPattern, LeaveRequest, TimeSlotRequirement, Assignment, DayGroup, RelationshipGroup, OtherAssignment
from .serializers import AssignmentSerializer
from datetime import date, timedelta, datetime, time
from collections import defaultdict

def generate_schedule(start_date_str, end_date_str):
    # --- 1. データ準備 ---
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)
    days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    all_members = Member.objects.all().prefetch_related('assignable_patterns', 'allowed_day_groups')
    all_patterns = ShiftPattern.objects.all()
    night_shift_pattern_ids = {p.id for p in all_patterns if p.is_night_shift}

    shift_work_minutes = {}
    for p in all_patterns:
        total_duration = (datetime.combine(date.today(), p.end_time) - datetime.combine(date.today(), p.start_time)).total_seconds() / 60
        if p.end_time < p.start_time:
            total_duration += 24 * 60
        work_minutes = total_duration - p.break_minutes
        shift_work_minutes[p.id] = int(work_minutes)

    day_difficulty = defaultdict(int)
    for req in LeaveRequest.objects.filter(status='approved', leave_date__range=[start_date, end_date]):
        day_difficulty[req.leave_date] += 1

    # --- 2. モデルと変数の定義 ---
    model = cp_model.CpModel()
    shifts = {}
    for m in all_members:
        for d in days:
            for p in all_patterns:
                shifts[(m.id, d, p.id)] = model.NewBoolVar(f'shift_m{m.id}_d{d}_p{p.id}')

    # --- 3. 目的関数とペナルティの準備 ---
    total_priority_score = []
    total_penalty_terms = []
    HEADCOUNT_PENALTY_COST = 100000
    DIFFICULTY_BONUS_WEIGHT = 10000

    for m in all_members:
        for d in days:
            for p in all_patterns:
                priority_reward = 100 - m.priority_score
                work_minutes = shift_work_minutes[p.id]
                difficulty_bonus = day_difficulty.get(d, 0) * DIFFICULTY_BONUS_WEIGHT
                score_term = (priority_reward * work_minutes) + difficulty_bonus
                total_priority_score.append(shifts[(m.id, d, p.id)] * score_term)

    # --- 4. 制約の追加 ---
    time_interval = 30
    slot_coverage = defaultdict(list)
    for m in all_members:
        for d in days:
            for p in all_patterns:
                p_start, p_end = p.start_time, p.end_time
                current_time = datetime.combine(d, p_start)
                end_time_dt = datetime.combine(d, p_end)
                if p_end < p_start: end_time_dt += timedelta(days=1)
                num_intervals = int(((end_time_dt - current_time).total_seconds() / 60) / time_interval)
                for i in range(num_intervals):
                    slot_start_dt = current_time + timedelta(minutes=i * time_interval)
                    if start_date <= slot_start_dt.date() <= end_date:
                        slot_coverage[(slot_start_dt.date(), slot_start_dt.time())].append((shifts[(m.id, d, p.id)], m.id))

    incompatible_groups = RelationshipGroup.objects.filter(rule_type='incompatible').prefetch_related('groupmember_set')
    for group in incompatible_groups:
        members_in_group_ids = {gm.member.id for gm in group.groupmember_set.all()}
        for slot_key, covering_shifts in slot_coverage.items():
            incompatible_shifts_in_slot = [s for s, member_id in covering_shifts if member_id in members_in_group_ids]
            if incompatible_shifts_in_slot:
                model.Add(sum(incompatible_shifts_in_slot) <= 1)

    # 時間帯別必要人数を「努力目標」として設定
    for d in days:
        day_name_field = f"is_{d.strftime('%A').lower()}"
        applicable_groups = DayGroup.objects.filter(**{day_name_field: True})
        if not applicable_groups.exists(): continue
        requirements = TimeSlotRequirement.objects.filter(day_group__in=applicable_groups)
        for t in range(0, 24 * 60, time_interval):
            current_slot_start = time(t // 60, t % 60)
            rule_for_slot = next((req for req in requirements if req.start_time <= current_slot_start and current_slot_start < req.end_time), None)
            if rule_for_slot:
                workers_in_slot = [s for s, member_id in slot_coverage.get((d, current_slot_start), [])]
                shortfall = model.NewIntVar(0, rule_for_slot.min_headcount, f'headcount_shortfall_d{d}_t{t}')
                model.Add(sum(workers_in_slot) + shortfall >= rule_for_slot.min_headcount)
                total_penalty_terms.append(shortfall * HEADCOUNT_PENALTY_COST)
                if rule_for_slot.max_headcount is not None:
                    model.Add(sum(workers_in_slot) <= rule_for_slot.max_headcount)
    
    # 他の絶対条件
    for req in LeaveRequest.objects.filter(status='approved', leave_date__range=[start_date, end_date]):
        for p in all_patterns:
            if (req.member.id, req.leave_date, p.id) in shifts:
                model.Add(shifts[(req.member.id, req.leave_date, p.id)] == 0)
    
    for m in all_members:
        assigned_pattern_ids = {p.id for p in m.assignable_patterns.all()}
        if assigned_pattern_ids:
            for p in all_patterns:
                if p.id not in assigned_pattern_ids:
                    for d in days:
                        model.Add(shifts[(m.id, d, p.id)] == 0)
        allowed_groups = m.allowed_day_groups.all()
        if allowed_groups.exists():
            allowed_weekdays = set()
            for group in allowed_groups:
                if group.is_monday: allowed_weekdays.add(0)
                if group.is_tuesday: allowed_weekdays.add(1)
                if group.is_wednesday: allowed_weekdays.add(2)
                if group.is_thursday: allowed_weekdays.add(3)
                if group.is_friday: allowed_weekdays.add(4)
                if group.is_saturday: allowed_weekdays.add(5)
                if group.is_sunday: allowed_weekdays.add(6)
            for d in days:
                if d.weekday() not in allowed_weekdays:
                    for p in all_patterns:
                        model.Add(shifts[(m.id, d, p.id)] == 0)

    MIN_REST_MINUTES = 8 * 60
    for m in all_members:
        for d_idx, d in enumerate(days):
            for p1 in all_patterns:
                end_time1 = datetime.combine(d, p1.end_time)
                if p1.end_time < p1.start_time:
                    end_time1 += timedelta(days=1)
                min_next_start_time = end_time1 + timedelta(minutes=MIN_REST_MINUTES)
                for next_d_idx in range(d_idx, min(d_idx + 2, len(days))):
                    next_d = days[next_d_idx]
                    for p2 in all_patterns:
                        if d == next_d and p1.id == p2.id: continue
                        start_time2 = datetime.combine(next_d, p2.start_time)
                        if start_time2 < min_next_start_time:
                            model.AddImplication(shifts[(m.id, d, p1.id)], shifts[(m.id, next_d, p2.id)].Not())
    
    for m in all_members:
        for d in days:
            model.Add(sum(shifts[(m.id, d, p.id)] for p in all_patterns) <= 1)
            daily_minutes = sum(shifts[(m.id, d, p.id)] * shift_work_minutes[p.id] for p in all_patterns)
            model.Add(daily_minutes <= m.max_hours_per_day * 60)
            
        work_days_in_period = []
        for d in days:
            is_working_day = model.NewBoolVar(f'is_working_m{m.id}_d{d}')
            model.Add(sum(shifts[(m.id, d, p.id)] for p in all_patterns) >= 1).OnlyEnforceIf(is_working_day)
            model.Add(sum(shifts[(m.id, d, p.id)] for p in all_patterns) == 0).OnlyEnforceIf(is_working_day.Not())
            work_days_in_period.append(is_working_day)
        
        num_days_in_period = len(days)
        total_work_days = sum(work_days_in_period)
        
        if m.employee_type == 'salaried':
            required_work_days = num_days_in_period - m.min_monthly_days_off
            if required_work_days >= 0:
                model.Add(total_work_days == required_work_days)
        else:
            max_work_days = num_days_in_period - m.min_monthly_days_off
            if max_work_days >= 0:
                model.Add(total_work_days <= max_work_days)

    # --- 5. 目的関数の設定 ---
    model.Maximize(sum(total_priority_score) - sum(total_penalty_terms))

    # --- 6. ソルバーの実行 & 結果の保存 ---
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        Assignment.objects.filter(shift_date__range=[start_date, end_date]).delete()
        new_assignments = []
        for m in all_members:
            for d in days:
                for p in all_patterns:
                    if (m.id, d, p.id) in shifts and solver.Value(shifts[(m.id, d, p.id)]) == 1:
                        new_assignments.append(Assignment(member_id=m.id, shift_pattern_id=p.id, shift_date=d))
        Assignment.objects.bulk_create(new_assignments)
        
        serializer = AssignmentSerializer(new_assignments, many=True)
        return {'success': True, 'infeasible_days': [], 'assignments': serializer.data}
    
    return {'success': False, 'infeasible_days': [], 'assignments': []}