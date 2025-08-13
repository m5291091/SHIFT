from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# MemberAvailability と LeaveRequest をインポートリストに追加
from .models import Member, Assignment, LeaveRequest, MemberAvailability
# MemberAvailabilitySerializer をインポートリストに追加
from .serializers import MemberSerializer, AssignmentSerializer, MemberAvailabilitySerializer
from .solver import generate_schedule

class MemberListView(generics.ListAPIView):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

# フロントエンドが必要とする全描画データを返すAPIビュー
class ScheduleDataView(APIView):
    def get(self, request, *args, **kwargs):
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if not start_date or not end_date:
            return Response({})

        # 期間内の確定シフトを取得
        assignments = Assignment.objects.filter(shift_date__range=[start_date, end_date])
        assignment_serializer = AssignmentSerializer(assignments, many=True)

        # 期間内の承認済み希望休を取得
        leave_requests = LeaveRequest.objects.filter(
            status='approved',
            leave_date__range=[start_date, end_date]
        )
        # フロントエンドが扱いやすいようにデータを整形
        leave_data = [{'leave_date': str(req.leave_date), 'member_id': req.member.id} for req in leave_requests]

        # 全メンバーのリストを取得
        members = Member.objects.all()
        member_serializer = MemberSerializer(members, many=True)
        
        # 全メンバーの勤務可能情報を取得
        availabilities = MemberAvailability.objects.all()
        availability_serializer = MemberAvailabilitySerializer(availabilities, many=True)
        
        # 全てのデータをまとめて一つのレスポンスとして返す
        return Response({
            'assignments': assignment_serializer.data,
            'leave_requests': leave_data,
            'members': member_serializer.data,
            'availabilities': availability_serializer.data,
        })

class GenerateShiftView(APIView):
    # このクラスは変更ありません
    def post(self, request, *args, **kwargs):
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not start_date or not end_date:
            return Response({'error': 'start_date and end_date are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = generate_schedule(start_date, end_date)

        # 常に200 OKを返し、結果を詳細に伝える
        return Response(result, status=status.HTTP_200_OK)
