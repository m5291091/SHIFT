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