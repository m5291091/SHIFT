from django.urls import path
from .views import (
    MemberListView, 
    GenerateShiftView, 
    ScheduleDataView, 
    ShiftPatternListView,
    ManualAssignmentView,
    OtherAssignmentView,
    DepartmentListView,
    BulkFixedAssignmentView,
    FixedAssignmentView
)

urlpatterns = [
    path('departments/', DepartmentListView.as_view(), name='department-list'),
    path('members/', MemberListView.as_view(), name='member-list'),
    path('shift-patterns/', ShiftPatternListView.as_view(), name='shift-pattern-list'),
    path('schedule-data/', ScheduleDataView.as_view(), name='schedule-data'),
    path('generate-shifts/', GenerateShiftView.as_view(), name='generate-shifts'),
    path('manual-assignment/', ManualAssignmentView.as_view(), name='manual-assignment'),
    path('other-assignment/', OtherAssignmentView.as_view(), name='other-assignment'),
    path('bulk-fixed-assignments/', BulkFixedAssignmentView.as_view(), name='bulk-fixed-assignments'),
    path('fixed-assignment/', FixedAssignmentView.as_view(), name='fixed-assignment'),
]