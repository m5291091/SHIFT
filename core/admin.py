from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from .forms import BulkLeaveRequestForm, BulkUpdateMinDaysOffForm, BulkAssignmentForm, BulkFixedAssignmentForm, BulkOtherAssignmentForm, BulkPaidLeaveForm # Added
from .models import (
    Member, Skill, DayGroup, MemberSkill, ShiftPattern, MemberAvailability,
    LeaveRequest, TimeSlotRequirement, RelationshipGroup, GroupMember, Assignment, OtherAssignment,
    FixedAssignment, SpecificDateRequirement, SpecificTimeSlotRequirement, MemberShiftPatternPreference,
    Department, DesignatedHoliday, PaidLeave # Added PaidLeave
)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)

class MemberShiftPatternPreferenceInline(admin.TabularInline):
    model = MemberShiftPatternPreference
    extra = 1

class MemberAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'department', 'sort_order', 'employee_type', 'min_monthly_days_off',
        'max_consecutive_work_days', 'max_hours_per_day', 'enforce_exact_holidays'
    )
    list_filter = ('department', 'employee_type',)
    list_editable = ('sort_order', 'max_consecutive_work_days',)
    fieldsets = (
        (None, {'fields': ('name', 'department', 'priority_score', 'sort_order')}),
        ('給与形態', {'fields': ('employee_type', 'hourly_wage', 'monthly_salary')}),
        ('給与目標', {'fields': ('min_monthly_salary', 'max_monthly_salary', 'max_annual_salary', 'current_annual_salary', 'salary_year_start_month')}),
        ('労働時間・休日制約', {'fields': ('max_hours_per_day', 'min_days_off_per_week', 'min_monthly_days_off', 'max_consecutive_work_days', 'enforce_exact_holidays')}),
        ('勤務可能な曜日', {'fields': ('allowed_day_groups',)}),
    )
    search_fields = ('name',)
    filter_horizontal = ('allowed_day_groups',)
    actions = ['bulk_update_min_days_off_action']
    inlines = [MemberShiftPatternPreferenceInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-update-days-off/', self.admin_site.admin_view(self.bulk_update_view), name='core_member_bulk_update'),
        ]
        return custom_urls + urls

    @admin.action(description='選択した従業員の最低公休日数を変更')
    def bulk_update_min_days_off_action(self, request, queryset):
        selected_ids = queryset.values_list('id', flat=True)
        return redirect(f"{reverse('admin:core_member_bulk_update')}?ids={', '.join(map(str, selected_ids))}")

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
        context = dict(self.admin_site.each_context(request), form=form, queryset=queryset, title="最低公休日数の一括変更")
        return render(request, 'admin/core/member/bulk_update_form.html', context)

class ShiftPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_name', 'department', 'start_time', 'end_time', 'break_minutes', 'is_night_shift', 'min_headcount', 'max_headcount')
    list_filter = ('department',)

class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('member', 'leave_date', 'status')
    list_filter = ('status', 'member__department', 'member')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-add/', self.admin_site.admin_view(self.bulk_add_view), name='core_leaverequest_bulk_add'),
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
                        _, created = LeaveRequest.objects.get_or_create(member=member, leave_date=date_str, defaults={'status': 'approved'})
                        if created: created_count += 1
                self.message_user(request, f"{created_count}件の希望休を登録しました。")
                return redirect('admin:core_leaverequest_changelist')
        else:
            form = BulkLeaveRequestForm()
        context = dict(self.admin_site.each_context(request), form=form, title="希望休の一括登録")
        return render(request, 'admin/core/leaverequest/bulk_add_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['bulk_add_url'] = reverse('admin:core_leaverequest_bulk_add')
        return super().changelist_view(request, extra_context=extra_context)

class TimeSlotRequirementAdmin(admin.ModelAdmin):
    list_display = ('department', 'day_group', 'start_time', 'end_time', 'min_headcount', 'max_headcount')
    list_filter = ('department', 'day_group',)

class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('shift_date', 'member', 'shift_pattern')
    list_filter = ('shift_date', 'member__department', 'member', 'shift_pattern')

@admin.register(FixedAssignment)
class FixedAssignmentAdmin(admin.ModelAdmin):
    list_display = ('shift_date', 'member', 'shift_pattern')
    list_filter = ('shift_date', 'member__department', 'member', 'shift_pattern')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-add/', self.admin_site.admin_view(self.bulk_add_view), name='core_fixedassignment_bulk_add'),
        ]
        return custom_urls + urls

    def bulk_add_view(self, request):
        if request.method == 'POST':
            form = BulkFixedAssignmentForm(request.POST)
            if form.is_valid():
                member = form.cleaned_data['member']
                shift_pattern = form.cleaned_data['shift_pattern']
                dates_str = form.cleaned_data['dates']
                dates = dates_str.split(',')
                
                count = 0
                for date_str in dates:
                    if not date_str: continue
                    FixedAssignment.objects.update_or_create(
                        member=member, 
                        shift_date=date_str,
                        defaults={'shift_pattern': shift_pattern}
                    )
                    count += 1
                
                self.message_user(request, f"{count}件の固定シフトを登録・更新しました。")
                return redirect('admin:core_fixedassignment_changelist')
        else:
            form = BulkFixedAssignmentForm()

        context = dict(
           self.admin_site.each_context(request),
           form=form,
           title="固定シフトの一括登録"
        )
        return render(request, 'admin/core/fixedassignment/bulk_add_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['bulk_add_url'] = reverse('admin:core_fixedassignment_bulk_add')
        return super().changelist_view(request, extra_context)

@admin.register(OtherAssignment)
class OtherAssignmentAdmin(admin.ModelAdmin):
    list_display = ('member', 'shift_date', 'activity_name')
    list_filter = ('member__department', 'member', 'activity_name')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-add/', self.admin_site.admin_view(self.bulk_add_view), name='core_otherassignment_bulk_add'),
        ]
        return custom_urls + urls

    def bulk_add_view(self, request):
        if request.method == 'POST':
            form = BulkOtherAssignmentForm(request.POST)
            if form.is_valid():
                member = form.cleaned_data['member']
                activity_name = form.cleaned_data['activity_name']
                dates_str = form.cleaned_data['dates']
                dates = dates_str.split(',')
                
                count = 0
                for date_str in dates:
                    if not date_str: continue
                    OtherAssignment.objects.update_or_create(
                        member=member, 
                        shift_date=date_str,
                        defaults={'activity_name': activity_name}
                    )
                    count += 1
                
                self.message_user(request, f"{count}件のその他の割り当てを登録・更新しました。")
                return redirect('admin:core_otherassignment_changelist')
        else:
            form = BulkOtherAssignmentForm()

        context = dict(
           self.admin_site.each_context(request),
           form=form,
           title="その他の割り当てを一括登録"
        )
        return render(request, 'admin/core/otherassignment/bulk_add_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['bulk_add_url'] = reverse('admin:core_otherassignment_bulk_add')
        return super().changelist_view(request, extra_context)

@admin.register(SpecificDateRequirement)
class SpecificDateRequirementAdmin(admin.ModelAdmin):
    list_display = ('date', 'department', 'shift_pattern', 'min_headcount', 'max_headcount')
    list_filter = ('date', 'department', 'shift_pattern')
    ordering = ('-date',)

@admin.register(SpecificTimeSlotRequirement)
class SpecificTimeSlotRequirementAdmin(admin.ModelAdmin):
    list_display = ('date', 'department', 'start_time', 'end_time', 'min_headcount', 'max_headcount')
    list_filter = ('date', 'department',)
    ordering = ('-date', 'start_time')

@admin.register(DesignatedHoliday)
class DesignatedHolidayAdmin(admin.ModelAdmin):
    list_display = ('member', 'date')
    list_filter = ('member__department', 'member',)


@admin.register(PaidLeave)
class PaidLeaveAdmin(admin.ModelAdmin):
    list_display = ('member', 'date', 'hours')
    list_filter = ('member__department', 'member',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-add/', self.admin_site.admin_view(self.bulk_add_view), name='core_paidleave_bulk_add'),
        ]
        return custom_urls + urls

    def bulk_add_view(self, request):
        if request.method == 'POST':
            form = BulkPaidLeaveForm(request.POST)
            if form.is_valid():
                member = form.cleaned_data['member']
                dates_str = form.cleaned_data['dates']
                dates = dates_str.split(',')
                
                count = 0
                for date_str in dates:
                    if not date_str: continue
                    PaidLeave.objects.update_or_create(
                        member=member, 
                        date=date_str,
                        defaults={'hours': 8} # Default to 8 hours for paid leave
                    )
                    count += 1
                
                self.message_user(request, f"{count}件の有給を登録・更新しました。")
                return redirect('admin:core_paidleave_changelist')
        else:
            form = BulkPaidLeaveForm()

        context = dict(
           self.admin_site.each_context(request),
           form=form,
           title="有給の一括登録"
        )
        return render(request, 'admin/core/paidleave/bulk_add_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['bulk_add_url'] = reverse('admin:core_paidleave_bulk_add')
        return super().changelist_view(request, extra_context)

# --- モデルの登録 ---
admin.site.register(Member, MemberAdmin)
admin.site.register(ShiftPattern, ShiftPatternAdmin)
admin.site.register(LeaveRequest, LeaveRequestAdmin)
admin.site.register(TimeSlotRequirement, TimeSlotRequirementAdmin)
admin.site.register(Assignment, AssignmentAdmin)

admin.site.register(Skill)
admin.site.register(DayGroup)
admin.site.register(MemberSkill)
admin.site.register(MemberAvailability)
admin.site.register(RelationshipGroup)
admin.site.register(GroupMember)
