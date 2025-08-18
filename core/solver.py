from ortools.sat.python import cp_model
from .models import (
    Member, ShiftPattern, LeaveRequest, TimeSlotRequirement, Assignment, DayGroup, 
    RelationshipGroup, OtherAssignment, FixedAssignment, SpecificDateRequirement, 
    SpecificTimeSlotRequirement, MemberShiftPatternPreference, DesignatedHoliday,
    SolverSettings, PaidLeave # Added SolverSettings, PaidLeave
)
from .serializers import AssignmentSerializer
from datetime import date, timedelta, datetime, time
from collections import defaultdict
import itertools

def generate_schedule(department_id, start_date_str, end_date_str):
    # --- 1. データ準備 ---
    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    # Fetch solver settings for the department
    try:
        settings = SolverSettings.objects.get(department_id=department_id, is_default=True)
    except SolverSettings.DoesNotExist:
        # If no default settings exist for this department, create one and set it as default
        # Also, ensure any existing settings are not marked as default
        SolverSettings.objects.filter(department_id=department_id).update(is_default=False)
        settings = SolverSettings.objects.create(
            department_id=department_id,
            name="Default Pattern", # Assign a default name
            is_default=True
        )
    except SolverSettings.MultipleObjectsReturned:
        # This should ideally not happen if is_default is properly managed.
        # If it does, pick the first one and ensure only one is default.
        default_settings = SolverSettings.objects.filter(department_id=department_id, is_default=True)
        if default_settings.count() > 1:
            # Set all but the first one to not default
            for s in default_settings[1:]:
                s.is_default = False
                s.save()
        settings = default_settings.first()
    days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    all_members = Member.objects.filter(department_id=department_id).prefetch_related('shift_preferences', 'allowed_day_groups')
    all_patterns = ShiftPattern.objects.filter(department_id=department_id)
    fixed_assignments = FixedAssignment.objects.filter(shift_date__range=[start_date, end_date], member__department_id=department_id).select_related('shift_pattern', 'member')
    other_assignments = OtherAssignment.objects.filter(shift_date__range=[start_date, end_date], member__department_id=department_id).select_related('member')
    designated_holidays = DesignatedHoliday.objects.filter(date__range=[start_date, end_date], member__department_id=department_id)
    specific_date_reqs = SpecificDateRequirement.objects.filter(date__range=[start_date, end_date], department_id=department_id)
    specific_timeslot_reqs = SpecificTimeSlotRequirement.objects.filter(date__range=[start_date, end_date], department_id=department_id)
    prefs = MemberShiftPatternPreference.objects.filter(member__department_id=department_id)
    priority_map = {(p.member_id, p.shift_pattern.id): p.priority for p in prefs}
    time_interval = 30

    # 特定日の設定がある日付をセットとして保持
    dates_with_specific_reqs = {req.date for req in specific_date_reqs} | {req.date for req in specific_timeslot_reqs}

    # 固定シフト・その他シフトがある従業員と日付のセットを事前に計算
    fixed_slot_coverage = defaultdict(int)
    pre_assigned_days = set()
    for fa in fixed_assignments:
        pre_assigned_days.add((fa.member.id, fa.shift_date))
        p_start, p_end = fa.shift_pattern.start_time, fa.shift_pattern.end_time
        current_time = datetime.combine(fa.shift_date, p_start)
        end_time_dt = datetime.combine(fa.shift_date, p_end)
        if p_end < p_start:
            end_time_dt += timedelta(days=1)
        num_intervals = int(((end_time_dt - current_time).total_seconds() / 60) / time_interval)
        for i in range(num_intervals):
            slot_start_dt = current_time + timedelta(minutes=i * time_interval)
            if start_date <= slot_start_dt.date() <= end_date:
                fixed_slot_coverage[(slot_start_dt.date(), slot_start_dt.time())] += 1
    for oa in other_assignments:
        pre_assigned_days.add((oa.member.id, oa.shift_date))

    shift_work_minutes = {}
    for p in all_patterns:
        total_duration = (datetime.combine(date.today(), p.end_time) - datetime.combine(date.today(), p.start_time)).total_seconds() / 60
        if p.end_time < p.start_time:
            total_duration += 24 * 60
        work_minutes = total_duration - p.break_minutes
        shift_work_minutes[p.id] = int(work_minutes)

    day_difficulty = defaultdict(int)
    leave_requests_map = defaultdict(set)
    for req in LeaveRequest.objects.filter(status='approved', leave_date__range=[start_date, end_date], member__department_id=department_id):
        day_difficulty[req.leave_date] += 1
        leave_requests_map[req.member.id].add(req.leave_date)

    # --- 2. モデルと変数の定義 ---
    model = cp_model.CpModel()
    shifts = {}
    shortfall_vars = {}
    actual_workers_in_slot_vars = {}
    work_day_surplus_vars = {}
    incompatible_violation_vars = {}
    unavailable_day_violation_vars = {}
    salary_shortfall_vars = {}
    salary_surplus_vars = {}
    consecutive_violation_vars = {}

    for m in all_members:
        for d in days:
            for p in all_patterns:
                shifts[(m.id, d, p.id)] = model.NewBoolVar(f'shift_m{m.id}_d{d}_p{p.id}')

    # --- 3. 目的関数とペナルティの準備 ---
    total_priority_score = []
    total_penalty_terms = []
    HEADCOUNT_PENALTY_COST = settings.headcount_penalty_cost
    HOLIDAY_VIOLATION_PENALTY = settings.holiday_violation_penalty
    INCOMPATIBLE_PENALTY = settings.incompatible_penalty
    CONSECUTIVE_WORK_VIOLATION_PENALTY = settings.consecutive_work_violation_penalty
    SALARY_TOO_LOW_PENALTY = settings.salary_too_low_penalty
    SALARY_TOO_HIGH_PENALTY = settings.salary_too_high_penalty
    DIFFICULTY_BONUS_WEIGHT = settings.difficulty_bonus_weight
    WORK_DAY_DEVIATION_PENALTY = settings.work_day_deviation_penalty
    PAIRING_BONUS = settings.pairing_bonus
    SHIFT_PREFERENCE_BONUS = settings.shift_preference_bonus
    UNAVAILABLE_DAY_PENALTY = settings.unavailable_day_penalty # This was not a constant before, now it is.

    for m in all_members:
        num_possible_shifts = 0
        allowed_patterns = {p.id for p in m.shift_preferences.all()}
        allowed_groups = m.allowed_day_groups.all()
        allowed_weekdays = set()
        if allowed_groups.exists():
            for group in allowed_groups:
                if group.is_monday: allowed_weekdays.add(0)
                if group.is_tuesday: allowed_weekdays.add(1)
                if group.is_wednesday: allowed_weekdays.add(2)
                if group.is_thursday: allowed_weekdays.add(3)
                if group.is_friday: allowed_weekdays.add(4)
                if group.is_saturday: allowed_weekdays.add(5)
                if group.is_sunday: allowed_weekdays.add(6)
        
        for d in days:
            if d in leave_requests_map.get(m.id, set()): continue
            
            is_unavailable_day_violation = model.NewBoolVar(f'unavailable_day_violation_m{m.id}_d{d}')
            unavailable_day_violation_vars[(m.id, d)] = is_unavailable_day_violation
            if allowed_groups.exists() and d.weekday() not in allowed_weekdays:
                model.Add(sum(shifts.get((m.id, d, p.id), 0) for p in all_patterns) == 0).OnlyEnforceIf(is_unavailable_day_violation.Not())
                total_penalty_terms.append(is_unavailable_day_violation * UNAVAILABLE_DAY_PENALTY)
            else:
                # If no violation, ensure the violation variable is false
                model.Add(is_unavailable_day_violation == 0)

            for p in all_patterns:
                if allowed_patterns and p.id not in allowed_patterns: continue
                num_possible_shifts += 1
        
        priority_reward = (10000 // (num_possible_shifts + 1)) * (100 - m.priority_score)
        for d in days:
            for p in all_patterns:
                score_term = priority_reward + day_difficulty.get(d, 0) * DIFFICULTY_BONUS_WEIGHT
                pattern_priority = priority_map.get((m.id, p.id), 100)
                priority_bonus = (100 - pattern_priority) * SHIFT_PREFERENCE_BONUS
                score_term += priority_bonus
                total_priority_score.append(shifts[(m.id, d, p.id)] * score_term)

    # ペアリングのボーナス項
    pairing_groups = RelationshipGroup.objects.filter(rule_type='pairing').prefetch_related('groupmember_set__member')
    for group in pairing_groups:
        members_in_group = [gm.member for gm in group.groupmember_set.all()]
        for m1, m2 in itertools.combinations(members_in_group, 2):
            for d in days:
                for p in all_patterns:
                    is_paired = model.NewBoolVar(f'paired_m{m1.id}_m{m2.id}_d{d}_p{p.id}')
                    model.AddBoolAnd([shifts[(m1.id, d, p.id)], shifts[(m2.id, d, p.id)]]).OnlyEnforceIf(is_paired)
                    model.AddImplication(is_paired, shifts[(m1.id, d, p.id)])
                    model.AddImplication(is_paired, shifts[(m2.id, d, p.id)])
                    total_priority_score.append(is_paired * PAIRING_BONUS)

    work_days_per_member = []
    for m in all_members:
        work_days = []
        for d in days:
            is_working_day = model.NewBoolVar(f'is_working_for_fairness_m{m.id}_d{d}')
            model.Add(sum(shifts.get((m.id, d, p.id), 0) for p in all_patterns) >= 1).OnlyEnforceIf(is_working_day)
            model.Add(sum(shifts.get((m.id, d, p.id), 0) for p in all_patterns) == 0).OnlyEnforceIf(is_working_day.Not())
            work_days.append(is_working_day)
        work_days_per_member.append(sum(work_days))
    
    if len(work_days_per_member) > 1:
        total_work_days_all_members = sum(work_days_per_member)
        for i, work_days_sum in enumerate(work_days_per_member):
            member_id = all_members[i].id
            deviation = model.NewIntVar(-len(days) * len(all_members), len(days) * len(all_members), f'deviation_m_{member_id}')
            model.Add(len(all_members) * work_days_sum - total_work_days_all_members == deviation)
            abs_deviation = model.NewIntVar(0, len(days) * len(all_members), f'abs_deviation_m_{member_id}')
            model.AddAbsEquality(abs_deviation, deviation)
            total_penalty_terms.append(abs_deviation * WORK_DAY_DEVIATION_PENALTY)

    # --- 4. 制約の追加 ---
    # 固定シフト・その他シフトの制約
    for fa in fixed_assignments:
        model.Add(shifts[(fa.member.id, fa.shift_date, fa.shift_pattern.id)] == 1)
    for oa in other_assignments:
        for p in all_patterns:
            if (oa.member.id, oa.shift_date, p.id) in shifts:
                model.Add(shifts[(oa.member.id, oa.shift_date, p.id)] == 0)

    # 特定日・シフトパターンごとの必要人数制約
    for req in specific_date_reqs:
        workers_in_pattern = sum(shifts[(m.id, req.date, req.shift_pattern.id)] for m in all_members)
        model.Add(workers_in_pattern >= req.min_headcount)
        if req.max_headcount is not None:
            model.Add(workers_in_pattern <= req.max_headcount)

    # 担当可能でないシフトには割り当てない制約
    for m in all_members:
        assigned_pattern_ids = {p.id for p in m.shift_preferences.all()}
        if assigned_pattern_ids:
            for p in all_patterns:
                if p.id not in assigned_pattern_ids:
                    for d in days:
                        model.Add(shifts[(m.id, d, p.id)] == 0)

    # 各シフトパターンの最高人数制約
    for d in days:
        for p in all_patterns:
            if p.max_headcount is not None:
                workers_in_pattern_on_day = sum(shifts[(m.id, d, p.id)] for m in all_members)
                model.Add(workers_in_pattern_on_day <= p.max_headcount)

    slot_coverage = defaultdict(list)
    for m in all_members:
        for d in days:
            if (m.id, d) in pre_assigned_days:
                continue
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
                incompatible_violation = model.NewIntVar(0, len(incompatible_shifts_in_slot), f'incompatible_violation_d{slot_key[0]}_t{slot_key[1]}')
                incompatible_violation_vars[slot_key] = incompatible_violation
                model.Add(sum(incompatible_shifts_in_slot) <= 1 + incompatible_violation)
                total_penalty_terms.append(incompatible_violation * INCOMPATIBLE_PENALTY)

    # 必要人数の制約 (曜日グループ or 特定日)
    for d in days:
        if d in dates_with_specific_reqs:
            day_specific_reqs = [req for req in specific_timeslot_reqs if req.date == d]
            if day_specific_reqs:
                for t in range(0, 24 * 60, time_interval):
                    current_slot_start = time(t // 60, t % 60)
                    rule_for_slot = next((req for req in day_specific_reqs if req.start_time <= current_slot_start and current_slot_start < req.end_time), None)
                    if rule_for_slot:
                        variable_workers_in_slot = [s for s, m_id in slot_coverage.get((d, current_slot_start), [])]
                        fixed_workers_in_slot = fixed_slot_coverage.get((d, current_slot_start), 0)
                        total_workers_expr = sum(variable_workers_in_slot) + fixed_workers_in_slot
                        actual_workers_in_slot = model.NewIntVar(0, len(all_members), f'actual_workers_d{d}_t{t}')
                        actual_workers_in_slot_vars[(d, t)] = actual_workers_in_slot
                        model.Add(actual_workers_in_slot == total_workers_expr)
                        shortfall = model.NewIntVar(0, rule_for_slot.min_headcount, f'headcount_shortfall_d{d}_t{t}')
                        shortfall_vars[(d, t)] = shortfall
                        model.Add(total_workers_expr + shortfall >= rule_for_slot.min_headcount)
                        total_penalty_terms.append(shortfall * HEADCOUNT_PENALTY_COST)
                        if rule_for_slot.max_headcount is not None:
                            model.Add(actual_workers_in_slot <= rule_for_slot.max_headcount)
                        else:
                            raise ValueError(f"max_headcount is None for rule {rule_for_slot.id} at {d} {current_slot_start}")
        else:
            day_name_field = f"is_{d.strftime('%A').lower()}"
            applicable_groups = DayGroup.objects.filter(**{day_name_field: True})
            if not applicable_groups.exists(): continue
            requirements = TimeSlotRequirement.objects.filter(day_group__in=applicable_groups, department_id=department_id)
            for t in range(0, 24 * 60, time_interval):
                current_slot_start = time(t // 60, t % 60)
                rule_for_slot = next((req for req in requirements if req.start_time <= current_slot_start and current_slot_start < req.end_time), None)
                if rule_for_slot:
                    variable_workers_in_slot = [s for s, m_id in slot_coverage.get((d, current_slot_start), [])]
                    fixed_workers_in_slot = fixed_slot_coverage.get((d, current_slot_start), 0)
                    total_workers_expr = sum(variable_workers_in_slot) + fixed_workers_in_slot
                    actual_workers_in_slot = model.NewIntVar(0, len(all_members), f'actual_workers_d{d}_t{t}')
                    actual_workers_in_slot_vars[(d, t)] = actual_workers_in_slot
                    model.Add(actual_workers_in_slot == total_workers_expr)
                    shortfall = model.NewIntVar(0, rule_for_slot.min_headcount, f'headcount_shortfall_d{d}_t{t}')
                    shortfall_vars[(d, t)] = shortfall
                    model.Add(total_workers_expr + shortfall >= rule_for_slot.min_headcount)
                    total_penalty_terms.append(shortfall * HEADCOUNT_PENALTY_COST)
                    if rule_for_slot.max_headcount is not None:
                        model.Add(actual_workers_in_slot <= rule_for_slot.max_headcount)
                    else:
                        raise ValueError(f"max_headcount is None for rule {rule_for_slot.id} at {d} {current_slot_start}")
    
    for req in LeaveRequest.objects.filter(status='approved', leave_date__range=[start_date, end_date], member__department_id=department_id):
        for p in all_patterns:
            if (req.member.id, req.leave_date, p.id) in shifts:
                model.Add(shifts[(req.member.id, req.leave_date, p.id)] == 0)

    for dh in designated_holidays:
        for p in all_patterns:
            if (dh.member.id, dh.date, p.id) in shifts:
                model.Add(shifts[(dh.member.id, dh.date, p.id)] == 0)

    # Constraint for PaidLeave: No shifts on paid leave days
    paid_leaves = PaidLeave.objects.filter(date__range=[start_date, end_date], member__department_id=department_id)
    for pl in paid_leaves:
        for p in all_patterns:
            if (pl.member.id, pl.date, p.id) in shifts:
                model.Add(shifts[(pl.member.id, pl.date, p.id)] == 0)
    
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
        total_work_days_sum = sum(work_days_in_period)
        max_work_days = num_days_in_period - m.min_monthly_days_off

        if max_work_days >= 0:
            work_day_surplus = model.NewIntVar(0, num_days_in_period, f'work_day_surplus_m{m.id}')
            work_day_surplus_vars[m.id] = work_day_surplus
            model.Add(total_work_days_sum <= max_work_days + work_day_surplus)
            total_penalty_terms.append(work_day_surplus * HOLIDAY_VIOLATION_PENALTY * (1000 if m.enforce_exact_holidays else 1))

        # Consecutive work days constraint
        if m.max_consecutive_work_days is not None and m.max_consecutive_work_days > 0:
            for i in range(len(days) - m.max_consecutive_work_days):
                window = work_days_in_period[i:i + m.max_consecutive_work_days + 1]
                surplus = model.NewIntVar(0, 1, f'consecutive_surplus_m{m.id}_d{i}')
                model.Add(sum(window) <= m.max_consecutive_work_days + surplus)
                total_penalty_terms.append(surplus * CONSECUTIVE_WORK_VIOLATION_PENALTY)
                consecutive_violation_vars[(m.id, days[i])] = surplus

        # Salary-based penalties
        if m.employee_type == 'hourly' and m.hourly_wage is not None:
            total_earnings = model.NewIntVar(0, 10000000, f'total_earnings_m{m.id}') # Max earnings for a month
            model.Add(total_earnings == sum(shifts[(m.id, d, p.id)] * ((shift_work_minutes[p.id] * m.hourly_wage) // 60) for d in days for p in all_patterns))

            if m.min_monthly_salary is not None:
                salary_shortfall = model.NewIntVar(0, m.min_monthly_salary, f'salary_shortfall_m{m.id}')
                salary_shortfall_vars[m.id] = salary_shortfall
                model.Add(total_earnings + salary_shortfall >= m.min_monthly_salary)
                total_penalty_terms.append(salary_shortfall * SALARY_TOO_LOW_PENALTY)

            if m.max_monthly_salary is not None:
                salary_surplus = model.NewIntVar(0, 10000000, f'salary_surplus_m{m.id}') # Max earnings for a month
                salary_surplus_vars[m.id] = salary_surplus
                model.Add(total_earnings <= m.max_monthly_salary + salary_surplus)
                total_penalty_terms.append(salary_surplus * SALARY_TOO_HIGH_PENALTY)

    # --- 5. 目的関数の設定 ---
    model.Maximize(sum(total_priority_score) - sum(total_penalty_terms))

    # --- 6. ソルバーの実行 & 結果の保存 ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        Assignment.objects.filter(shift_date__range=[start_date, end_date], member__department_id=department_id).delete()
        new_assignments = []
        for m in all_members:
            for d in days:
                for p in all_patterns:
                    if (m.id, d, p.id) in shifts and solver.Value(shifts[(m.id, d, p.id)]) == 1:
                        new_assignments.append(Assignment(member_id=m.id, shift_pattern_id=p.id, shift_date=d))
        Assignment.objects.bulk_create(new_assignments)
        
        infeasible_days_info = defaultdict(list)

        # 1. Headcount Shortfall/Surplus
        for (d, t), var in shortfall_vars.items():
            if solver.Value(var) > 0:
                infeasible_days_info[str(d)].append(f'時間帯 {time(t // 60, t % 60).strftime('%H:%M')} に {solver.Value(var)} 人の不足')
        
        # Check for hard constraint violation of max_headcount (should not happen if model is correct)
        for (d, t), var in actual_workers_in_slot_vars.items():
            # Find the rule for this slot to get max_headcount
            rule_for_slot = None
            if d in dates_with_specific_reqs:
                day_specific_reqs = [req for req in specific_timeslot_reqs if req.date == d]
                rule_for_slot = next((req for req in day_specific_reqs if req.start_time <= time(t // 60, t % 60) and time(t // 60, t % 60) < req.end_time), None)
            else:
                day_name_field = f"is_{d.strftime('%A').lower()}"
                applicable_groups = DayGroup.objects.filter(**{day_name_field: True})
                if applicable_groups.exists():
                    requirements = TimeSlotRequirement.objects.filter(day_group__in=applicable_groups, department_id=department_id)
                    rule_for_slot = next((req for req in requirements if req.start_time <= time(t // 60, t % 60) and time(t // 60, t % 60) < req.end_time), None)

            if rule_for_slot and rule_for_slot.max_headcount is not None:
                if solver.Value(var) > rule_for_slot.max_headcount:
                    infeasible_days_info[str(d)].append(f'時間帯 {time(t // 60, t % 60).strftime('%H:%M')} に最高人数 ({rule_for_slot.max_headcount}人) を {solver.Value(var) - rule_for_slot.max_headcount} 人超過 (ハード制約違反)')

        # 2. Holiday Violation
        for member_id, var in work_day_surplus_vars.items():
            if solver.Value(var) > 0:
                member_name = next((m.name for m in all_members if m.id == member_id), f'Member {member_id}')
                infeasible_days_info[str(start_date)].append(f'{member_name} が最低休日数を {solver.Value(var)} 日下回りました') # Link to start_date of period

        # 3. Incompatible Members
        for (d, t), var in incompatible_violation_vars.items():
            if solver.Value(var) > 0:
                infeasible_days_info[str(d)].append(f'時間帯 {time(t // 60, t % 60).strftime('%H:%M')} に相性の悪いメンバーが {solver.Value(var)} 組勤務')

        # 4. Unavailable Day Assignment
        for (member_id, d), var in unavailable_day_violation_vars.items():
            if solver.Value(var) == 1:
                member_name = next((m.name for m in all_members if m.id == member_id), f'Member {member_id}')
                infeasible_days_info[str(d)].append(f'{member_name} が勤務不可曜日に割り当てられました')

        # 5. Salary Violations
        for member_id, var in salary_shortfall_vars.items():
            if solver.Value(var) > 0:
                member_name = next((m.name for m in all_members if m.id == member_id), f'Member {member_id}')
                infeasible_days_info[str(start_date)].append(f'{member_name} の給与が目標最低額を {solver.Value(var)} 円下回りました')
        for member_id, var in salary_surplus_vars.items():
            if solver.Value(var) > 0:
                member_name = next((m.name for m in all_members if m.id == member_id), f'Member {member_id}')
                infeasible_days_info[str(start_date)].append(f'{member_name} の給与が目標最高額を {solver.Value(var)} 円上回りました')

        # 6. Consecutive Work Violations
        for (member_id, start_day_of_window), var in consecutive_violation_vars.items():
            if solver.Value(var) > 0:
                member = next((m for m in all_members if m.id == member_id), None)
                if member:
                    infeasible_days_info[str(start_day_of_window)].append(
                        f'{member.name} が連続勤務数上限 ({member.max_consecutive_work_days}日) を超過しました。'
                    )

        serializer = AssignmentSerializer(new_assignments, many=True)
        return {'success': True, 'infeasible_days': dict(infeasible_days_info), 'assignments': serializer.data}
    
    return {'success': False, 'infeasible_days': {'general': ['指定された期間でシフトを生成できませんでした。制約が厳しすぎるか、人員が不足している可能性があります。']}, 'assignments': []}