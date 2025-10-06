from django.contrib import admin
from datetime import timedelta
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    MT5ConnectionSettings,
    MT5ConnectionLog,
    MT5ConnectionHealth,
    MT5MonitoringSettings,
    TradingSystem,
    TradingSystemSignalSettings,
    TimeFrame,
    DataFile,
    IndicatorDefinition,
    Bar,
    IndicatorValue,
    ImportLog,
    SignalEvent,
    SignalExecutionLog,
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
        'system_status_icon', 'system_sid', 'name', 'symbol', 'magic_number', 'magic_number', 
        'timeframes_count', 'time_offset_minutes', 'is_active', 'trading_enabled', 'lot_size',
        'files_count', 'created_at'
    ]
    
    list_filter = [
        'is_active', 'symbol', 'timeframes_count', 'created_at'
    ]
    
    search_fields = [
        'system_sid', 'name', 'symbol', 'description'
    ]
    
    list_editable = [
        'is_active', 'trading_enabled', 'lot_size'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'expected_files_info', 'file_pattern_info'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('system_sid', 'name', 'symbol')
        }),
        ('Конфигурация', {
            'fields': ('timeframes_count', 'time_offset_minutes', 'data_dir', 'magic_number', 'is_active')
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
    
    class SignalSettingsInline(admin.StackedInline):
        model = TradingSystemSignalSettings
        extra = 0
        max_num = 1
        can_delete = True
        verbose_name = 'Signal Logic'
        verbose_name_plural = 'Signal Logic'
        readonly_fields = ['indicators_available']
        fields = ('signal_logic', 'signal_base_tf_level', 'signal_indicators', 'indicators_available')

        def get_formset(self, request, obj=None, **kwargs):
            # Keep a reference to parent TradingSystem for readonly field rendering when obj is not yet saved
            self._parent_ts = obj
            return super().get_formset(request, obj, **kwargs)

        def indicators_available(self, obj):
            from django.utils.html import format_html
            # Determine trading system
            ts = None
            if obj and getattr(obj, 'trading_system_id', None):
                ts = obj.trading_system
            elif hasattr(self, '_parent_ts') and self._parent_ts is not None:
                ts = self._parent_ts
            if ts is None:
                return 'Save Trading System first to see indicators.'

            # Collect indicators for this system and distinct TF levels observed in data
            names = list(IndicatorDefinition.objects.filter(trading_system=ts)
                        .values_list('name', flat=True).order_by('name').distinct())
            rows = IndicatorValue.objects.filter(indicator__trading_system=ts)
            rows = rows.values_list('indicator__name', 'tf_level').distinct()
            levels_map = {}
            for name, lvl in rows:
                if name not in levels_map:
                    levels_map[name] = set()
                if lvl is not None:
                    levels_map[name].add(int(lvl))

            if not names:
                return 'No indicators detected yet. Import data to populate the list.'

            lines = []
            for name in names:
                lvls = sorted(levels_map.get(name, []))
                lvls_str = ', '.join(f'L{v}' for v in lvls) if lvls else '-'
                lines.append(f"{name}: {lvls_str}")
            html = '<pre style="white-space: pre-wrap; background:#f8f9fa; padding:8px; border-radius:4px; max-height:240px; overflow:auto;">' \
                   + '\n'.join(lines) + '</pre>'
            return format_html(html)
        indicators_available.short_description = 'Available Indicators (by TF levels)'

    inlines = [TimeFrameInline, SignalSettingsInline]
    actions = ['scan_data_files', 'import_pending_files', 'wipe_market_data', 'generate_signals_now']
    
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

    def get_fieldsets(self, request, obj=None):
        fs = list(super().get_fieldsets(request, obj))
        # Ensure compatibility if model lacks data_dir
        try:
            has_data_dir = any(f.name == 'data_dir' for f in self.model._meta.get_fields())
        except Exception:
            has_data_dir = False
        if not has_data_dir:
            # Remove data_dir if present in second fieldset
            new_fs = []
            for name, opts in fs:
                fields = list(opts.get('fields', ()))
                if 'data_dir' in fields:
                    fields = [f for f in fields if f != 'data_dir']
                    opts = dict(opts)
                    opts['fields'] = tuple(fields)
                new_fs.append((name, opts))
            fs = new_fs
        return fs

    def scan_data_files(self, request, queryset):
        import os, glob
        from .services.datafile_collector import collect_for_system
        total_created = total_updated = total_skipped = 0
        debug_lines = []
        for system in queryset:
            data_dir = system.get_data_dir() if hasattr(system, 'get_data_dir') else ''
            pattern = os.path.join(data_dir, system.get_file_pattern()) if data_dir else ''
            try:
                found = glob.glob(pattern) if pattern else []
            except Exception:
                found = []
        c, u, s = collect_for_system(system)
        total_created += c
        total_updated += u
        total_skipped += s
        debug_lines.append(f"{system.system_sid}: dir={data_dir}, pattern={system.get_file_pattern()}, matches={len(found)}")
        if found:
            preview = ", ".join(os.path.basename(f) for f in found[:3])
            debug_lines.append(f"  e.g.: {preview}{' …' if len(found)>3 else ''}")
        # surface any per-file errors from collector
        errors = getattr(collect_for_system, 'last_errors', [])
        if errors:
            debug_lines.append(f"  errors: {len(errors)} → {errors[:2]}{' …' if len(errors)>2 else ''}")
        self.message_user(
            request,
            "Scanned. Created: %d, Updated: %d, Unchanged: %d" % (total_created, total_updated, total_skipped)
        )
        if debug_lines:
            self.message_user(request, " | ".join(debug_lines))
    scan_data_files.short_description = 'Сканировать папку данных и обновить файлы'

    def import_pending_files(self, request, queryset):
        from .services.bar_importer import import_datafile
        from .models import DataFile
        ok = failed = 0
        for system in queryset:
            qs = DataFile.objects.filter(trading_system=system, status='pending')
            for df in qs:
                try:
                    import_datafile(df)
                    ok += 1
                except Exception:
                    failed += 1
        self.message_user(request, f"Imported pending files → OK: {ok}, Failed: {failed}")
    import_pending_files.short_description = 'Импортировать все pending файлы системы'

    def wipe_market_data(self, request, queryset):
        from django.db import transaction
        from .models import DataIngestionStatus
        with transaction.atomic():
            iv_cnt = IndicatorValue.objects.count()
            IndicatorValue.objects.all().delete()
            bar_cnt = Bar.objects.count()
            Bar.objects.all().delete()
            log_cnt = ImportLog.objects.count()
            ImportLog.objects.all().delete()
            df_qs = DataFile.objects.all()
            df_cnt = df_qs.count()
            df_qs.update(status='pending', rows_processed=None, processed_at=None, error_message='')
            st = DataIngestionStatus.get()
            st.files_scanned = 0
            st.files_imported = 0
            st.rows_imported = 0
            st.last_run = None
            st.last_error = ''
            st.save()
        self.message_user(request, f"Wiped market data. Bars={bar_cnt}, IndicatorValues={iv_cnt}, Logs={log_cnt}, Files reset={df_cnt}")
    wipe_market_data.short_description = 'Очистить рыночные данные (Bars/Indicators/Logs)'

    def generate_signals_now(self, request, queryset):
        """Manually run signal generation for selected systems and save events."""
        from django.db import transaction
        from .services.signal_engine import generate_signals_for_system

        total_saved = 0
        details = []
        for system in queryset:
            try:
                events = generate_signals_for_system(system, limit_bars=1000)
                if not events:
                    details.append(f"{system.system_sid}: no signals")
                    continue
                saved = 0
                with transaction.atomic():
                    for ev in events:
                        obj, created = SignalEvent.objects.get_or_create(
                            trading_system=ev.trading_system,
                            timeframe=ev.timeframe,
                            event_time=ev.event_time,
                            direction=ev.direction,
                            action=getattr(ev, 'action', 'OPEN'),
                            defaults={'rule_text': ev.rule_text, 'bar': ev.bar},
                        )
                        if not created and obj.bar_id is None and ev.bar_id:
                            obj.bar = ev.bar
                            obj.save(update_fields=['bar'])
                        if created:
                            saved += 1
                total_saved += saved
                details.append(f"{system.system_sid}: saved {saved}")
            except Exception as e:
                details.append(f"{system.system_sid}: ERROR {e}")
        msg = f"Signals generated. New events: {total_saved}. " + (" | ".join(details[:4]) + (" …" if len(details) > 4 else ""))
        self.message_user(request, msg)
    generate_signals_now.short_description = 'Сгенерировать сигналы сейчас'


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
    actions = ['scan_selected_timeframes', 'import_pending_for_timeframes']
    
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


    def scan_selected_timeframes(self, request, queryset):
        from .services.datafile_collector import collect_for_timeframe
        total_created = total_updated = total_skipped = 0
        for tf in queryset:
            c, u, s = collect_for_timeframe(tf)
            total_created += c
            total_updated += u
            total_skipped += s
        self.message_user(
            request,
            f"Synced files. Created: {total_created}, Updated: {total_updated}, Unchanged: {total_skipped}"
        )
    scan_selected_timeframes.short_description = 'Сканировать файлы для выбранных таймфреймов'

@admin.register(Bar)
class BarAdmin(admin.ModelAdmin):
    list_display = ['dt', 'bartime', 'timeframe', 'trading_system', 'open', 'high', 'low', 'close', 'volume', 'data_file']
    list_filter = ['timeframe', 'trading_system']
    search_fields = ['symbol']
    date_hierarchy = 'dt'
    ordering = ['-dt']
    readonly_fields = [
        'trading_system', 'timeframe', 'data_file', 'dt', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'source_row'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def bartime(self, obj):
        # Show bar time exactly as in source (stored in dt_server during import). No fallbacks.
        if getattr(obj, 'dt_server', None):
            try:
                return obj.dt_server.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                return str(obj.dt_server)
        return '-'
    bartime.short_description = 'BAR TIME'


@admin.register(IndicatorDefinition)
class IndicatorDefinitionAdmin(admin.ModelAdmin):
    list_display = ['trading_system', 'name', 'dtype']
    list_filter = ['trading_system', 'dtype']
    search_fields = ['name', 'trading_system__system_sid']
    ordering = ['trading_system', 'name']


@admin.register(IndicatorValue)
class IndicatorValueAdmin(admin.ModelAdmin):
    list_display = ['bar', 'indicator', 'tf_level', 'value_int']
    list_filter = ['indicator__trading_system', 'indicator', 'tf_level']
    search_fields = ['indicator__name']
    date_hierarchy = 'bar__dt'
    readonly_fields = ['bar', 'indicator', 'tf_level', 'value_int']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SignalEvent)
class SignalEventAdmin(admin.ModelAdmin):
    list_display = ['event_time', 'direction', 'action', 'trading_system', 'timeframe', 'bar']
    list_filter = ['trading_system', 'timeframe', 'direction', 'action']
    search_fields = ['trading_system__system_sid']
    date_hierarchy = 'event_time'
    ordering = ['-event_time']


@admin.register(SignalExecutionLog)
class SignalExecutionLogAdmin(admin.ModelAdmin):
    list_display = ['executed_at', 'signal', 'success', 'short_message']
    list_filter = ['success']
    search_fields = ['signal__trading_system__system_sid']
    ordering = ['-executed_at']

    def short_message(self, obj):
        msg = obj.message or ''
        return (msg[:120] + '...') if len(msg) > 120 else msg
    short_message.short_description = 'Message'

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
    
    actions = ['reprocess_files', 'mark_as_pending', 'import_to_db']
    
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
    
    def import_to_db(self, request, queryset):
        from .services.bar_importer import import_datafile
        ok = 0
        failed = 0
        details = []
        for df in queryset:
            try:
                res = import_datafile(df)
                ok += 1
                details.append(f"{df.filename}: bars={res.bars_created}, indVals={res.indicator_values_created}")
            except Exception as e:
                failed += 1
                details.append(f"{df.filename}: ERROR {e}")
        summary = f"Imported: {ok}, Failed: {failed}. " + (" | ".join(details[:3]) + (" …" if len(details) > 3 else ""))
        self.message_user(request, summary)
    import_to_db.short_description = 'Импортировать выбранные файлы в БД'

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










