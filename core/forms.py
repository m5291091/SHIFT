from django import forms
from .models import Member

class BulkLeaveRequestForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.all(),
        label="従業員"
    )
    leave_dates = forms.CharField(
        label="希望休（カレンダーで選択）",
        widget=forms.HiddenInput() # このフィールドはJSで操作するため非表示
    )

class BulkUpdateMinDaysOffForm(forms.Form):
    min_monthly_days_off = forms.IntegerField(label="新しい月の最低公休日数")
    