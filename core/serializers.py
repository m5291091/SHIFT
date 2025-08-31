from rest_framework import serializers
from .models import (
    Member, Assignment, ShiftPattern, MemberAvailability, OtherAssignment, FixedAssignment, Department, DesignatedHoliday, SolverSettings, PaidLeave
)

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'

class MemberSerializer(serializers.ModelSerializer):
    shift_preferences = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            'id', 'name', 'department', 'employee_type', 'hourly_wage', 'monthly_salary', 
            'min_monthly_salary', 'max_monthly_salary', 'max_annual_salary', 
            'current_annual_salary', 'salary_year_start_month', 'max_hours_per_day', 
            'min_days_off_per_week', 'min_monthly_days_off', 'max_consecutive_work_days', 'enforce_exact_holidays',
            'priority_score', 'sort_order', 
            'shift_preferences'
        ]

    def get_shift_preferences(self, obj):
        return [pref.shift_pattern.id for pref in obj.membershiftpatternpreference_set.all()]

class AssignmentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    shift_pattern_name = serializers.CharField(source='shift_pattern.pattern_name', read_only=True)
    member_id = serializers.IntegerField(source='member.id', read_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'shift_date', 'member_name', 'shift_pattern_name', 'member_id', 'shift_pattern']

class FixedAssignmentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    shift_pattern_name = serializers.CharField(source='shift_pattern.pattern_name', read_only=True)
    member_id = serializers.IntegerField(source='member.id', read_only=True)

    class Meta:
        model = FixedAssignment
        fields = ['id', 'shift_date', 'member_name', 'shift_pattern_name', 'member_id', 'shift_pattern']

class MemberAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberAvailability
        fields = '__all__'

class ShiftPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftPattern
        fields = ['id', 'department', 'pattern_name', 'min_headcount', 'max_headcount']

class OtherAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OtherAssignment
        fields = '__all__'

class DesignatedHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignatedHoliday
        fields = '__all__'


class SolverSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolverSettings
        fields = '__all__'


class PaidLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaidLeave
        fields = '__all__'
