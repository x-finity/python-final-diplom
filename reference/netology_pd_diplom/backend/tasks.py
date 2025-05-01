from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

@shared_task
def send_email(subject, message, recipient):
    msg = EmailMultiAlternatives(subject, message, settings.EMAIL_HOST_USER, [recipient])
    msg.send()


@shared_task
def do_import(user_id, data):
    from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter

    shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user_id)
    for category in data['categories']:
        category_obj, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
        category_obj.shops.add(shop)

    ProductInfo.objects.filter(shop=shop).delete()

    for item in data['goods']:
        product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
        product_info = ProductInfo.objects.create(
            product=product,
            shop=shop,
            model=item['model'],
            external_id=item['id'],
            quantity=item['quantity'],
            price=item['price'],
            price_rrc=item['price_rrc']
        )
        for name, value in item['parameters'].items():
            param, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.create(
                product_info=product_info,
                parameter=param,
                value=value
            )
    return True
