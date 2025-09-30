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
