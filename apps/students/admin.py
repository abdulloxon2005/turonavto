from django.contrib import admin

from .models import DeleteRequest, InstructorStudent, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'brought_by_user_id', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('full_name', 'phone', 'passport_no')


@admin.register(DeleteRequest)
class DeleteRequestAdmin(admin.ModelAdmin):
    list_display = ('entity_type', 'entity_id', 'requested_by', 'status', 'created_at')
    list_filter = ('status', 'entity_type')


admin.site.register(InstructorStudent)
