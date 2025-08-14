from django.db import models

class Member(models.Model):
    EMPLOYEE_TYPE_CHOICES = [
        ('hourly', '時給制'),
        ('salaried', '固定給'),
    ]
    
    name = models.CharField("氏名", max_length=100)
    employee_type = models.CharField("雇用形態", max_length=10, choices=EMPLOYEE_TYPE_CHOICES, default='hourly')
    hourly_wage = models.IntegerField("時給", null=True, blank=True, help_text="時給制の場合のみ入力")
    monthly_salary = models.IntegerField("月給", null=True, blank=True, help_text="固定給の場合のみ入力")
    
    min_monthly_salary = models.IntegerField("月の最低給与目標", null=True, blank=True, help_text="時給制メンバーの目標額")
    max_monthly_salary = models.IntegerField("月の最高給与目標", null=True, blank=True, help_text="時給制メンバーの目標額")
    max_annual_salary = models.IntegerField("年間の最大給与額", null=True, blank=True, help_text="例: 1030000")
    current_annual_salary = models.IntegerField("現在の年間給与累計額", default=0, help_text="管理者が手動で更新します")
    salary_year_start_month = models.IntegerField("給与年の開始月", default=12, help_text="例: 12月始まりの場合「12」")

    max_hours_per_day = models.IntegerField("1日の最大労働時間", default=8)
    min_days_off_per_week = models.IntegerField("週の最低休日数", default=2)
    min_monthly_days_off = models.IntegerField("月の最低公休日数", default=8)
    enforce_exact_holidays = models.BooleanField("休日数を固定する", default=False, help_text="オンの場合、月の公休日数が設定通りに固定されます")
    
    priority_score = models.IntegerField("割り当て優先度", default=10)
    sort_order = models.IntegerField("表示順", default=99, help_text="数値が小さいほど上に表示されます")
    
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    assignable_patterns = models.ManyToManyField(
        'ShiftPattern',
        verbose_name="担当可能なシフト",
        blank=True,
        help_text="空の場合、全てのシフトパターンが担当可能と見なされます"
    )
    allowed_day_groups = models.ManyToManyField(
        'DayGroup',
        verbose_name="勤務可能な曜日グループ",
        blank=True,
        related_name="allowed_members"
    )

    class Meta:
        verbose_name = "従業員"
        verbose_name_plural = "従業員"

    def __str__(self):
        return self.name

class ShiftPattern(models.Model):
    pattern_name = models.CharField("パターン名", max_length=100)
    start_time = models.TimeField("開始時刻")
    end_time = models.TimeField("終了時刻")
    break_minutes = models.IntegerField("休憩時間(分)", default=60)
    is_night_shift = models.BooleanField("夜勤シフト", default=False, help_text="このシフトが夜勤の場合にチェック")
    min_headcount = models.IntegerField("このシフトの最低人数", default=0, help_text="0の場合は無制限")
    max_headcount = models.IntegerField("このシフトの最高人数", null=True, blank=True, help_text="空欄の場合は無制限")

    class Meta:
        verbose_name = "シフトパターン"
        verbose_name_plural = "シフトパターン"

    def __str__(self):
        return f"{self.pattern_name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

class DayGroup(models.Model):
    group_name = models.CharField("グループ名", max_length=100, unique=True)
    is_monday = models.BooleanField("月", default=False)
    is_tuesday = models.BooleanField("火", default=False)
    is_wednesday = models.BooleanField("水", default=False)
    is_thursday = models.BooleanField("木", default=False)
    is_friday = models.BooleanField("金", default=False)
    is_saturday = models.BooleanField("土", default=False)
    is_sunday = models.BooleanField("日", default=False)

    class Meta:
        verbose_name = "曜日グループ"
        verbose_name_plural = "曜日グループ"

    def __str__(self):
        return self.group_name

class TimeSlotRequirement(models.Model):
    day_group = models.ForeignKey(DayGroup, on_delete=models.CASCADE, verbose_name="曜日グループ")
    start_time = models.TimeField("開始時刻")
    end_time = models.TimeField("終了時刻")
    min_headcount = models.IntegerField("最低必要人数")
    max_headcount = models.IntegerField("最大必要人数", null=True, blank=True, help_text="空欄の場合は上限なし")

    class Meta:
        verbose_name = "時間帯別必要人数"
        verbose_name_plural = "時間帯別必要人数"

    def __str__(self):
        return f"{self.day_group.group_name} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}): {self.min_headcount}人"

class MemberAvailability(models.Model):
    DAY_CHOICES = [
        (0, '月曜日'), (1, '火曜日'), (2, '水曜日'), (3, '木曜日'),
        (4, '金曜日'), (5, '土曜日'), (6, '日曜日')
    ]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    day_of_week = models.IntegerField("曜日", choices=DAY_CHOICES)
    start_time = models.TimeField("勤務可能開始時刻")
    end_time = models.TimeField("勤務可能終了時刻")
    
    class Meta:
        verbose_name = "勤務可能条件"
        verbose_name_plural = "勤務可能条件"

    def __str__(self):
        return f"{self.member.name} - {self.get_day_of_week_display()}"

class LeaveRequest(models.Model):
    STATUS_CHOICES = [('approved', '承認'), ('pending', '申請中')]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    leave_date = models.DateField("希望休の日付")
    status = models.CharField("状態", max_length=50, choices=STATUS_CHOICES, default='pending')
    
    class Meta:
        verbose_name = "希望休"
        verbose_name_plural = "希望休登録"

    def __str__(self):
        return f"{self.member.name} - {self.leave_date}"

class RelationshipGroup(models.Model):
    RULE_CHOICES = [('incompatible', '非互換'), ('pairing', 'ペアリング')]
    group_name = models.CharField("グループ名", max_length=100)
    rule_type = models.CharField("ルールの種類", max_length=50, choices=RULE_CHOICES)
    
    class Meta:
        verbose_name = "関係性グループ"
        verbose_name_plural = "関係性グループ"

    def __str__(self):
        return self.group_name

class GroupMember(models.Model):
    group = models.ForeignKey(RelationshipGroup, on_delete=models.CASCADE, verbose_name="グループ")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    
    class Meta:
        verbose_name = "グループ所属メンバー"
        verbose_name_plural = "グループ所属メンバー"

    def __str__(self):
        return f"{self.group.group_name} - {self.member.name}"

class Assignment(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    shift_pattern = models.ForeignKey(ShiftPattern, on_delete=models.CASCADE, verbose_name="シフトパターン")
    shift_date = models.DateField("勤務日")
    
    class Meta:
        verbose_name = "確定シフト"
        verbose_name_plural = "確定シフト"

    def __str__(self):
        return f"{self.shift_date} {self.member.name} ({self.shift_pattern.pattern_name})"

class OtherAssignment(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    shift_date = models.DateField("勤務日")
    activity_name = models.CharField("業務内容", max_length=100)

    class Meta:
        verbose_name = "その他の割り当て"
        verbose_name_plural = "その他の割り当て"
        unique_together = ('member', 'shift_date')

    def __str__(self):
        return f"{self.shift_date} {self.member.name}: {self.activity_name}"

class Skill(models.Model):
    skill_name = models.CharField("スキル名", max_length=100, unique=True)
    
    class Meta:
        verbose_name = "スキル"
        verbose_name_plural = "スキル"

    def __str__(self):
        return self.skill_name

class MemberSkill(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, verbose_name="スキル")

    class Meta:
        verbose_name = "保有スキル"
        verbose_name_plural = "保有スキル"

    def __str__(self):
        return f"{self.member.name}: {self.skill.skill_name}"

class FixedAssignment(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    shift_pattern = models.ForeignKey(ShiftPattern, on_delete=models.CASCADE, verbose_name="シフトパターン")
    shift_date = models.DateField("勤務日")

    class Meta:
        verbose_name = "固定シフト"
        verbose_name_plural = "固定シフト"
        unique_together = ('member', 'shift_date')

    def __str__(self):
        return f"{self.shift_date} {self.member.name} ({self.shift_pattern.pattern_name})"
