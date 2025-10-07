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
    SignalEvent,
    SignalExecutionLog,
)
from .models import (
    Instrument, TFCode, DataFeed, MarketBar, MarketIndicatorDef, MarketIndicatorValue, MarketDataFile,
    TradingSystemTFBinding,
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
        'timeframes_count', 'time_offset_minutes', 'is_active', 'trading_enabled', 'is_sar', 'lot_size',
        'created_at'
    ]
    
    list_filter = [
        'is_active', 'symbol', 'timeframes_count', 'created_at'
    ]
    
    search_fields = [
        'system_sid', 'name', 'symbol', 'description'
    ]
    
    list_editable = [
        'is_active', 'trading_enabled', 'is_sar', 'lot_size'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'expected_files_info', 'file_pattern_info'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('system_sid', 'name', 'symbol')
        }),
        ('Конфигурация', {
            'fields': (
                'timeframes_count', 'time_offset_minutes', 'data_dir', 'magic_number',
                'is_active', 'trading_enabled', 'is_sar', 'lot_size'
            )
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

            # Always read from global feed
            from .models import TradingSystemTFBinding, MarketIndicatorDef
            bindings = list(TradingSystemTFBinding.objects.filter(trading_system=ts).select_related('feed'))
            if not bindings:
                return 'No TF bindings yet. Add bindings to see indicators.'
            levels_map = {}
            all_names = set()
            for b in bindings:
                names = list(MarketIndicatorDef.objects.filter(feed=b.feed)
                             .values_list('name', flat=True).order_by('name').distinct())
                for n in names:
                    levels_map.setdefault(n, set()).add(int(b.level))
                all_names.update(names)
            if not all_names:
                return 'No indicators detected yet in global feed. Import data or verify bindings.'
            lines = []
            for name in sorted(all_names):
                lvls = sorted(levels_map.get(name, []))
                lvls_str = ', '.join(f'L{v}' for v in lvls) if lvls else '-'
                lines.append(f"{name}: {lvls_str}")
            html = '<pre style="white-space: pre-wrap; background:#f8f9fa; padding:8px; border-radius:4px; max-height:240px; overflow:auto;">' \
                   + '\n'.join(lines) + '</pre>'
            return format_html(html)
        indicators_available.short_description = 'Available Indicators (by TF levels)'

    class TFBindingInline(admin.TabularInline):
        model = TradingSystemTFBinding
        extra = 0
        fields = ['level', 'feed']
        ordering = ['level']

    inlines = [TimeFrameInline, TFBindingInline, SignalSettingsInline]
    actions = ['scan_global_files', 'import_global_pending', 'wipe_global_market_data', 'reset_and_reimport', 'generate_signals_now']
    
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

    def scan_global_files(self, request, queryset):
        from .services.global_feed_collector import collect_for_system
        total_c = total_u = total_s = 0
        for system in queryset:
            c, u, s = collect_for_system(system)
            total_c += c; total_u += u; total_s += s
        self.message_user(request, f"Global scan → Created: {total_c}, Updated: {total_u}, Unchanged: {total_s}")
    scan_global_files.short_description = 'Scan global feed files (by TF bindings)'

    def import_global_pending(self, request, queryset):
        from .models import MarketDataFile
        from .services.global_importer import import_market_datafile
        ok = failed = 0
        details = []
        for system in queryset:
            mdfs = MarketDataFile.objects.filter(feed__system_bindings__trading_system=system, status='pending')
            for mdf in mdfs:
                try:
                    res = import_market_datafile(mdf)
                    ok += 1
                except Exception as e:
                    failed += 1
                    details.append(f"{mdf.filename}: {e}")
        self.message_user(request, f"Global import → OK: {ok}, Failed: {failed} {'| ' + ', '.join(details[:2]) if details else ''}")
    import_global_pending.short_description = 'Import global pending files'

    def wipe_global_market_data(self, request, queryset):
        from django.db import transaction
        from .models import MarketBar, MarketIndicatorValue, MarketIndicatorDef, MarketDataFile, SignalEvent, SignalExecutionLog
        total_bars = total_vals = total_defs = total_signals = total_execs = 0
        with transaction.atomic():
            for system in queryset:
                feeds = [b.feed_id for b in system.tf_bindings.all()]
                if not feeds:
                    continue
                vals_qs = MarketIndicatorValue.objects.filter(bar__feed_id__in=feeds)
                total_vals += vals_qs.count()
                vals_qs.delete()
                bars_qs = MarketBar.objects.filter(feed_id__in=feeds)
                total_bars += bars_qs.count()
                bars_qs.delete()
                defs_qs = MarketIndicatorDef.objects.filter(feed_id__in=feeds)
                total_defs += defs_qs.count()
                defs_qs.delete()
                # Derived outputs: signals and executions for this system
                exec_qs = SignalExecutionLog.objects.filter(signal__trading_system=system)
                total_execs += exec_qs.count()
                exec_qs.delete()
                sig_qs = SignalEvent.objects.filter(trading_system=system)
                total_signals += sig_qs.count()
                sig_qs.delete()
                # Reset MarketDataFile status to pending to force re-import
                MarketDataFile.objects.filter(feed_id__in=feeds).update(status='pending', processed_at=None)
        self.message_user(request, f"Wiped global data for selected systems → Bars={total_bars}, IndicatorValues={total_vals}, IndicatorDefs={total_defs}, Signals={total_signals}, ExecLogs={total_execs}")
        wipe_global_market_data.short_description = 'Wipe global market data for selected systems'

    def reset_and_reimport(self, request, queryset):
        """Full reset (wipe + rescan + reimport + regenerate) for selected systems."""
        from .services.global_feed_collector import collect_for_system
        from .services.global_importer import import_market_datafile
        from .models import MarketDataFile
        total_imported = 0
        for system in queryset:
            # Wipe
            self.wipe_global_market_data(request, [system])
            # Re-scan
            collect_for_system(system)
            # Import all files for bound feeds
            feed_ids = [b.feed_id for b in system.tf_bindings.all()]
            files = MarketDataFile.objects.filter(feed_id__in=feed_ids)
            ok = 0
            for mdf in files:
                try:
                    import_market_datafile(mdf)
                    ok += 1
                except Exception:
                    pass
            total_imported += ok
            # Regenerate signals
            self.generate_signals_now(request, [system])
        self.message_user(request, f"Reset+Reimport complete. Files imported: {total_imported}")
    reset_and_reimport.short_description = 'Reset data and reimport (selected systems)'

    # Legacy scan action removed

    # Legacy import/wipe actions removed in global-only mode

    def generate_signals_now(self, request, queryset):
        """Re-generate signals for selected systems from current rules and data.

        Fully replaces existing SignalEvent records for each system to ensure
        consistency after rule changes.
        """
        from django.db import transaction
        from .services.signal_engine import generate_signals_for_system, diagnose_system_for_signals
        from .models import TimeFrame
        from .models import TradingSystemTFBinding, MarketBar

        total_saved = 0
        details = []
        for system in queryset:
            try:
                # Determine full window size based on base TF and mode
                try:
                    settings = system.signal_settings
                except Exception:
                    settings = None
                base_level = getattr(settings, 'signal_base_tf_level', None) or 1
                use_global = bool(getattr(settings, 'use_global_feed', False))
                limit = 1000
                if use_global:
                    bind = TradingSystemTFBinding.objects.filter(trading_system=system, level=base_level).select_related('feed').first()
                    if bind:
                        limit = MarketBar.objects.filter(feed=bind.feed).count() or 0
                else:
                    base_tf = TimeFrame.objects.filter(trading_system=system, level=base_level).first()
                    if base_tf:
                        # Legacy bars no longer used; fallback to a safe default if needed
                        limit = 1000

                events = generate_signals_for_system(system, limit_bars=max(0, limit))

                with transaction.atomic():
                    # Replace existing signals for the system
                    SignalEvent.objects.filter(trading_system=system).delete()
                    if events:
                        # Bulk create for speed
                        SignalEvent.objects.bulk_create(events, batch_size=1000)
                        saved = len(events)
                    else:
                        saved = 0
                total_saved += saved
                if saved == 0:
                    diag = diagnose_system_for_signals(system, limit_bars=200)
                    hint = ("; ".join(diag[:2]) + (" …" if len(diag) > 2 else "")) if diag else "no details"
                    details.append(f"{system.system_sid}: regenerated 0 ({hint})")
                else:
                    details.append(f"{system.system_sid}: regenerated {saved}")
            except Exception as e:
                details.append(f"{system.system_sid}: ERROR {e}")
        msg = f"Signals regenerated: {total_saved}. " + (" | ".join(details[:4]) + (" …" if len(details) > 4 else ""))
        self.message_user(request, msg)
    generate_signals_now.short_description = 'Сгенерировать сигналы сейчас'


@admin.register(TimeFrame)
class TimeFrameAdmin(admin.ModelAdmin):
    """Админ панель для таймфреймов"""
    
    list_display = [
        'trading_system', 'timeframe', 'level', 'is_active',
        'expected_filename'
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
    actions = ['scan_selected_timeframes']
    
    def expected_filename(self, obj):
        return format_html('<code>{}</code>', obj.get_filename_pattern())
    
    expected_filename.short_description = 'Ожидаемый файл'
    
    def scan_selected_timeframes(self, request, queryset):
        self.message_user(request, 'Legacy file scan is disabled in global-feed mode.')
    scan_selected_timeframes.short_description = 'Legacy scan (disabled)'

@admin.register(SignalEvent)
class SignalEventAdmin(admin.ModelAdmin):
    list_display = ['event_time', 'direction', 'action', 'trading_system', 'level', 'feed', 'price_close', 'values_short']
    list_filter = ['trading_system', 'level', 'feed', 'direction', 'action']
    search_fields = ['trading_system__system_sid']
    date_hierarchy = 'event_time'
    ordering = ['-event_time']
    readonly_fields = ['ind_values']

    def values_short(self, obj):
        vals = obj.ind_values or {}
        try:
            items = list(vals.items()) if isinstance(vals, dict) else []
            s = ', '.join(f"{k}={v}" for k, v in items[:4])
            if len(items) > 4:
                s += ' …'
            return s or '-'
        except Exception:
            return '-'
    values_short.short_description = 'Values'

    def price_close(self, obj):
        try:
            feed_id = getattr(obj, 'feed_id', None)
            if not feed_id:
                lvl = getattr(obj, 'level', None)
                ts = getattr(obj, 'trading_system', None)
                if ts and lvl:
                    b = TradingSystemTFBinding.objects.filter(trading_system=ts, level=int(lvl)).select_related('feed').first()
                    if b:
                        feed_id = b.feed_id
            if feed_id:
                mb = MarketBar.objects.filter(feed_id=feed_id, dt=obj.event_time).only('close').first()
                if mb and mb.close is not None:
                    return f"{float(mb.close):.5f}"
        except Exception:
            pass
        return '-'
    price_close.short_description = 'Price (Close)'


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



# Настройка заголовков админ панели
admin.site.site_header = "Project GCE 3 - Админ панель"
admin.site.site_title = "Project GCE 3"
admin.site.index_title = "Управление MT5 & Торговыми системами"


# ============================================================================
# Global feed admin
# ============================================================================

@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'is_active']
    search_fields = ['symbol', 'name']
    list_filter = ['is_active']


@admin.register(TFCode)
class TFCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'minutes', 'is_active']
    list_editable = ['minutes', 'is_active']
    search_fields = ['code']


@admin.register(DataFeed)
class DataFeedAdmin(admin.ModelAdmin):
    list_display = ['provider', 'instrument', 'tfcode', 'is_active']
    list_filter = ['provider', 'tfcode__code', 'is_active']
    search_fields = ['instrument__symbol']


@admin.register(MarketDataFile)
class MarketDataFileAdmin(admin.ModelAdmin):
    list_display = ['provider', 'filename', 'feed', 'file_size', 'file_modified', 'status', 'processed_at']
    list_filter = ['provider', 'status', 'feed']
    search_fields = ['filename']
    readonly_fields = ['created_at', 'processed_at']
    actions = ['scan_global_dir', 'import_all_pending', 'wipe_all_global', 'import_to_global']
    change_list_template = 'admin/main/marketdatafile/change_list.html'

    def import_to_global(self, request, queryset):
        from .services.global_importer import import_market_datafile
        ok = failed = 0
        for mdf in queryset:
            try:
                import_market_datafile(mdf)
                ok += 1
            except Exception:
                failed += 1
        self.message_user(request, f"Imported to global feed → OK: {ok}, Failed: {failed}")
    import_to_global.short_description = 'Import selected into Global Feed'

    def scan_global_dir(self, request, queryset):
        from .services.global_feed_collector import collect_global_dir
        c, u, s = collect_global_dir()
        self.message_user(request, f"Global scan: Created={c}, Updated={u}, Unchanged={s}")
    scan_global_dir.short_description = 'Scan global TS_EXPORTS_DIR for files'

    def import_all_pending(self, request, queryset):
        from .services.global_importer import import_market_datafile
        from .models import MarketDataFile
        ok = failed = 0
        for mdf in MarketDataFile.objects.filter(status='pending'):
            try:
                import_market_datafile(mdf); ok += 1
            except Exception:
                failed += 1
        self.message_user(request, f"Imported all pending → OK: {ok}, Failed: {failed}")
    import_all_pending.short_description = 'Import ALL pending files'

    # --- Extra object-tool endpoints (no selection required) ---
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()

        def wrap(view):
            return self.admin_site.admin_view(view)

        return [
            path('scan-global/', wrap(self._scan_global_view), name='main_marketdatafile_scan'),
            path('import-all/', wrap(self._import_all_view), name='main_marketdatafile_import_all'),
            path('wipe-all/', wrap(self._wipe_all_view), name='main_marketdatafile_wipe_all'),
        ] + urls

    def _scan_global_view(self, request):
        self.scan_global_dir(request, queryset=None)
        from django.shortcuts import redirect
        return redirect('admin:main_marketdatafile_changelist')

    def _import_all_view(self, request):
        self.import_all_pending(request, queryset=None)
        from django.shortcuts import redirect
        return redirect('admin:main_marketdatafile_changelist')

    def _wipe_all_view(self, request):
        self.wipe_all_global(request, queryset=None)
        from django.shortcuts import redirect
        return redirect('admin:main_marketdatafile_changelist')

    def wipe_all_global(self, request, queryset):
        from django.db import transaction
        from .models import MarketBar, MarketIndicatorValue, MarketIndicatorDef, MarketDataFile, SignalEvent, SignalExecutionLog
        with transaction.atomic():
            v = MarketIndicatorValue.objects.count(); MarketIndicatorValue.objects.all().delete()
            b = MarketBar.objects.count(); MarketBar.objects.all().delete()
            d = MarketIndicatorDef.objects.count(); MarketIndicatorDef.objects.all().delete()
            e = SignalExecutionLog.objects.count(); SignalExecutionLog.objects.all().delete()
            s = SignalEvent.objects.count(); SignalEvent.objects.all().delete()
            MarketDataFile.objects.all().update(status='pending', processed_at=None)
        self.message_user(request, f"Global wipe complete → Bars={b}, IndicatorValues={v}, IndicatorDefs={d}, Signals={s}, ExecLogs={e}. Files set to pending.")
    wipe_all_global.short_description = 'Wipe ALL global market data (set files to pending)'


@admin.register(MarketBar)
class MarketBarAdmin(admin.ModelAdmin):
    list_display = ['feed', 'dt', 'open', 'high', 'low', 'close', 'volume', 'created_at']
    list_filter = ['feed__provider', 'feed__instrument__symbol', 'feed__tfcode__code']
    date_hierarchy = 'dt'
    ordering = ['-dt']


@admin.register(MarketIndicatorDef)
class MarketIndicatorDefAdmin(admin.ModelAdmin):
    list_display = ['feed', 'name', 'dtype']
    list_filter = ['feed', 'dtype']
    search_fields = ['name']


@admin.register(MarketIndicatorValue)
class MarketIndicatorValueAdmin(admin.ModelAdmin):
    list_display = ['indicator', 'bar', 'value_int']
    list_filter = ['indicator__feed', 'indicator__name']










