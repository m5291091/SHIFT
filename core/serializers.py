from rest_framework import serializers
from .models import Member, Assignment, ShiftPattern, MemberAvailability, OtherAssignment



class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        # 全てのフィールドを対象にするか、必要なものをリストアップ
        fields = [
            'id', 'name', 'employee_type', 'hourly_wage', 'monthly_salary', 
            'min_monthly_salary', 'max_monthly_salary', 'max_annual_salary', 
            'current_annual_salary', 'salary_year_start_month', 'max_hours_per_day', 
            'min_days_off_per_week', 'min_monthly_days_off', 'enforce_exact_holidays',
            'priority_score', 'sort_order', 
            'assignable_patterns' # 【この行を追加】
        ]

class AssignmentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    shift_pattern_name = serializers.CharField(source='shift_pattern.pattern_name', read_only=True)
    member_id = serializers.IntegerField(source='member.id', read_only=True) # この行を追加

    class Meta:
        model = Assignment
        fields = ['id', 'shift_date', 'member_name', 'shift_pattern_name', 'member_id', 'shift_pattern'] # fieldsにも追加

class MemberAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberAvailability
        # このモデルの全てのフィールドを対象にする
        fields = '__all__'

class ShiftPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftPattern
        fields = ['id', 'pattern_name', 'min_headcount', 'max_headcount']

class OtherAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OtherAssignment
        fields = '__all__'