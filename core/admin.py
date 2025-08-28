from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model # Add this import
from .forms import BulkLeaveRequestForm, BulkUpdateMinDaysOffForm, BulkAssignmentForm, BulkFixedAssignmentForm, BulkOtherAssignmentForm, BulkPaidLeaveForm
from .models import (
    Member, DayGroup, ShiftPattern, MemberAvailability,
    LeaveRequest, TimeSlotRequirement, RelationshipGroup, GroupMember, Assignment, OtherAssignment,
    FixedAssignment, SpecificDateRequirement, SpecificTimeSlotRequirement, MemberShiftPatternPreference,
    Department, DesignatedHoliday, PaidLeave, SolverSettings
)

User = get_user_model() # Define User model

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(managers=request.user)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return request.user in obj.managers.all()
        return True # Allow viewing the list, get_queryset will filter

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return request.user in obj.managers.all()
        return False # Disallow changing objects not explicitly managed

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return request.user in obj.managers.all()
        return False # Disallow deleting objects not explicitly managed

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return False

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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists() # Allow viewing list if user manages any department

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-update-days-off/', self.admin_site.admin_view(self.bulk_update_view), name='core_member_bulk_update'),
        ]
        return custom_urls + urls

    @admin.action(description='選択した従業員の最低公休日数を変更')
    def bulk_update_min_days_off_action(self, request, queryset):
        selected_ids = queryset.values_list('id', flat=True)
        # Filter queryset to only include members from departments managed by the user
        if not request.user.is_superuser:
            queryset = queryset.filter(department__in=request.user.managed_departments.all())
        
        if not queryset.exists():
            self.message_user(request, "選択された従業員の中に、あなたが管理する部門の従業員はいません。", level='error')
            return
        
        return redirect(f"{reverse('admin:core_member_bulk_update')}?ids={','.join(map(str, selected_ids))}")

    def bulk_update_view(self, request):
        if request.method == 'POST':
            form = BulkUpdateMinDaysOffForm(request.POST)
            if form.is_valid():
                new_days_off = form.cleaned_data['min_monthly_days_off']
                selected_ids_str = request.POST.get('selected_ids')
                selected_ids = [int(id) for id in selected_ids_str.split(',') if id]
                
                # Ensure only members from managed departments are updated
                members_to_update = Member.objects.filter(id__in=selected_ids)
                if not request.user.is_superuser:
                    members_to_update = members_to_update.filter(department__in=request.user.managed_departments.all())

                updated_count = members_to_update.update(min_monthly_days_off=new_days_off)
                self.message_user(request, f"{updated_count}人の従業員の最低公休日数を更新しました。")
                return redirect('admin:core_member_changelist')
        else:
            form = BulkUpdateMinDaysOffForm()
            ids = request.GET.get('ids')
            queryset = Member.objects.none() # Start with empty queryset
            if ids:
                selected_ids = [int(id) for id in ids.split(',') if id]
                queryset = Member.objects.filter(id__in=selected_ids)
                if not request.user.is_superuser:
                    queryset = queryset.filter(department__in=request.user.managed_departments.all())

        context = dict(self.admin_site.each_context(request), form=form, queryset=queryset, title="最低公休日数の一括変更")
        return render(request, 'admin/core/member/bulk_update_form.html', context)

class ShiftPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_name', 'department', 'start_time', 'end_time', 'break_minutes', 'is_night_shift', 'min_headcount', 'max_headcount')
    list_filter = ('department',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('member', 'leave_date', 'status')
    list_filter = ('status', 'member__department', 'member')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

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
                # Ensure the selected member belongs to a department managed by the user
                if not request.user.is_superuser and member.department not in request.user.managed_departments.all():
                    self.message_user(request, "選択された従業員は、あなたが管理する部門に属していません。", level='error')
                    return redirect('admin:core_leaverequest_changelist')

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
            # Filter member choices in the form based on managed departments
            if not request.user.is_superuser:
                form.fields['member'].queryset = Member.objects.filter(department__in=request.user.managed_departments.all())

        context = dict(self.admin_site.each_context(request), form=form, title="希望休の一括登録")
        return render(request, 'admin/core/leaverequest/bulk_add_form.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['bulk_add_url'] = reverse('admin:core_leaverequest_bulk_add')
        return super().changelist_view(request, extra_context=extra_context)

class TimeSlotRequirementAdmin(admin.ModelAdmin):
    list_display = ('department', 'day_group', 'start_time', 'end_time', 'min_headcount', 'max_headcount')
    list_filter = ('department', 'day_group',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('shift_date', 'member', 'shift_pattern')
    list_filter = ('shift_date', 'member__department', 'member', 'shift_pattern')
    actions = ['delete_selected_assignments']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    @admin.action(description='選択された確定シフトを削除')
    def delete_selected_assignments(self, request, queryset):
        # Filter queryset to only include assignments from departments managed by the user
        if not request.user.is_superuser:
            queryset = queryset.filter(member__department__in=request.user.managed_departments.all())

        if not queryset.exists():
            self.message_user(request, "選択された確定シフトの中に、あなたが管理する部門のシフトはありません。", level='error')
            return

        queryset.delete()
        self.message_user(request, f"選択された確定シフトを削除しました。")

class FixedAssignmentAdmin(admin.ModelAdmin):
    list_display = ('shift_date', 'member', 'shift_pattern')
    list_filter = ('shift_date', 'member__department', 'member', 'shift_pattern')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

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
                
                # Ensure the selected member belongs to a department managed by the user
                if not request.user.is_superuser and member.department not in request.user.managed_departments.all():
                    self.message_user(request, "選択された従業員は、あなたが管理する部門に属していません。", level='error')
                    return redirect('admin:core_fixedassignment_changelist')

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
            # Filter member choices in the form based on managed departments
            if not request.user.is_superuser:
                form.fields['member'].queryset = Member.objects.filter(department__in=request.user.managed_departments.all())
            # Filter shift_pattern choices in the form based on managed departments
            if not request.user.is_superuser:
                form.fields['shift_pattern'].queryset = ShiftPattern.objects.filter(department__in=request.user.managed_departments.all())


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


class OtherAssignmentAdmin(admin.ModelAdmin):
    list_display = ('member', 'shift_date', 'activity_name')
    list_filter = ('member__department', 'member', 'activity_name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

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
                
                # Ensure the selected member belongs to a department managed by the user
                if not request.user.is_superuser and member.department not in request.user.managed_departments.all():
                    self.message_user(request, "選択された従業員は、あなたが管理する部門に属していません。", level='error')
                    return redirect('admin:core_otherassignment_changelist')

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
            # Filter member choices in the form based on managed departments
            if not request.user.is_superuser:
                form.fields['member'].queryset = Member.objects.filter(department__in=request.user.managed_departments.all())

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


class SpecificDateRequirementAdmin(admin.ModelAdmin):
    list_display = ('date', 'department', 'shift_pattern', 'min_headcount', 'max_headcount')
    list_filter = ('date', 'department', 'shift_pattern')
    ordering = ('-date',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False


class SpecificTimeSlotRequirementAdmin(admin.ModelAdmin):
    list_display = ('date', 'department', 'start_time', 'end_time', 'min_headcount', 'max_headcount')
    list_filter = ('date', 'department',)
    ordering = ('-date', 'start_time')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False


class DesignatedHolidayAdmin(admin.ModelAdmin):
    list_display = ('member', 'date')
    list_filter = ('member__department', 'member',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False


class PaidLeaveAdmin(admin.ModelAdmin):
    list_display = ('member', 'date', 'hours')
    list_filter = ('member__department', 'member',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.member.department in request.user.managed_departments.all()
        return False

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
                
                # Ensure the selected member belongs to a department managed by the user
                if not request.user.is_superuser and member.department not in request.user.managed_departments.all():
                    self.message_user(request, "選択された従業員は、あなたが管理する部門に属していません。", level='error')
                    return redirect('admin:core_paidleave_changelist')

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
            # Filter member choices in the form based on managed departments
            if not request.user.is_superuser:
                form.fields['member'].queryset = Member.objects.filter(department__in=request.user.managed_departments.all())

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


class SolverSettingsAdmin(admin.ModelAdmin):
    list_display = ('department', 'name', 'is_default', 'headcount_penalty_cost')
    list_filter = ('department', 'is_default')
    fieldsets = (
        (None, {'fields': ('department', 'name', 'is_default')}),
        ('ペナルティコスト', {
            'fields': (
                'headcount_penalty_cost',
                'holiday_violation_penalty',
                'incompatible_penalty',
                'consecutive_work_violation_penalty',
                'salary_too_low_penalty',
                'salary_too_high_penalty',
                'unavailable_day_penalty',
            )
        }),
        ('ボーナス', {
            'fields': (
                'difficulty_bonus_weight',
                'work_day_deviation_penalty',
                'pairing_bonus',
                'shift_preference_bonus',
            )
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(department__in=request.user.managed_departments.all())

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return request.user.managed_departments.exists()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.managed_departments.exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is not None:
            return obj.department in request.user.managed_departments.all()
        return False


# --- モデルの登録 ---
admin.site.register(Member, MemberAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(DayGroup)
admin.site.register(MemberAvailability)
admin.site.register(ShiftPattern, ShiftPatternAdmin)
admin.site.register(TimeSlotRequirement, TimeSlotRequirementAdmin)
admin.site.register(SpecificDateRequirement, SpecificDateRequirementAdmin)
admin.site.register(SpecificTimeSlotRequirement, SpecificTimeSlotRequirementAdmin)
admin.site.register(RelationshipGroup)
admin.site.register(GroupMember)
admin.site.register(LeaveRequest, LeaveRequestAdmin)
admin.site.register(PaidLeave, PaidLeaveAdmin)
admin.site.register(FixedAssignment, FixedAssignmentAdmin)
admin.site.register(OtherAssignment, OtherAssignmentAdmin)
admin.site.register(DesignatedHoliday, DesignatedHolidayAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(SolverSettings, SolverSettingsAdmin)