from .models import Notification


def notify(user, type, title, body='', link=''):
    return Notification.objects.create(user=user, type=type, title=title, body=body, link=link)
