from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from .forms import BulkLeaveRequestForm,  BulkUpdateMinDaysOffForm
from .models import (
    Member, Skill, DayGroup, MemberSkill, ShiftPattern, MemberAvailability,
    LeaveRequest, TimeSlotRequirement, RelationshipGroup, GroupMember, Assignment
)

# Memberモデルの管理画面表示をカスタマイズ
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sort_order','employee_type', 'min_monthly_days_off', # 表示項目を調整
        'max_hours_per_day', 'min_days_off_per_week',
        'max_annual_salary'
    )
    list_editable = ('sort_order',)

    fieldsets = (
        (None, {'fields': ('name', 'priority_score','sort_order')}),
        ('給与形態', {'fields': ('employee_type', 'hourly_wage', 'monthly_salary')}),
        ('給与目標', {'fields': ('min_monthly_salary', 'max_monthly_salary', 'max_annual_salary', 'current_annual_salary', 'salary_year_start_month')}),
        ('労働時間・休日制約', {'fields': ('max_hours_per_day', 'min_days_off_per_week', 'min_monthly_days_off', 'enforce_exact_holidays')}),
        ('担当シフト・曜日', {'fields': ('assignable_patterns', 'allowed_day_groups')}),
    )
    list_filter = ('employee_type',)
    search_fields = ('name',)
    filter_horizontal = ('assignable_patterns', 'allowed_day_groups')

    # --- 【ここから追加】 ---
    actions = ['bulk_update_min_days_off_action']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'bulk-update-days-off/', 
                self.admin_site.admin_view(self.bulk_update_view), 
                name='core_member_bulk_update'
            ),
        ]
        return custom_urls + urls

    @admin.action(description='選択した従業員の最低公休日数を変更')
    def bulk_update_min_days_off_action(self, request, queryset):
        selected_ids = queryset.values_list('id', flat=True)
        return redirect(f"{reverse('admin:core_member_bulk_update')}?ids={','.join(map(str, selected_ids))}")

    def bulk_update_view(self, request):
        if request.method == 'POST':
            form = BulkUpdateMinDaysOffForm(request.POST)
            if form.is_valid():
                new_days_off = form.cleaned_data['min_monthly_days_off']
                selected_ids_str = request.POST.get('selected_ids')
                selected_ids = [int(id) for id in selected_ids_str.split(',') if id]
                
                updated_count = Member.objects.filter(id__in=selected_ids).update(min_monthly_days_off=new_days_off)
                
                self.message_user(request, f"{updated_count}人の従業員の最低公休日数を更新しました。")
                return redirect('admin:core_member_changelist')
        else:
            form = BulkUpdateMinDaysOffForm()
            ids = request.GET.get('ids')
            queryset = Member.objects.filter(id__in=[int(id) for id in ids.split(',') if id])

        context = dict(
           self.admin_site.each_context(request),
           form=form,
           queryset=queryset,
           title="最低公休日数の一括変更"
        )
        return render(request, 'admin/core/member/bulk_update_form.html', context)

# ShiftPatternモデルの管理画面表示をカスタマイズ
class ShiftPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_name', 'start_time', 'end_time', 'break_minutes', 'is_night_shift', 'min_headcount', 'max_headcount')

# LeaveRequestモデルの管理画面表示をカスタマイズ
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('member', 'leave_date', 'status')
    list_filter = ('status', 'member')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'bulk-add/', 
                self.admin_site.admin_view(self.bulk_add_view), 
                name='core_leaverequest_bulk_add'
            ),
        ]
        return custom_urls + urls

    def bulk_add_view(self, request):
        if request.method == 'POST':
            form = BulkLeaveRequestForm(request.POST)
            if form.is_valid():
                member = form.cleaned_data['member']
                dates_str = form.cleaned_data['leave_dates']
                dates = dates_str.split(',')
                
                created_count = 0
                for date_str in dates:
                    if date_str:
                        _, created = LeaveRequest.objects.get_or_create(
                            member=member,
                            leave_date=date_str,
                            defaults={'status': 'approved'}
                        )
                        if created:
                            created_count += 1
                
                self.message_user(request, f"{created_count}件の希望休を登録しました。")
                return redirect('admin:core_leaverequest_changelist')
        else:
            form = BulkLeaveRequestForm()

        context = dict(
           self.admin_site.each_context(request),
           form=form,
           title="希望休の一括登録",
        )
        return render(request, 'admin/core/leaverequest/bulk_add_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['bulk_add_url'] = reverse('admin:core_leaverequest_bulk_add')
        return super().changelist_view(request, extra_context=extra_context)

# TimeSlotRequirementの管理画面表示を定義
class TimeSlotRequirementAdmin(admin.ModelAdmin):
    list_display = ('day_group', 'start_time', 'end_time', 'min_headcount', 'max_headcount')
    list_filter = ('day_group',)

# --- モデルの登録 ---
admin.site.register(Member, MemberAdmin)
admin.site.register(ShiftPattern, ShiftPatternAdmin)
admin.site.register(LeaveRequest, LeaveRequestAdmin)
admin.site.register(TimeSlotRequirement, TimeSlotRequirementAdmin) # 新しいモデルを登録

# 他のモデル
admin.site.register(Skill)
admin.site.register(DayGroup)
admin.site.register(MemberSkill)
admin.site.register(MemberAvailability)
admin.site.register(RelationshipGroup)
admin.site.register(GroupMember)
admin.site.register(Assignment)