from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import date, datetime, time, timedelta
from collections import defaultdict

from .models import Member, Assignment, LeaveRequest, MemberAvailability, ShiftPattern, OtherAssignment, TimeSlotRequirement, FixedAssignment, Department, DesignatedHoliday, SolverSettings, PaidLeave
from .serializers import MemberSerializer, AssignmentSerializer, MemberAvailabilitySerializer, ShiftPatternSerializer, OtherAssignmentSerializer, FixedAssignmentSerializer, DepartmentSerializer, DesignatedHolidaySerializer, SolverSettingsSerializer, PaidLeaveSerializer
from .solver import generate_schedule

class DepartmentListView(generics.ListAPIView):
    queryset = Department.objects.all().order_by('name')
    serializer_class = DepartmentSerializer

class MemberListView(generics.ListAPIView):
    queryset = Member.objects.all().order_by('sort_order', 'name')
    serializer_class = MemberSerializer

class ShiftPatternListView(generics.ListAPIView):
    serializer_class = ShiftPatternSerializer

    def get_queryset(self):
        queryset = ShiftPattern.objects.all()
        department_id = self.request.query_params.get('department_id')
        if department_id is not None:
            queryset = queryset.filter(department_id=department_id)
        return queryset

class ScheduleDataView(APIView):
    def get(self, request, *args, **kwargs):
        department_id = self.request.query_params.get('department_id')
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')
        
        members_queryset = Member.objects.all()
        shift_patterns_queryset = ShiftPattern.objects.all()
        if department_id:
            members_queryset = members_queryset.filter(department_id=department_id)
            shift_patterns_queryset = shift_patterns_queryset.filter(department_id=department_id)

        members = members_queryset.order_by('sort_order', 'name')
        member_serializer = MemberSerializer(members, many=True)

        if not start_date_str or not end_date_str:
            return Response({
                'members': member_serializer.data,
                'assignments': [], 'leave_requests': [], 'availabilities': [],
                'other_assignments': [], 'earnings': {},
                'fixed_assignments': [], 'designated_holidays': [],
            })

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        assignments = Assignment.objects.filter(
            shift_date__range=[start_date, end_date],
            member__department_id=department_id
        ).select_related('member', 'shift_pattern')
        assignment_serializer = AssignmentSerializer(assignments, many=True)

        fixed_assignments = FixedAssignment.objects.filter(
            shift_date__range=[start_date, end_date],
            member__department_id=department_id
        ).select_related('member', 'shift_pattern')
        fixed_assignment_serializer = FixedAssignmentSerializer(fixed_assignments, many=True)

        leave_requests = LeaveRequest.objects.filter(
            status='approved', 
            leave_date__range=[start_date, end_date],
            member__department_id=department_id
        )
        leave_data = [{'leave_date': str(req.leave_date), 'member_id': req.member.id} for req in leave_requests]
        
        availabilities = MemberAvailability.objects.filter(
            member__department_id=department_id
        )
        availability_serializer = MemberAvailabilitySerializer(availabilities, many=True)

        other_assignments = OtherAssignment.objects.filter(
            shift_date__range=[start_date, end_date],
            member__department_id=department_id
        )
        other_serializer = OtherAssignmentSerializer(other_assignments, many=True)

        designated_holidays = DesignatedHoliday.objects.filter(
            date__range=[start_date, end_date],
            member__department_id=department_id
        )
        designated_holiday_serializer = DesignatedHolidaySerializer(designated_holidays, many=True)

        paid_leaves = PaidLeave.objects.filter(
            date__range=[start_date, end_date],
            member__department_id=department_id
        ).select_related('member')
        paid_leave_serializer = PaidLeaveSerializer(paid_leaves, many=True)

        earnings_map = defaultdict(float)
        premium_start, premium_end = time(22, 0), time(5, 0)
        for assign in assignments:
            if assign.member.employee_type == 'hourly' and assign.member.hourly_wage:
                p = assign.shift_pattern
                total_duration = (datetime.combine(date.today(), p.end_time) - datetime.combine(date.today(), p.start_time)).total_seconds() / 60
                if p.end_time < p.start_time: total_duration += 24 * 60
                work_minutes = total_duration - p.break_minutes
                
                premium_minutes = 0
                current_time = datetime.combine(date.today(), p.start_time)
                for _ in range(int(total_duration)):
                    if current_time.time() >= premium_start or current_time.time() < premium_end:
                        premium_minutes += 1
                    current_time += timedelta(minutes=1)
                
                normal_minutes = work_minutes - premium_minutes
                
                earnings = (normal_minutes * assign.member.hourly_wage) + (premium_minutes * assign.member.hourly_wage * 1.25)
                earnings_map[assign.member.id] += earnings / 60
        
        # Add earnings for paid leaves
        for pl in paid_leaves:
            if pl.member.employee_type == 'hourly' and pl.member.hourly_wage:
                earnings_map[pl.member.id] += (pl.hours * pl.member.hourly_wage)
        
        return Response({
            'assignments': assignment_serializer.data,
            'fixed_assignments': fixed_assignment_serializer.data,
            'leave_requests': leave_data,
            'members': member_serializer.data,
            'availabilities': availability_serializer.data,
            'other_assignments': other_serializer.data,
            'designated_holidays': designated_holiday_serializer.data,
            'paid_leaves': paid_leave_serializer.data, # Added
            'earnings': {k: round(v) for k, v in earnings_map.items()},
        })

class GenerateShiftView(APIView):
    def post(self, request, *args, **kwargs):
        department_id = request.data.get('department_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        if not start_date or not end_date or not department_id:
            return Response({'error': 'department_id, start_date and end_date are required'}, status=status.HTTP_400_BAD_REQUEST)
        result = generate_schedule(department_id, start_date, end_date)
        return Response(result, status=status.HTTP_200_OK)

class ManualAssignmentView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        shift_date = request.data.get('shift_date')
        pattern_id = request.data.get('pattern_id')
        
        member = Member.objects.get(id=member_id)

        DesignatedHoliday.objects.filter(member_id=member_id, date=shift_date).delete()
        PaidLeave.objects.filter(member_id=member_id, date=shift_date).delete() # Added
        
        Assignment.objects.filter(
            member_id=member_id, 
            shift_date=shift_date,
            member__department_id=member.department.id
        ).delete()
        OtherAssignment.objects.filter(
            member_id=member_id, 
            shift_date=shift_date,
            member__department_id=member.department.id
        ).delete()
        if pattern_id:
            Assignment.objects.create(member_id=member_id, shift_pattern_id=pattern_id, shift_date=shift_date)
        return Response(status=status.HTTP_200_OK)

class OtherAssignmentView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        shift_date = request.data.get('shift_date')
        activity_name = request.data.get('activity_name')
        
        member = Member.objects.get(id=member_id)

        DesignatedHoliday.objects.filter(member_id=member_id, date=shift_date).delete()
        PaidLeave.objects.filter(member_id=member_id, date=shift_date).delete() # Added
        
        Assignment.objects.filter(
            member_id=member_id, 
            shift_date=shift_date,
            member__department_id=member.department.id
        ).delete()
        OtherAssignment.objects.filter(
            member_id=member_id, 
            shift_date=shift_date,
            member__department_id=member.department.id
        ).delete()
        if activity_name:
            OtherAssignment.objects.create(member_id=member_id, shift_date=shift_date, activity_name=activity_name)
        return Response(status=status.HTTP_200_OK)

class BulkFixedAssignmentView(APIView):
    def post(self, request, *args, **kwargs):
        assignments = request.data.get('assignments', [])
        if not assignments:
            return Response({'error': 'No assignments provided'}, status=status.HTTP_400_BAD_REQUEST)

        fixed_assignments_to_create = []
        for assign in assignments:
            fixed_assignments_to_create.append(
                FixedAssignment(
                    member_id=assign['member_id'],
                    shift_pattern_id=assign['shift_pattern_id'],
                    shift_date=assign['shift_date']
                )
            )
        
        FixedAssignment.objects.bulk_create(fixed_assignments_to_create, ignore_conflicts=True)
        
        return Response({'status': 'success'}, status=status.HTTP_201_CREATED)

class FixedAssignmentView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        shift_date = request.data.get('shift_date')
        pattern_id = request.data.get('pattern_id')
        
        if not all([member_id, shift_date]):
            return Response({'error': 'member_id and shift_date are required'}, status=status.HTTP_400_BAD_REQUEST)

        DesignatedHoliday.objects.filter(member_id=member_id, date=shift_date).delete()
        PaidLeave.objects.filter(member_id=member_id, date=shift_date).delete() # Added
        
        # Delete any existing generated assignment for this member and date
        Assignment.objects.filter(member_id=member_id, shift_date=shift_date).delete()
        
        # If a pattern_id is provided, create or update the fixed assignment
        if pattern_id:
            FixedAssignment.objects.update_or_create(
                member_id=member_id,
                shift_date=shift_date,
                defaults={'shift_pattern_id': pattern_id}
            )
        # If no pattern_id is provided (e.g., 'delete' was selected), delete the fixed assignment
        else:
            FixedAssignment.objects.filter(member_id=member_id, shift_date=shift_date).delete()
            
        return Response(status=status.HTTP_200_OK)


class DesignatedHolidayView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        date = request.data.get('date')

        if not all([member_id, date]):
            return Response({'error': 'member_id and date are required'}, status=status.HTTP_400_BAD_REQUEST)

        # If it doesn't exist, create it. If it exists, do nothing.
        holiday, created = DesignatedHoliday.objects.get_or_create(
            member_id=member_id,
            date=date
        )

        if created:
            # it was created, so clear any other assignments for that day
            Assignment.objects.filter(member_id=member_id, shift_date=date).delete()
            FixedAssignment.objects.filter(member_id=member_id, shift_date=date).delete()
            OtherAssignment.objects.filter(member_id=member_id, shift_date=date).delete()
            PaidLeave.objects.filter(member_id=member_id, date=date).delete() # Added
            action = "created"
        else:
            action = "already_exists"
            
        return Response({'status': f'holiday {action}'}, status=status.HTTP_200_OK)


class PaidLeaveView(APIView):
    def post(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        date = request.data.get('date')

        if not all([member_id, date]):
            return Response({'error': 'member_id and date are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Delete any other assignments for this member and date
        Assignment.objects.filter(member_id=member_id, shift_date=date).delete()
        FixedAssignment.objects.filter(member_id=member_id, shift_date=date).delete()
        OtherAssignment.objects.filter(member_id=member_id, shift_date=date).delete()
        DesignatedHoliday.objects.filter(member_id=member_id, date=date).delete()
        LeaveRequest.objects.filter(member_id=member_id, leave_date=date).delete() # Also remove LeaveRequest if it exists

        # Create or get the PaidLeave
        paid_leave, created = PaidLeave.objects.get_or_create(
            member_id=member_id,
            date=date
        )

        if created:
            action = "created"
        else:
            action = "already_exists"
            
        return Response({'status': f'paid_leave {action}'}, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        member_id = request.data.get('member_id')
        date = request.data.get('date')

        if not all([member_id, date]):
            return Response({'error': 'member_id and date are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        deleted_count, _ = PaidLeave.objects.filter(member_id=member_id, date=date).delete()
        if deleted_count > 0:
            return Response({'status': 'deleted'}, status=status.HTTP_200_OK)
        return Response({'status': 'not_found'}, status=status.HTTP_404_NOT_FOUND)


class SolverSettingsDetailView(generics.RetrieveUpdateAPIView):
    queryset = SolverSettings.objects.all()
    serializer_class = SolverSettingsSerializer
    lookup_field = 'department_id' # Use department_id as the lookup field

class SolverSettingsListView(generics.ListCreateAPIView):
    queryset = SolverSettings.objects.all()
    serializer_class = SolverSettingsSerializer
