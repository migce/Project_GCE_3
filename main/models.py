from django.db import models
from django.core.exceptions import ValidationError

# Create your models here.

class MT5ConnectionSettings(models.Model):
    """Модель для хранения настроек подключения к MetaTrader 5"""
    
    # Основные настройки подключения
    name = models.CharField(
        max_length=100, 
        unique=True,
        verbose_name="Название настройки",
        help_text="Уникальное название для этого набора настроек"
    )
    
    # Настройки терминала
    terminal_path = models.CharField(
        max_length=500,
        verbose_name="Путь к терминалу MT5",
        help_text="Полный путь к исполняемому файлу terminal64.exe",
        blank=True,
        null=True
    )
    
    # Настройки сервера
    server = models.CharField(
        max_length=100,
        verbose_name="Сервер",
        help_text="Название торгового сервера (например: MetaQuotes-Demo)",
        blank=True
    )
    
    # Учетные данные
    login = models.BigIntegerField(
        verbose_name="Логин",
        help_text="Номер торгового счета",
        null=True,
        blank=True
    )
    
    password = models.CharField(
        max_length=100,
        verbose_name="Пароль",
        help_text="Пароль торгового счета",
        blank=True
    )
    
    # Настройки подключения
    timeout = models.IntegerField(
        default=60000,
        verbose_name="Таймаут (мс)",
        help_text="Таймаут подключения в миллисекундах"
    )
    
    portable = models.BooleanField(
        default=False,
        verbose_name="Портативный режим",
        help_text="Запуск терминала в портативном режиме"
    )
    
    # Статус и управление
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активно",
        help_text="Использовать эти настройки для подключения"
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name="По умолчанию",
        help_text="Использовать как настройки по умолчанию"
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено"
    )
    
    # Дополнительные настройки
    notes = models.TextField(
        blank=True,
        verbose_name="Заметки",
        help_text="Дополнительная информация о настройках"
    )
    
    # Торговая информация (обновляется автоматически)
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Баланс",
        help_text="Текущий баланс счета"
    )
    
    equity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Эквити",
        help_text="Текущее эквити счета"
    )
    
    last_connection_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последнее подключение",
        help_text="Время последнего успешного подключения"
    )
    
    # Параметр data_dir удалён из MT5ConnectionSettings — директория выбирается на уровне TradingSystem
    class Meta:
        verbose_name = "Настройки MT5"
        verbose_name_plural = "Настройки MT5"
        ordering = ['-is_default', '-is_active', 'name']

    def __str__(self):
        status = "🟢" if self.is_active else "🔴"
        default = " (по умолчанию)" if self.is_default else ""
        return f"{status} {self.name}{default}"

    def clean(self):
        """Валидация модели"""
        super().clean()
        
        # Проверяем, что есть только одна настройка по умолчанию
        if self.is_default:
            existing_default = MT5ConnectionSettings.objects.filter(
                is_default=True
            ).exclude(pk=self.pk)
            
            if existing_default.exists():
                raise ValidationError(
                    "Только одна настройка может быть установлена по умолчанию"
                )

    def save(self, *args, **kwargs):
        """Переопределяем save для обеспечения единственности default"""
        if self.is_default:
            # Убираем флаг default у всех остальных записей
            MT5ConnectionSettings.objects.filter(
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)

    @classmethod
    def get_default_settings(cls):
        """Получить настройки по умолчанию"""
        try:
            return cls.objects.filter(is_default=True, is_active=True).first()
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_active_settings(cls):
        """Получить все активные настройки"""
        return cls.objects.filter(is_active=True)


class MT5ConnectionLog(models.Model):
    """Модель для логирования подключений к MT5"""
    
    settings = models.ForeignKey(
        MT5ConnectionSettings,
        on_delete=models.CASCADE,
        verbose_name="Настройки"
    )
    
    connection_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время подключения"
    )
    
    success = models.BooleanField(
        verbose_name="Успешно"
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name="Сообщение об ошибке"
    )
    
    account_info = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Информация о счете"
    )

    class Meta:
        verbose_name = "Лог подключения MT5"
        verbose_name_plural = "Логи подключений MT5"
        ordering = ['-connection_time']

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.settings.name} - {self.connection_time.strftime('%d.%m.%Y %H:%M')}"


class MT5ConnectionHealth(models.Model):
    """Model for tracking MT5 connection health over time"""
    
    settings = models.ForeignKey(
        MT5ConnectionSettings,
        on_delete=models.CASCADE,
        verbose_name="Connection Settings",
        related_name="health_records"
    )
    
    check_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Check Time"
    )
    
    is_connected = models.BooleanField(
        verbose_name="Is Connected"
    )
    
    ping_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Ping (ms)",
        help_text="Connection response time in milliseconds"
    )
    
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Account Balance"
    )
    
    equity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Account Equity"
    )
    
    margin = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Used Margin"
    )
    
    error_message = models.TextField(
        blank=True,
        verbose_name="Error Message"
    )
    
    class Meta:
        verbose_name = "MT5 Connection Health Record"
        verbose_name_plural = "MT5 Connection Health Records"
        ordering = ['-check_time']
        indexes = [
            models.Index(fields=['settings', '-check_time']),
            models.Index(fields=['is_connected', '-check_time']),
        ]
    
    def __str__(self):
        status = "🟢" if self.is_connected else "🔴"
        return f"{status} {self.settings.name} - {self.check_time.strftime('%H:%M:%S')}"


class MT5MonitoringSettings(models.Model):
    """Global settings for MT5 monitoring system"""
    
    # Monitoring intervals
    health_check_interval = models.IntegerField(
        default=30,
        verbose_name="Health Check Interval (seconds)",
        help_text="How often to check connection health"
    )
    
    reconnect_interval = models.IntegerField(
        default=60,
        verbose_name="Reconnect Interval (seconds)",
        help_text="How often to attempt reconnection when disconnected"
    )
    
    max_reconnect_attempts = models.IntegerField(
        default=5,
        verbose_name="Max Reconnect Attempts",
        help_text="Maximum number of consecutive reconnection attempts"
    )
    
    # Alerting settings
    enable_email_alerts = models.BooleanField(
        default=False,
        verbose_name="Enable Email Alerts"
    )
    
    alert_email = models.EmailField(
        blank=True,
        verbose_name="Alert Email Address"
    )
    
    # Data retention
    health_records_retention_days = models.IntegerField(
        default=30,
        verbose_name="Health Records Retention (days)",
        help_text="How long to keep health check records"
    )
    
    # Monitoring control
    monitoring_enabled = models.BooleanField(
        default=True,
        verbose_name="Enable Monitoring",
        help_text="Enable/disable the entire monitoring system"
    )
    
    auto_reconnect_enabled = models.BooleanField(
        default=True,
        verbose_name="Enable Auto-Reconnect",
        help_text="Automatically attempt to reconnect when connection is lost"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated"
    )
    
    class Meta:
        verbose_name = "MT5 Monitoring Settings"
        verbose_name_plural = "MT5 Monitoring Settings"
    
    def __str__(self):
        status = "🟢" if self.monitoring_enabled else "🔴"
        return f"{status} MT5 Monitoring Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create monitoring settings"""
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'health_check_interval': 30,
                'reconnect_interval': 60,
                'max_reconnect_attempts': 5,
                'monitoring_enabled': True,
                'auto_reconnect_enabled': True,
            }
        )
        return settings


class TradingSystem(models.Model):
    """Модель для настройки торговых систем TradeStation"""
    
    # Идентификатор системы
    system_sid = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="System ID",
        help_text="Краткое название системы (например: DOTBIN, TestSys)"
    )
    
    # Название системы
    name = models.CharField(
        max_length=200,
        verbose_name="Название системы",
        help_text="Полное описательное название торговой системы"
    )
    
    # Валютная пара
    symbol = models.CharField(
        max_length=20,
        default="EURUSD"
    )

    # System trading controls
    trading_enabled = models.BooleanField(
        default=False,
        verbose_name='Allow Trading',
        help_text='If enabled, signals may execute real trades for this system'
    )
    is_sar = models.BooleanField(
        default=True,
        verbose_name='SAR (Stop & Reverse)',
        help_text='If enabled, OPEN signals reverse the position (close opposite side)'
    )
    lot_size = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.01,
        verbose_name='Lot Size',
        help_text='Default lot size to use for trades (e.g., 0.01)'
    )

    # MT5 magic number mapping for this system (optional)
    magic_number = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Magic Number',
        help_text='MT5 Expert Advisor magic number for mapping/filtering'
    )
    
    # Количество уровней таймфреймов
    timeframes_count = models.PositiveIntegerField(
        verbose_name="Количество таймфреймов",
        help_text="Сколько разных таймфреймов использует система",
        default=1
    )
    
    # Сдвиг времени
    time_offset_minutes = models.IntegerField(
        verbose_name="Сдвиг времени (минуты)",
        help_text="Сдвиг времени в минутах (может быть отрицательным)",
        default=0
    )
    
    # Активность системы
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
        help_text="Обрабатывать ли данные этой системы"
    )
    
    # Дополнительная информация
    description = models.TextField(
        blank=True,
        verbose_name="Описание",
        help_text="Подробное описание торговой системы"
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено"
    )
    
    class Meta:
        verbose_name = "Торговая система"
        verbose_name_plural = "Торговые системы"
        ordering = ['system_sid']
    
    def __str__(self):
        return f"{self.system_sid} - {self.symbol} ({self.timeframes_count} TF)"
    
    def get_expected_files_count(self):
        """Возвращает ожидаемое количество файлов для системы"""
        return self.timeframes_count
    
    def get_file_pattern(self):
        """Возвращает паттерн имён файлов для системы"""
        return f"collector_{self.system_sid}_{self.symbol}_*.csv"

    # Полный путь к папке с CSV для этой системы
    data_dir = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Папка с данными",
        help_text="Полный путь к папке, где искать файлы системы. Если пусто, используется глобальная TS_EXPORTS_DIR."
    )

    def get_data_dir(self):
        from django.conf import settings as django_settings
        return self.data_dir or getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS')

class TradingSystemSignalSettings(models.Model):
    """Per-system signal logic configuration."""

    trading_system = models.OneToOneField(
        TradingSystem,
        on_delete=models.CASCADE,
        related_name='signal_settings',
        verbose_name='Trading System'
    )
    signal_logic = models.TextField(
        blank=True,
        verbose_name='Signal Logic (IF/THEN/ELSE)',
        help_text='Rules DSL, e.g., IF cond THEN BUY ELSE NONE'
    )
    signal_base_tf_level = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Base TF Level',
        help_text='TF level to evaluate rules on (1=M1, 2=M2, ...). Optional.'
    )
    signal_indicators = models.TextField(
        blank=True,
        verbose_name='Indicators Description',
        help_text='List/mapping of indicator names and their TFs available in rules'
    )
    use_global_feed = models.BooleanField(
        default=False,
        verbose_name='Use Global Feed',
        help_text='If enabled, rules read data from provider-agnostic global feed with TF level bindings'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated')

    class Meta:
        verbose_name = 'Signal Settings'
        verbose_name_plural = 'Signal Settings'

    def __str__(self):
        return f"Signal Settings for {self.trading_system.system_sid}"

class TimeFrame(models.Model):
    """Модель для описания таймфреймов торговой системы"""
    
    TIMEFRAME_CHOICES = [
        ('M1', '1 Minute'),
        ('M2', '2 Minutes'),
        ('M5', '5 Minutes'),
        ('M15', '15 Minutes'),
        ('M30', '30 Minutes'),
        ('H1', '1 Hour'),
        ('H4', '4 Hours'),
        ('D1', '1 Day'),
        ('W1', '1 Week'),
        ('MN1', '1 Month'),
    ]
    
    # Связь с торговой системой
    trading_system = models.ForeignKey(
        TradingSystem,
        on_delete=models.CASCADE,
        related_name='timeframes',
        verbose_name="Торговая система"
    )
    
    # Таймфрейм
    timeframe = models.CharField(
        max_length=10,
        choices=TIMEFRAME_CHOICES,
        verbose_name="Таймфрейм"
    )
    
    # Уровень важности (для сортировки)
    level = models.PositiveIntegerField(
        verbose_name="Уровень",
        help_text="Уровень важности таймфрейма (1 - самый важный)"
    )
    
    # Активность
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    
    class Meta:
        verbose_name = "Таймфрейм"
        verbose_name_plural = "Таймфреймы"
        unique_together = ['trading_system', 'timeframe']
        ordering = ['trading_system', 'level']
    
    def __str__(self):
        return f"{self.trading_system.system_sid} - {self.timeframe} (L{self.level})"
    
    def get_filename_pattern(self):
        """Возвращает паттерн имени файла для данного таймфрейма"""
        return f"collector_{self.trading_system.system_sid}_{self.trading_system.symbol}_{self.timeframe}.csv"


class TradingSystemTFBinding(models.Model):
    """Bind a system logical TF level (L1/L2/...) to a global DataFeed."""

    trading_system = models.ForeignKey(TradingSystem, on_delete=models.CASCADE, related_name='tf_bindings')
    level = models.PositiveIntegerField()
    feed = models.ForeignKey('DataFeed', on_delete=models.CASCADE, related_name='system_bindings')

    class Meta:
        unique_together = [('trading_system', 'level')]
        indexes = [
            models.Index(fields=['trading_system', 'level']),
        ]
        verbose_name = 'TF Binding'
        verbose_name_plural = 'TF Bindings'

    def __str__(self):
        return f"{self.trading_system.system_sid}: L{self.level} -> {self.feed}"




class SignalEvent(models.Model):
    DIRECTION_CHOICES = [
        ('BUY', 'BUY'),
        ('SELL', 'SELL'),
    ]

    trading_system = models.ForeignKey(TradingSystem, on_delete=models.CASCADE, related_name='signals', verbose_name='Trading System')
    timeframe = models.ForeignKey(TimeFrame, on_delete=models.SET_NULL, null=True, blank=True, related_name='signals', verbose_name='Timeframe')
    # Global-feed fields
    level = models.PositiveIntegerField(default=1, verbose_name='TF Level')
    feed = models.ForeignKey('DataFeed', on_delete=models.SET_NULL, null=True, blank=True, related_name='signal_events')
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES)
    action = models.CharField(
        max_length=8,
        choices=[('OPEN', 'OPEN'), ('CLOSE', 'CLOSE')],
        default='OPEN'
    )
    rule_text = models.TextField(blank=True)
    event_time = models.DateTimeField(verbose_name='Event Time')
    created_at = models.DateTimeField(auto_now_add=True)
    ind_values = models.JSONField(null=True, blank=True, verbose_name='Indicator values')

    class Meta:
        ordering = ['-event_time']
        indexes = [
            models.Index(fields=['trading_system', 'level', '-event_time']),
            models.Index(fields=['feed', '-event_time']),
            models.Index(fields=['direction', 'action', '-event_time']),
        ]
        unique_together = [('trading_system', 'level', 'event_time', 'direction', 'action')]

    def __str__(self):
        lvl = getattr(self, 'level', None) or 1
        return f"{self.trading_system.system_sid}:L{lvl} {self.direction}/{self.action} @ {self.event_time:%Y-%m-%d %H:%M:%S}"


class SignalExecutionLog(models.Model):
    signal = models.OneToOneField(SignalEvent, on_delete=models.CASCADE, related_name='execution')
    executed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    message = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['-executed_at']),
        ]

class DataIngestionStatus(models.Model):
    """Singleton-like model to track data ingestion worker status and KPIs."""

    active = models.BooleanField(default=False)
    scan_interval = models.PositiveIntegerField(default=5, help_text='Scan interval in seconds')
    last_run = models.DateTimeField(null=True, blank=True)
    files_scanned = models.PositiveIntegerField(default=0)
    files_imported = models.PositiveIntegerField(default=0)
    rows_imported = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Data Ingestion Status'
        verbose_name_plural = 'Data Ingestion Status'

    def __str__(self):
        return f"Ingestion: {'ON' if self.active else 'OFF'} (interval {self.scan_interval}s)"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

# ImportLog removed in global-only mode


# ============================================================================
# Global Market Data (provider-agnostic feed layer)
# ============================================================================

class Instrument(models.Model):
    """Tradeable instrument (e.g., EURUSD)."""

    symbol = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['symbol']

    def __str__(self):
        return self.symbol


class TFCode(models.Model):
    """Timeframe code (M1, M5, H1, ...)."""

    code = models.CharField(max_length=10, unique=True)
    minutes = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['minutes']

    def __str__(self):
        return self.code


class DataFeed(models.Model):
    """Data feed per provider × instrument × timeframe."""

    provider = models.CharField(max_length=32, default='TS')
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name='feeds')
    tfcode = models.ForeignKey(TFCode, on_delete=models.CASCADE, related_name='feeds')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [('provider', 'instrument', 'tfcode')]
        indexes = [
            models.Index(fields=['provider', 'instrument']),
            models.Index(fields=['instrument', 'tfcode']),
        ]

    def __str__(self):
        return f"{self.provider}:{self.instrument.symbol}@{self.tfcode.code}"


class MarketBar(models.Model):
    """Global market bar row."""

    feed = models.ForeignKey(DataFeed, on_delete=models.CASCADE, related_name='bars')
    dt = models.DateTimeField()
    dt_server = models.DateTimeField(null=True, blank=True)
    open = models.DecimalField(max_digits=16, decimal_places=6)
    high = models.DecimalField(max_digits=16, decimal_places=6)
    low = models.DecimalField(max_digits=16, decimal_places=6)
    close = models.DecimalField(max_digits=16, decimal_places=6)
    volume = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('feed', 'dt')]
        indexes = [
            models.Index(fields=['feed', '-dt']),
            models.Index(fields=['-dt']),
        ]

    def __str__(self):
        # Display dt in project timezone to match admin list field rendering
        try:
            from django.utils import timezone as dj_tz
            dt_local = dj_tz.localtime(self.dt) if dj_tz.is_aware(self.dt) else self.dt
        except Exception:
            dt_local = self.dt
        return f"{self.feed} {dt_local:%Y-%m-%d %H:%M}"


class MarketIndicatorDef(models.Model):
    """Indicator definition scoped to a DataFeed."""

    feed = models.ForeignKey(DataFeed, on_delete=models.CASCADE, related_name='indicators')
    name = models.CharField(max_length=64)
    dtype = models.CharField(max_length=16, default='numeric')
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [('feed', 'name')]
        indexes = [
            models.Index(fields=['feed', 'name']),
        ]

    def __str__(self):
        return f"{self.feed}:{self.name}"


class MarketIndicatorValue(models.Model):
    """Indicator value for a MarketBar."""

    bar = models.ForeignKey(MarketBar, on_delete=models.CASCADE, related_name='indicator_values')
    indicator = models.ForeignKey(MarketIndicatorDef, on_delete=models.CASCADE, related_name='values')
    value_int = models.IntegerField(null=True)

    class Meta:
        unique_together = [('bar', 'indicator')]
        indexes = [
            models.Index(fields=['indicator', 'bar']),
        ]


class MarketDataFile(models.Model):
    """File tracking for global feed ingestion."""

    provider = models.CharField(max_length=32, default='TS')
    instrument = models.ForeignKey(Instrument, on_delete=models.SET_NULL, null=True, blank=True)
    tfcode = models.ForeignKey(TFCode, on_delete=models.SET_NULL, null=True, blank=True)
    feed = models.ForeignKey(DataFeed, on_delete=models.SET_NULL, null=True, blank=True)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_modified = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['provider', 'filename']),
            models.Index(fields=['feed', '-file_modified']),
        ]

    def __str__(self):
        return f"{self.provider}:{self.filename} ({self.status})"
