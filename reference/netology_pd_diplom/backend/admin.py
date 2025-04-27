from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from backend.models import (
    User, Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter, Order, OrderItem,
    Contact, ConfirmEmailToken
)

# --- Ограничение видимости для поставщиков ---
class ShopScopedAdmin(admin.ModelAdmin):
    """Поставщик видит только свои объекты."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or getattr(request.user, "type", None) != "shop":
            return qs
        if hasattr(qs.model, 'shop'):
            return qs.filter(shop__user=request.user)
        return qs.filter(user=request.user)

# --- Админка пользователей ---
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'company', 'position')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'type', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

# --- Категории ---
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

# --- Продукты ---
class ProductInfoInline(admin.TabularInline):
    model = ProductInfo
    extra = 0
    autocomplete_fields = ('shop',)
    show_change_link = True

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)
    inlines = (ProductInfoInline,)

# --- Магазины ---
@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'state')
    list_filter = ('state',)
    search_fields = ('name', 'user__email')

# --- Информация о товарах ---
@admin.register(ProductInfo)
class ProductInfoAdmin(ShopScopedAdmin):
    list_display = ('id', 'product', 'shop', 'model', 'quantity', 'price', 'price_rrc')
    list_filter = ('shop',)
    search_fields = ('product__name', 'shop__name', 'model')
    autocomplete_fields = ('product', 'shop')

# --- Заказы ---
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ('product_info',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('product_info', 'product_info__product')

@admin.register(Order)
class OrderAdmin(ShopScopedAdmin):
    date_hierarchy = 'dt'
    list_display = ('id', 'user', 'dt', 'state', 'contact', 'total_sum')
    list_filter = ('state', 'dt')
    search_fields = ('user__email', 'contact__phone')
    list_editable = ('state',)
    inlines = (OrderItemInline,)
    actions = ('mark_as_assembled',)

    @admin.display(description=_('Total, ₽'))
    def total_sum(self, obj):
        return sum(
            item.quantity * item.product_info.price
            for item in obj.ordered_items.select_related('product_info')
        )

    @admin.action(description=_('Mark selected orders as assembled'))
    def mark_as_assembled(self, request, queryset):
        updated = queryset.update(state='assembled')
        self.message_user(request, _(f'Обновлено заказов: {updated}'))

# --- Позиции заказа ---
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_info', 'quantity')
    autocomplete_fields = ('order', 'product_info')
    search_fields = ('order__id', 'product_info__product__name')

# --- Параметры и параметры товаров ---
@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_info', 'parameter', 'value')
    autocomplete_fields = ('product_info', 'parameter')
    search_fields = ('product_info__product__name', 'parameter__name', 'value')

# --- Контакты ---
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'city', 'phone')
    search_fields = ('user__email', 'city', 'phone')

# --- Токены подтверждения email ---
@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')
    search_fields = ('user__email', 'key')