from django.http import HttpRequest
from accounts.models import User


def current_user_context(request):
    uid = request.session.get('user_id')
    if uid is None:
        return {'current_user': None}
    try:
        user = User.objects.select_related('role').get(user_id=uid)
        return {'current_user': user}
    except User.DoesNotExist:
        request.session.flush()
        return {'current_user': None}


def current_user(request: HttpRequest):
    uid = request.session.get('user_id')
    if uid is None:
        return None
    try:
        return User.objects.select_related('role').get(user_id=uid)
    except User.DoesNotExist:
        request.session.flush()
        return None


def login_required(view_func):
    from functools import wraps
    from django.shortcuts import redirect
    from django.contrib import messages

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = current_user(request)
        if user is None:
            messages.error(request, "Please log in to continue.")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(*required_roles):
    from functools import wraps
    from django.shortcuts import redirect
    from django.contrib import messages

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = current_user(request)
            if user is None:
                messages.error(request, "Please log in to continue.")
                return redirect('login')
            if user.role.role_name.lower() not in required_roles:
                messages.error(request, "You do not have permission to access this page.")
                return redirect('login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
