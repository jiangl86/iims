def get_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # 所以这里是真实的ip
        ip = x_forwarded_for.split(',')[0]
    else:
        # 这里获得代理ip
        ip = request.META.get('REMOTE_ADDR')
    return ip
