from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import date, datetime, time, timedelta
from collections import defaultdict

from .models import Member, Assignment, LeaveRequest, MemberAvailability, ShiftPattern, OtherAssignment, TimeSlotRequirement
from .serializers import MemberSerializer, AssignmentSerializer, MemberAvailabilitySerializer, ShiftPatternSerializer, OtherAssignmentSerializer
from .solver import generate_schedule

class MemberListView(generics.ListAPIView):
    queryset = Member.objects.all().order_by('sort_order', 'name')
    serializer_class = MemberSerializer

class ShiftPatternListView(generics.ListAPIView):
    queryset = ShiftPattern.objects.all()
    serializer_class = ShiftPatternSerializer

class ScheduleDataView(APIView):
    def get(self, request, *args, **kwargs):
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')
        
        members = Member.objects.all().order_by('sort_order', 'name')
        member_serializer = MemberSerializer(members, many=True)

        if not start_date_str or not end_date_str:
            return Response({
                'members': member_serializer.data,
                'assignments': [], 'leave_requests': [], 'availabilities': [],
                'other_assignments': [], 'earnings': {},
            })

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        assignments = Assignment.objects.filter(shift_date__range=[start_date, end_date]).select_related('member', 'shift_pattern')
        assignment_serializer = AssignmentSerializer(assignments, many=True)

        leave_requests = LeaveRequest.objects.filter(status='approved', leave_date__range=[start_date, end_date])
        leave_data = [{'leave_date': str(req.leave_date), 'member_id': req.member.id} for req in leave_requests]
        
        availabilities = MemberAvailability.objects.all()
        availability_serializer = MemberAvailabilitySerializer(availabilities, many=True)

        other_assignments = OtherAssignment.objects.filter(shift_date__range=[start_date, end_date])
        other_serializer = OtherAssignmentSerializer(other_assignments, many=True)

        earnings_map = defaultdict(int)
        for assign in assignments:
            if assign.member.employee_type == 'hourly' and assign.member.hourly_wage:
                p = assign.shift_pattern
                total_duration = (datetime.combine(date.today(), p.end_time) - datetime.combine(date.today(), p.start_time)).total_seconds() / 60
                if p.end_time < p.start_time: total_duration += 24 * 60
                work_minutes = total_duration - p.break_minutes
                premium_minutes = 0
                current_time = datetime.combine(date.today(), p.start_time)
                for _ in range(int(total_duration)):
                    if current_time.time() >= time(22,0) or current_time.time() < time(5,0):
                        premium_minutes += 1
                    current_time += timedelta(minutes=1)
                normal_minutes = work_minutes - premium_minutes
                earnings = (normal_minutes * assign.member.hourly_wage) + (premium_minutes * assign.member.hourly_wage * 1.25)
                earnings_map[assign.member.id] += earnings / 60
        
        return Response({
            'assignments': assignment_serializer.data,
            'leave_requests': leave_data,
            'members': member_serializer.data,
            'availabilities': availability_serializer.data,
            'other_assignments': other_serializer.data,
            'earnings': {k: round(v) for k, v in earnings_map.items()},
        })

class GenerateShiftView(APIView):
    def post(self, request, *args, **kwargs):
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        if not start_date or not end_date:
            return Response({'error': 'start_date and end_date are required'}, status=status.HTTP_400_BAD_REQUEST)
        result = generate_schedule(start_date, end_date)
        return Response(result, status=status.HTTP_200_OK)

class ManualAssignmentView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        shift_date = request.data.get('shift_date')
        pattern_id = request.data.get('pattern_id')
        Assignment.objects.filter(member_id=member_id, shift_date=shift_date).delete()
        OtherAssignment.objects.filter(member_id=member_id, shift_date=shift_date).delete()
        if pattern_id:
            Assignment.objects.create(member_id=member_id, shift_pattern_id=pattern_id, shift_date=shift_date)
        return Response(status=status.HTTP_200_OK)

class OtherAssignmentView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        shift_date = request.data.get('shift_date')
        activity_name = request.data.get('activity_name')
        Assignment.objects.filter(member_id=member_id, shift_date=shift_date).delete()
        OtherAssignment.objects.filter(member_id=member_id, shift_date=shift_date).delete()
        if activity_name:
            OtherAssignment.objects.create(member_id=member_id, shift_date=shift_date, activity_name=activity_name)
        return Response(status=status.HTTP_200_OK)