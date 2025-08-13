from django.urls import path
from .views import MemberListView, GenerateShiftView, ScheduleDataView # 変更

urlpatterns = [
    path('members/', MemberListView.as_view(), name='member-list'),
    path('generate-shifts/', GenerateShiftView.as_view(), name='generate-shifts'),
    path('schedule-data/', ScheduleDataView.as_view(), name='schedule-data'), # ここを変更
]