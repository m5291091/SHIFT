from django.db import migrations
from django.contrib.auth import get_user_model
from django.conf import settings

def populate_created_by(apps, schema_editor):
    User = get_user_model()
    try:
        superuser = User.objects.filter(is_superuser=True).first()
        if not superuser:
            # Fallback if no superuser exists, or create one
            # IMPORTANT: In a real production environment, you should handle this more robustly
            # e.g., by prompting the user to create a superuser or ensuring one exists.
            # For this automated task, we'll create a temporary one if none found.
            print("No superuser found. Attempting to create a temporary one for migration.")
            superuser = User.objects.create_user(username='temp_migration_admin', email='temp_admin@example.com', password='temp_password', is_staff=True, is_superuser=True)
            print("Created a temporary superuser 'temp_migration_admin' for data migration.")
    except Exception as e:
        print(f"Error getting or creating superuser: {e}")
        return # Exit if we can't get a user

    if superuser:
        models_to_update = [
            'Department', 'Member', 'ShiftPattern', 'DayGroup', 'TimeSlotRequirement',
            'MemberAvailability', 'LeaveRequest', 'RelationshipGroup', 'GroupMember',
            'Assignment', 'OtherAssignment', 'FixedAssignment', 'DesignatedHoliday',
            'PaidLeave', 'SpecificDateRequirement', 'SpecificTimeSlotRequirement', 'SolverSettings'
        ]
        
        for model_name in models_to_update:
            MyModel = apps.get_model('core', model_name)
            # Update only objects where created_by is NULL
            updated_count = MyModel.objects.filter(created_by__isnull=True).update(created_by=superuser)
            print(f"Updated {updated_count} {model_name} objects with created_by={superuser.username}")

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_assignment_created_by_daygroup_created_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(populate_created_by, reverse_code=migrations.RunPython.noop),
    ]