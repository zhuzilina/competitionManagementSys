from django.contrib import admin

from userManage.models import Menu
from mptt.admin import DraggableMPTTAdmin


# Register your models here.
@admin.register(Menu)
class MenuAdmin(DraggableMPTTAdmin):
    mptt_level_indent = 20