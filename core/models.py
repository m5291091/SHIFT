from django.db import models

# 曜日グループを定義するモデル
class DayGroup(models.Model):
    group_name = models.CharField("グループ名", max_length=100, unique=True)
    is_monday = models.BooleanField("月", default=False)
    is_tuesday = models.BooleanField("火", default=False)
    is_wednesday = models.BooleanField("水", default=False)
    is_thursday = models.BooleanField("木", default=False)
    is_friday = models.BooleanField("金", default=False)
    is_saturday = models.BooleanField("土", default=False)
    is_sunday = models.BooleanField("日", default=False)

    def __str__(self):
        return self.group_name

class ShiftPattern(models.Model):
    pattern_name = models.CharField("パターン名", max_length=100)
    start_time = models.TimeField("開始時刻")
    end_time = models.TimeField("終了時刻")
    break_minutes = models.IntegerField("休憩時間(分)", default=60) # この行を追加
    is_night_shift = models.BooleanField("夜勤シフト", default=False, help_text="このシフトが夜勤の場合にチェック")
    
    class Meta:
        verbose_name = "シフトパターン"
        verbose_name_plural = "シフトパターン"

    def __str__(self):
        return f"{self.pattern_name} ({self.start_time} - {self.end_time})"
    
# 1. 従業員マスター
class Member(models.Model):
    EMPLOYEE_TYPE_CHOICES = [
        ('hourly', '時給制'),
        ('salaried', '固定給'),
    ]
    
    # --- フィールド定義 ---
    name = models.CharField("氏名", max_length=100)
    employee_type = models.CharField(
        "雇用形態",
        max_length=10,
        choices=EMPLOYEE_TYPE_CHOICES,
        default='hourly'
    )
    hourly_wage = models.IntegerField("時給", null=True, blank=True, help_text="時給制の場合のみ入力")
    monthly_salary = models.IntegerField("月給", null=True, blank=True, help_text="固定給の場合のみ入力")
    min_monthly_salary = models.IntegerField("月の最低給与目標", null=True, blank=True, help_text="時給制メンバーの目標額")
    max_monthly_salary = models.IntegerField("月の最高給与目標", null=True, blank=True, help_text="時給制メンバーの目標額")
    max_annual_salary = models.IntegerField("年間の最大給与額", null=True, blank=True, help_text="例: 1030000")
    current_annual_salary = models.IntegerField("現在の年間給与累計額", default=0, help_text="管理者が手動で更新します")
    salary_year_start_month = models.IntegerField("給与年の開始月", default=12, help_text="例: 12月始まりの場合「12」")

    allowed_day_groups = models.ManyToManyField(
        DayGroup,
        verbose_name="勤務可能な曜日グループ",
        blank=True,
        related_name="allowed_members" # 関連名を指定
    )

    assignable_patterns = models.ManyToManyField(
        ShiftPattern,
        verbose_name="担当可能なシフト",
        blank=True,
        help_text="空の場合、全てのシフトパターンが担当可能と見なされます"
    )

    # --- 労働時間制約 ---
    max_hours_per_day = models.IntegerField("1日の最大労働時間", default=8)
    #min_hours_per_week = models.IntegerField("週の最低労働時間", default=0)
    #max_hours_per_week = models.IntegerField("週の最大労働時間", default=40)
    min_days_off_per_week = models.IntegerField("週の最低休日数", default=2)
    min_monthly_days_off = models.IntegerField("月の最低公休日数", default=8) # この行を追加

    
    # --- その他 ---
    priority_score = models.IntegerField("割り当て優先度", default=10)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "従業員"
        verbose_name_plural = "従業員"

    def __str__(self):
        return self.name

# 2. スキルマスター
class Skill(models.Model):
    skill_name = models.CharField("スキル名", max_length=100, unique=True)

    def __str__(self):
        return self.skill_name

# 3. 従業員の保有スキル (中間テーブル)
class MemberSkill(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, verbose_name="スキル")

    def __str__(self):
        return f"{self.member.name}: {self.skill.skill_name}"


# 5. 従業員の勤務可能条件
class MemberAvailability(models.Model):
    DAY_CHOICES = [
        (0, '日曜日'), (1, '月曜日'), (2, '火曜日'), (3, '水曜日'),
        (4, '木曜日'), (5, '金曜日'), (6, '土曜日')
    ]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    day_of_week = models.IntegerField("曜日", choices=DAY_CHOICES)
    start_time = models.TimeField("勤務可能開始時刻")
    end_time = models.TimeField("勤務可能終了時刻")

    def __str__(self):
        return f"{self.member.name} - {self.get_day_of_week_display()}"

# 6. 希望休
class LeaveRequest(models.Model):
    STATUS_CHOICES = [('approved', '承認'), ('pending', '申請中')]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    leave_date = models.DateField("希望休の日付")
    status = models.CharField("状態", max_length=50, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.member.name} - {self.leave_date}"

# 7. 日別必要人数
'''
class RequiredHeadcount(models.Model):
    shift_pattern = models.ForeignKey(ShiftPattern, on_delete=models.CASCADE, verbose_name="シフトパターン")
    day_group = models.ForeignKey(DayGroup, on_delete=models.CASCADE, verbose_name="曜日グループ") # ここを変更
    min_headcount = models.IntegerField("最低必要人数")
    max_headcount = models.IntegerField("推奨最大人数", null=True, blank=True)

    def __str__(self):
        return f"{self.shift_pattern.pattern_name} ({self.day_group.group_name})"
'''

class TimeSlotRequirement(models.Model):
    day_group = models.ForeignKey(DayGroup, on_delete=models.CASCADE, verbose_name="曜日グループ")
    start_time = models.TimeField("開始時刻")
    end_time = models.TimeField("終了時刻")
    min_headcount = models.IntegerField("最低必要人数")
    max_headcount = models.IntegerField("最大必要人数", null=True, blank=True, help_text="空欄の場合は上限なし") # この行を追加


    class Meta:
        verbose_name = "時間帯別必要人数"
        verbose_name_plural = "時間帯別必要人数"

    def __str__(self):
        return f"{self.day_group.group_name} ({self.start_time}-{self.end_time}): {self.min_headcount}人"



# 8. 関係性グループ定義
class RelationshipGroup(models.Model):
    RULE_CHOICES = [('incompatible', '非互換'), ('pairing', 'ペアリング')]
    group_name = models.CharField("グループ名", max_length=100)
    rule_type = models.CharField("ルールの種類", max_length=50, choices=RULE_CHOICES)

    def __str__(self):
        return self.group_name

# 9. グループの所属メンバー
class GroupMember(models.Model):
    group = models.ForeignKey(RelationshipGroup, on_delete=models.CASCADE, verbose_name="グループ")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")

    def __str__(self):
        return f"{self.group.group_name} - {self.member.name}"

# 10. 確定シフト
class Assignment(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name="従業員")
    shift_pattern = models.ForeignKey(ShiftPattern, on_delete=models.CASCADE, verbose_name="シフトパターン")
    shift_date = models.DateField("勤務日")

    def __str__(self):
        return f"{self.shift_date} {self.member.name} ({self.shift_pattern.pattern_name})"
    

