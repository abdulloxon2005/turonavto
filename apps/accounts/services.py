import secrets
import string

from django.db import transaction

from apps.core.services import log_action

from .models import User

TEMP_PASSWORD_ALPHABET = string.ascii_uppercase + string.digits


def generate_temp_password(length=8):
    return ''.join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))


@transaction.atomic
def create_staff(actor, *, full_name, phone, role, photo=None):
    temp_password = generate_temp_password()
    user = User.objects.create_user(
        phone=phone,
        password=temp_password,
        full_name=full_name,
        role=role,
        must_change_password=True,
    )
    if photo:
        user.photo = photo
        user.save(update_fields=['photo'])
    log_action(
        actor,
        action='staff.create',
        entity_type='User',
        entity_id=user.pk,
        new_value={'full_name': full_name, 'phone': phone, 'role': role},
    )
    return user, temp_password


@transaction.atomic
def reset_password(actor, user):
    temp_password = generate_temp_password()
    user.set_password(temp_password)
    user.must_change_password = True
    user.save(update_fields=['password', 'must_change_password'])
    log_action(
        actor,
        action='staff.reset_password',
        entity_type='User',
        entity_id=user.pk,
    )
    return temp_password


@transaction.atomic
def set_active(actor, user, is_active):
    old_value = {'is_active': user.is_active}
    user.is_active = is_active
    user.save(update_fields=['is_active'])
    log_action(
        actor,
        action='staff.block' if not is_active else 'staff.unblock',
        entity_type='User',
        entity_id=user.pk,
        old_value=old_value,
        new_value={'is_active': is_active},
    )
    return user


@transaction.atomic
def delete_staff(actor, user):
    entity_id = user.pk
    log_action(
        actor,
        action='staff.delete',
        entity_type='User',
        entity_id=entity_id,
        old_value={'full_name': user.full_name, 'phone': user.phone, 'role': user.role},
    )
    user.delete()


@transaction.atomic
def update_staff(actor, user, *, full_name, phone, is_active, photo=None, remove_photo=False):
    old_value = {'full_name': user.full_name, 'phone': user.phone, 'is_active': user.is_active}
    user.full_name = full_name
    user.phone = phone
    user.is_active = is_active
    update_fields = ['full_name', 'phone', 'is_active']
    if photo:
        user.photo = photo
        update_fields.append('photo')
    elif remove_photo and user.photo:
        user.photo.delete(save=False)
        user.photo = None
        update_fields.append('photo')
    user.save(update_fields=update_fields)
    log_action(
        actor,
        action='staff.update',
        entity_type='User',
        entity_id=user.pk,
        old_value=old_value,
        new_value={'full_name': full_name, 'phone': phone, 'is_active': is_active},
    )
    return user
