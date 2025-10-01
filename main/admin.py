from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    MT5ConnectionSettings, 
    MT5ConnectionLog, 
    MT5ConnectionHealth, 
    MT5MonitoringSettings,
    TradingSystem,
    TimeFrame,
    DataFile
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


# ============================================================================
# ТОРГОВЫЕ СИСТЕМЫ
# ============================================================================

class TimeFrameInline(admin.TabularInline):
    """Inline для управления таймфреймами в торговой системе"""
    model = TimeFrame
    extra = 1
    fields = ['timeframe', 'level', 'is_active']
    ordering = ['level']


@admin.register(TradingSystem)
class TradingSystemAdmin(admin.ModelAdmin):
    """Админ панель для торговых систем"""
    
    list_display = [
        'system_status_icon', 'system_sid', 'name', 'symbol', 
        'timeframes_count', 'time_offset_minutes', 'is_active', 
        'files_count', 'created_at'
    ]
    
    list_filter = [
        'is_active', 'symbol', 'timeframes_count', 'created_at'
    ]
    
    search_fields = [
        'system_sid', 'name', 'symbol', 'description'
    ]
    
    list_editable = [
        'is_active'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'expected_files_info', 'file_pattern_info'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('system_sid', 'name', 'symbol')
        }),
        ('Конфигурация', {
            'fields': ('timeframes_count', 'time_offset_minutes', 'is_active')
        }),
        ('Дополнительно', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('expected_files_info', 'file_pattern_info', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TimeFrameInline]
    
    def system_status_icon(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-size: 16px;">●</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-size: 16px;">●</span>'
            )
    
    system_status_icon.short_description = 'Статус'
    
    def files_count(self, obj):
        count = obj.data_files.count()
        if count > 0:
            return format_html(
                '<a href="{}?trading_system__id__exact={}">{} files</a>',
                reverse('admin:main_datafile_changelist'),
                obj.id,
                count
            )
        return '0 files'
    
    files_count.short_description = 'Файлы'
    
    def expected_files_info(self, obj):
        return f"Ожидается файлов: {obj.get_expected_files_count()}"
    
    expected_files_info.short_description = 'Ожидаемые файлы'
    
    def file_pattern_info(self, obj):
        return format_html('<code>{}</code>', obj.get_file_pattern())
    
    file_pattern_info.short_description = 'Паттерн файлов'


@admin.register(TimeFrame)
class TimeFrameAdmin(admin.ModelAdmin):
    """Админ панель для таймфреймов"""
    
    list_display = [
        'trading_system', 'timeframe', 'level', 'is_active', 
        'expected_filename', 'files_count'
    ]
    
    list_filter = [
        'timeframe', 'is_active', 'trading_system'
    ]
    
    search_fields = [
        'trading_system__system_sid', 'trading_system__name', 'timeframe'
    ]
    
    list_editable = [
        'level', 'is_active'
    ]
    
    ordering = ['trading_system', 'level']
    
    def expected_filename(self, obj):
        return format_html('<code>{}</code>', obj.get_filename_pattern())
    
    expected_filename.short_description = 'Ожидаемый файл'
    
    def files_count(self, obj):
        count = obj.data_files.count()
        if count > 0:
            return format_html(
                '<a href="{}?timeframe__id__exact={}">{}</a>',
                reverse('admin:main_datafile_changelist'),
                obj.id,
                count
            )
        return '0'
    
    files_count.short_description = 'Файлов'


@admin.register(DataFile)
class DataFileAdmin(admin.ModelAdmin):
    """Админ панель для файлов данных"""
    
    list_display = [
        'file_status_icon', 'filename', 'trading_system', 'timeframe',
        'file_size_display', 'rows_processed', 'status', 'file_modified', 'processed_at'
    ]
    
    list_filter = [
        'status', 'trading_system', 'timeframe', 'created_at', 'processed_at'
    ]
    
    search_fields = [
        'filename', 'trading_system__system_sid', 'trading_system__name'
    ]
    
    readonly_fields = [
        'created_at', 'processed_at', 'json_preview'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('trading_system', 'timeframe', 'filename', 'file_path')
        }),
        ('Файл', {
            'fields': ('file_size', 'file_modified', 'status')
        }),
        ('Обработка', {
            'fields': ('rows_processed', 'error_message', 'processed_at')
        }),
        ('JSON данные', {
            'fields': ('json_preview',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['reprocess_files', 'mark_as_pending']
    
    def file_status_icon(self, obj):
        status_colors = {
            'pending': '#ffc107',      # yellow
            'processing': '#007bff',   # blue
            'completed': '#28a745',    # green
            'error': '#dc3545',        # red
            'skipped': '#6c757d',      # gray
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-size: 16px;">●</span>',
            color
        )
    
    file_status_icon.short_description = 'Статус'
    
    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "-"
    
    file_size_display.short_description = 'Размер'
    
    def json_preview(self, obj):
        if obj.json_data:
            import json
            try:
                formatted = json.dumps(obj.json_data, indent=2, ensure_ascii=False)
                if len(formatted) > 2000:
                    formatted = formatted[:2000] + "..."
                return format_html('<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px;">{}</pre>', formatted)
            except:
                return "Ошибка форматирования JSON"
        return "JSON данные отсутствуют"
    
    json_preview.short_description = 'Предпросмотр JSON'
    
    def reprocess_files(self, request, queryset):
        updated = queryset.update(status='pending', error_message='', processed_at=None)
        self.message_user(request, f'{updated} файлов помечены для повторной обработки.')
    
    reprocess_files.short_description = "Повторно обработать выбранные файлы"
    
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} файлов помечены как ожидающие обработки.')
    
    mark_as_pending.short_description = "Пометить как ожидающие"


# Настройка заголовков админ панели
admin.site.site_header = "Project GCE 3 - Админ панель"
admin.site.site_title = "Project GCE 3"
admin.site.index_title = "Управление MT5 & Торговыми системами"
