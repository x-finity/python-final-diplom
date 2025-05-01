from typing import Type

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User, Shop, ProductInfo
from backend.tasks import send_email

new_user_registered = Signal()

new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля
    When a token is created, an e-mail needs to be sent to the user
    :param sender: View Class that sent the signal
    :param instance: View Instance that sent the signal
    :param reset_password_token: Token Model Object
    :param kwargs:
    :return:
    """
    # send an e-mail to the user

    send_email.delay(
        f"Password Reset Token for {reset_password_token.user}",
        reset_password_token.key,
        reset_password_token.user.email
    )


@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """
     отправляем письмо с подтрердждением почты
    """
    if created and not instance.is_active:
        # send an e-mail to the user
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)

        send_email.delay(
            f"Password Reset Token for {instance.email}",
            token.key,
            instance.email
        )


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    отправяем письмо при изменении статуса заказа
    """
    # send an e-mail to the user
    user = User.objects.get(id=user_id)

    send_email.delay(
        "Обновление статуса заказа",
        "Заказ сформирован",
        user.email
    )

@receiver(post_save, sender=User)
def grant_staff_permissions(sender, instance, created, **kwargs):
    if instance.is_staff:
        # Получаем права на изменение Shop и ProductInfo
        shop = ContentType.objects.get_for_model(Shop)
        productinfo = ContentType.objects.get_for_model(ProductInfo)

        perms = Permission.objects.filter(content_type__in=[shop, productinfo],
                                          codename__in=['change_shop', 'change_productinfo'])

        instance.user_permissions.add(*perms)
