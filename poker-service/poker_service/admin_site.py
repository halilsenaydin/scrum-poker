from django.contrib.admin import AdminSite
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

class CustomAdminSite(AdminSite):
    def login(self, request, extra_context=None):
        response = super().login(request, extra_context)

        if request.user.is_authenticated:
            next_url = request.GET.get("next")

            if not request.user.is_staff and next_url:
                return redirect(next_url)

        return response
    
admin_site = CustomAdminSite(name="custom_admin")

admin_site.register(User, UserAdmin)