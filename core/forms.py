from django import forms
from .models import Member, ShiftPattern

class BulkLeaveRequestForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.all(),
        label="従業員"
    )
    leave_dates = forms.CharField(
        label="希望休（カレンダーで選択）",
        widget=forms.HiddenInput()
    )

class BulkUpdateMinDaysOffForm(forms.Form):
    min_monthly_days_off = forms.IntegerField(label="新しい月の最低公休日数")

class BulkAssignmentForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.all(),
        label="従業員"
    )
    # required=False で、このフィールドが空でもOKにする
    shift_pattern = forms.ModelChoiceField(
        queryset=ShiftPattern.objects.all(),
        label="シフトパターン（選択）",
        required=False 
    )
    activity_name = forms.CharField(
        label="または、業務内容を自由入力",
        required=False
    )
    dates = forms.CharField(
        label="対象日（カレンダーで選択）",
        widget=forms.HiddenInput()
    )