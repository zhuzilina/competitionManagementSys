from rest_framework import permissions

class IsCompAdminOrReadOnly(permissions.BasePermission):
    """
    仅竞赛管理者可修改，其余登录用户仅查看。用于竞赛业务管理
    """
    def has_permission(self, request, view):
        # 判断用户是否已登录
        if not (request.user and request.user.is_authenticated):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        # 检查用户是否是合法角色
        allowed_roles = ['CompetitionAdministrator']

        return request.user.groups.filter(name__in=allowed_roles).exists()

class IsCommonManager(permissions.BasePermission):
    """
    普通管理者：老师、竞赛管理员、管理员。用于查看信息
    """
    def has_permission(self, request, view):
        # 判断用户是否已登录
        if not (request.user and request.user.is_authenticated):
            return False

        # 判断用户是否是超级管理员
        if request.user.is_superuser:
            return True

        # 检查用户是否是合法角色
        allowed_roles = ['CompetitionAdministrator','Teacher']

        return request.user.groups.filter(name__in=allowed_roles).exists()



class IsAdmin(permissions.BasePermission):
    """
    超级管理者： 管理员。用于修改用户
    """
    def has_permission(self, request, view):
        if not(request.user and request.user.is_authenticated):
            return False

        # 只有管理员才能访问
        return request.user.is_superuser


class NotDeletingSelf(permissions.BasePermission):
    """
    不允许管理员删除自己
    """
    def has_permission(self, request, view, obj):
        if request.method == 'DELETE':
            return obj != request.user
        return True

class NotChangingSelf(permissions.BasePermission):
    """
    不允许管理员修改信息
    """
    def has_permission(self, request, view, obj):
        if request.method == 'PATCH':
            return obj != request.user
        return True

class IsCompAdmin(permissions.BasePermission):
    """
    仅竞赛管理员
    """
    def has_permission(self, request, view):
        # 判断用户是否已登录
        if not (request.user and request.user.is_authenticated):
            return False
        # 检查用户是否是合法角色
        allowed_roles = ['CompetitionAdministrator']

        return request.user.groups.filter(name__in=allowed_roles).exists()