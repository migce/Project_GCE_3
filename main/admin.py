from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    MT5ConnectionSettings, 
    MT5ConnectionLog, 
    MT5ConnectionHealth, 
    MT5MonitoringSettings
)

# Register your models here.

@admin.register(MT5ConnectionSettings)
class MT5ConnectionSettingsAdmin(admin.ModelAdmin):
    """Админ панель для настроек MT5"""
    
    list_display = [
        'status_icon', 'name', 'server', 'login', 
        'is_default', 'is_active', 'created_at'
    ]
    
    list_filter = [
        'is_active', 'is_default', 'server', 'created_at'
    ]
    
    search_fields = [
        'name', 'server', 'login'
    ]
    
    list_editable = [
        'is_active', 'is_default'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'notes')
        }),
        ('Настройки терминала', {
            'fields': ('terminal_path', 'portable'),
            'classes': ('collapse',)
        }),
        ('Настройки подключения', {
            'fields': ('server', 'login', 'password', 'timeout')
        }),
        ('Управление', {
            'fields': ('is_active', 'is_default')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['make_default', 'activate_settings', 'deactivate_settings']
    
    def status_icon(self, obj):
        """Иконка статуса"""
        if obj.is_active:
            icon = "🟢"
            color = "green"
        else:
            icon = "🔴"
            color = "red"
        
        default_mark = " 🌟" if obj.is_default else ""
        
        return format_html(
            '<span style="color: {};">{}</span>{}',
            color, icon, default_mark
        )
    status_icon.short_description = "Статус"
    
    def make_default(self, request, queryset):
        """Действие: сделать настройкой по умолчанию"""
        if queryset.count() > 1:
            self.message_user(
                request, 
                "Можно выбрать только одну настройку", 
                level='ERROR'
            )
            return
        
        # Сначала убираем флаг у всех
        MT5ConnectionSettings.objects.update(is_default=False)
        # Затем устанавливаем для выбранной
        queryset.update(is_default=True, is_active=True)
        
        self.message_user(
            request, 
            f"Настройка '{queryset.first().name}' установлена по умолчанию"
        )
    make_default.short_description = "Сделать настройкой по умолчанию"
    
    def activate_settings(self, request, queryset):
        """Действие: активировать настройки"""
        count = queryset.update(is_active=True)
        self.message_user(
            request, 
            f"Активировано настроек: {count}"
        )
    activate_settings.short_description = "Активировать выбранные настройки"
    
    def deactivate_settings(self, request, queryset):
        """Действие: деактивировать настройки"""
        count = queryset.update(is_active=False, is_default=False)
        self.message_user(
            request, 
            f"Деактивировано настроек: {count}"
        )
    deactivate_settings.short_description = "Деактивировать выбранные настройки"


@admin.register(MT5ConnectionLog)
class MT5ConnectionLogAdmin(admin.ModelAdmin):
    """Админ панель для логов подключений MT5"""
    
    list_display = [
        'status_icon', 'settings', 'connection_time', 
        'success', 'short_error'
    ]
    
    list_filter = [
        'success', 'connection_time', 'settings'
    ]
    
    search_fields = [
        'settings__name', 'error_message'
    ]
    
    readonly_fields = [
        'settings', 'connection_time', 'success', 
        'error_message', 'account_info_formatted'
    ]
    
    fields = [
        'settings', 'connection_time', 'success',
        'error_message', 'account_info_formatted'
    ]
    
    def has_add_permission(self, request):
        """Запрещаем добавление логов вручную"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем изменение логов"""
        return False
    
    def status_icon(self, obj):
        """Иконка статуса подключения"""
        if obj.success:
            return format_html('<span style="color: green;">✅</span>')
        else:
            return format_html('<span style="color: red;">❌</span>')
    status_icon.short_description = "Статус"
    
    def short_error(self, obj):
        """Краткое сообщение об ошибке"""
        if obj.error_message:
            if len(obj.error_message) > 50:
                return obj.error_message[:50] + "..."
            return obj.error_message
        return "-"
    short_error.short_description = "Ошибка"
    
    def account_info_formatted(self, obj):
        """Форматированная информация о счете"""
        if obj.account_info:
            html = "<table style='border-collapse: collapse;'>"
            for key, value in obj.account_info.items():
                html += f"<tr><td style='border: 1px solid #ddd; padding: 4px;'><strong>{key}:</strong></td>"
                html += f"<td style='border: 1px solid #ddd; padding: 4px;'>{value}</td></tr>"
            html += "</table>"
            return mark_safe(html)
        return "Нет данных"
    account_info_formatted.short_description = "Информация о счете"


@admin.register(MT5ConnectionHealth)
class MT5ConnectionHealthAdmin(admin.ModelAdmin):
    """Admin panel for MT5 connection health records"""
    
    list_display = [
        'status_icon', 'settings', 'check_time', 'ping_display', 
        'balance', 'equity', 'error_message_short'
    ]
    
    list_filter = [
        'is_connected', 'settings', 'check_time'
    ]
    
    search_fields = [
        'settings__name', 'error_message'
    ]
    
    readonly_fields = [
        'check_time', 'settings', 'is_connected', 'ping_ms',
        'balance', 'equity', 'margin', 'error_message'
    ]
    
    date_hierarchy = 'check_time'
    
    list_per_page = 50
    
    ordering = ['-check_time']
    
    def has_add_permission(self, request):
        """Health records are created automatically"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Health records are read-only"""
        return False
    
    def status_icon(self, obj):
        """Connection status icon"""
        if obj.is_connected:
            return format_html(
                '<span style="color: green; font-size: 16px;">✅</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-size: 16px;">❌</span>'
            )
    status_icon.short_description = 'Status'
    
    def ping_display(self, obj):
        """Formatted ping display"""
        if obj.ping_ms is not None:
            if obj.ping_ms < 100:
                color = 'green'
            elif obj.ping_ms < 500:
                color = 'orange'
            else:
                color = 'red'
            return format_html(
                '<span style="color: {};">{} ms</span>',
                color, obj.ping_ms
            )
        return '-'
    ping_display.short_description = 'Ping'
    
    def error_message_short(self, obj):
        """Shortened error message"""
        if obj.error_message:
            return obj.error_message[:50] + '...' if len(obj.error_message) > 50 else obj.error_message
        return '-'
    error_message_short.short_description = 'Error'


@admin.register(MT5MonitoringSettings)
class MT5MonitoringSettingsAdmin(admin.ModelAdmin):
    """Admin panel for MT5 monitoring settings"""
    
    list_display = [
        'status_icon', 'monitoring_enabled', 'auto_reconnect_enabled',
        'health_check_interval', 'max_reconnect_attempts', 'updated_at'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Monitoring Control', {
            'fields': ('monitoring_enabled', 'auto_reconnect_enabled')
        }),
        ('Timing Settings', {
            'fields': (
                'health_check_interval', 'reconnect_interval', 
                'max_reconnect_attempts'
            )
        }),
        ('Alert Settings', {
            'fields': ('enable_email_alerts', 'alert_email'),
            'classes': ('collapse',)
        }),
        ('Data Retention', {
            'fields': ('health_records_retention_days',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Only allow one settings instance"""
        return not MT5MonitoringSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of settings"""
        return False
    
    def status_icon(self, obj):
        """Monitoring status icon"""
        if obj.monitoring_enabled:
            return format_html(
                '<span style="color: green; font-size: 16px;">🟢</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-size: 16px;">🔴</span>'
            )
    status_icon.short_description = 'Status'


# Настройка заголовков админ панели
admin.site.site_header = "Project GCE 3 - Админ панель"
admin.site.site_title = "Project GCE 3"
admin.site.index_title = "Управление MT5 подключениями"
