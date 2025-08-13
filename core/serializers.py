from rest_framework import serializers
from .models import Member
from .models import Member, Assignment, ShiftPattern, MemberAvailability# Assignment を追加


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'name', 'hourly_wage']


class AssignmentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.name', read_only=True)
    shift_pattern_name = serializers.CharField(source='shift_pattern.pattern_name', read_only=True)
    member_id = serializers.IntegerField(source='member.id', read_only=True) # この行を追加

    class Meta:
        model = Assignment
        fields = ['id', 'shift_date', 'member_name', 'shift_pattern_name', 'member_id'] # fieldsにも追加

class MemberAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberAvailability
        # このモデルの全てのフィールドを対象にする
        fields = '__all__'
