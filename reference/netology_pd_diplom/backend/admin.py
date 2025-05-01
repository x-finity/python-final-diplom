from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import path
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django import forms

from backend.tasks import do_import
import yaml

from backend.models import (
    User, Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter, Order, OrderItem,
    Contact, ConfirmEmailToken
)

class ImportYAMLForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    yaml_file = forms.FileField(label="YAML файл для импорта")

# --- Ограничение видимости для поставщиков ---
class ShopScopedAdmin(admin.ModelAdmin):
    """Поставщик видит только свои объекты."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if getattr(request.user, "type", None) == "shop":
            return qs.filter(shop__user=request.user)
        return qs.none()

# --- Админка пользователей ---
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
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
    actions = ['import_from_yaml']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # владелец видит только свой магазин
        if getattr(request.user, 'type', None) == 'shop':
            return qs.filter(user=request.user)
        return qs.none()

    def import_from_yaml(self, request, queryset):
        if 'apply' in request.POST:
            form = ImportYAMLForm(request.POST, request.FILES)
            if form.is_valid():
                yaml_file = request.FILES['yaml_file']
                data = yaml.safe_load(yaml_file.read())
                for shop in queryset:
                    do_import.delay(shop.user.id, data)
                self.message_user(request, "Импорт запущен")
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = ImportYAMLForm(initial={'_selected_action': queryset.values_list('id', flat=True)})

        return TemplateResponse(request, "admin/import_from_yaml.html", {
            'shops': queryset,
            'form': form,
            'title': "Импорт товаров из YAML",
            'selected_ids': request.POST.getlist('_selected_action') or queryset.values_list('id', flat=True)
        })

    import_from_yaml.short_description = "Импорт товаров из YAML"

# --- Информация о товарах ---
@admin.register(ProductInfo)
class ProductInfoAdmin(ShopScopedAdmin):
    list_display = ('id', 'product', 'shop', 'model', 'quantity', 'price', 'price_rrc')
    list_filter = ('shop',)
    search_fields = ('product__name', 'shop__name', 'model')
    autocomplete_fields = ('product', 'shop')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user

        if user.is_superuser:
            return qs

        if user.is_staff and user.company:
            return qs.filter(shop__user__company=user.company)

        return qs.none()

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

    @admin.display(description='Total, ₽')
    def total_sum(self, obj):
        return sum(
            item.quantity * item.product_info.price
            for item in obj.ordered_items.select_related('product_info')
        )

    @admin.action(description='Mark selected orders as assembled')
    def mark_as_assembled(self, request, queryset):
        updated = queryset.update(state='assembled')
        self.message_user(request, f'Обновлено заказов: {updated}')

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

# --- Токены подтверждения email ---
@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')
    search_fields = ('user__email', 'key')