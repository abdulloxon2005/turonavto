from django.contrib import admin

from .models import Group, GroupInstructor, GroupStudent, GroupTeacher


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'status', 'start_date', 'price', 'max_students')
    list_filter = ('status', 'category')
    search_fields = ('name',)


admin.site.register(GroupTeacher)
admin.site.register(GroupInstructor)
admin.site.register(GroupStudent)
