"""
Сервис для обработки CSV файлов TradeStation и их конвертации в JSON
согласно конфигурации торговых систем
"""

import csv
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from django.utils import timezone
from django.conf import settings as django_settings
from ..models import TradingSystem, TimeFrame, DataFile


class CSVProcessor:
    """Класс для обработки CSV файлов из TradeStation"""
    
    def __init__(self, trading_system: TradingSystem):
        """
        Инициализация процессора CSV
        
        Args:
            trading_system: Экземпляр модели TradingSystem
        """
        self.trading_system = trading_system
        # Prefer per-system directory, fallback to global setting
        try:
            self.csv_exports_path = trading_system.get_data_dir()
        except Exception:
            self.csv_exports_path = getattr(django_settings, 'TS_EXPORTS_DIR', r'C\\TS_EXPORTS')
    
    def detect_delimiter(self, file_path: str) -> str:
        """
        Определяет разделитель в CSV файле
        
        Args:
            file_path: Путь к CSV файлу
            
        Returns:
            Символ разделителя
        """
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                sample = file.read(1024)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                return delimiter
        except Exception:
            return ','  # Разделитель по умолчанию
    
    def validate_csv_file(self, filename: str) -> Dict[str, Any]:
        """
        Валидирует CSV файл согласно конфигурации торговой системы
        
        Args:
            filename: Имя CSV файла
            
        Returns:
            Словарь с результатами валидации
        """
        file_path = os.path.join(self.csv_exports_path, filename)
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'File not found: {filename}'
            }
        
        try:
            delimiter = self.detect_delimiter(file_path)
            
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file, delimiter=delimiter)
                
                # Читаем заголовки
                try:
                    headers = next(reader)
                except StopIteration:
                    return {
                        'success': False,
                        'error': 'CSV file is empty'
                    }
                
                # Результаты валидации для каждого таймфрейма
                validation_results = []
                
                for timeframe in self.trading_system.timeframes.all():
                    result = self._validate_timeframe(timeframe, headers)
                    validation_results.append(result)
                
                # Читаем несколько строк для примера
                file.seek(0)
                reader = csv.reader(file, delimiter=delimiter)
                next(reader)  # Пропускаем заголовки
                
                sample_data = []
                for i, row in enumerate(reader):
                    if i >= 5:  # Только первые 5 строк
                        break
                    if row:
                        sample_data.append(row)
                
                return {
                    'success': True,
                    'filename': filename,
                    'headers': headers,
                    'sample_data': sample_data,
                    'validation_results': validation_results,
                    'is_valid': all(result['valid'] for result in validation_results),
                    'delimiter': delimiter
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Error reading CSV file: {str(e)}'
            }
    
    def _validate_timeframe(self, timeframe: TimeFrame, headers: List[str]) -> Dict[str, Any]:
        """
        Валидирует таймфрейм против заголовков CSV
        
        Args:
            timeframe: Экземпляр модели TimeFrame
            headers: Список заголовков CSV файла
            
        Returns:
            Результат валидации таймфрейма
        """
        result = {
            'timeframe_id': timeframe.id,
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Проверяем обязательные колонки
        required_columns = []
        
        if timeframe.open_column:
            required_columns.append(timeframe.open_column)
        if timeframe.high_column:
            required_columns.append(timeframe.high_column)
        if timeframe.low_column:
            required_columns.append(timeframe.low_column)
        if timeframe.close_column:
            required_columns.append(timeframe.close_column)
        if timeframe.datetime_column:
            required_columns.append(timeframe.datetime_column)
        
        # Проверяем наличие колонок в заголовках
        missing_columns = [col for col in required_columns if col not in headers]
        
        if missing_columns:
            result['valid'] = False
            result['errors'].append(f'Missing required columns: {", ".join(missing_columns)}')
        
        # Проверяем объемы (опционально)
        if timeframe.volume_column and timeframe.volume_column not in headers:
            result['warnings'].append(f'Volume column "{timeframe.volume_column}" not found')
        
        return result
    
    def process_csv_to_json(self, filename: str, save_to_db: bool = True) -> Dict[str, Any]:
        """
        Обрабатывает CSV файл и конвертирует в JSON
        
        Args:
            filename: Имя CSV файла
            save_to_db: Сохранить результат в базу данных
            
        Returns:
            Словарь с обработанными данными
        """
        file_path = os.path.join(self.csv_exports_path, filename)
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f'File not found: {filename}'
            }
        
        try:
            # Сначала валидируем файл
            validation_result = self.validate_csv_file(filename)
            if not validation_result['success'] or not validation_result['is_valid']:
                return {
                    'success': False,
                    'error': 'CSV file validation failed',
                    'validation_result': validation_result
                }
            
            delimiter = validation_result['delimiter']
            
            # Структура для обработанных данных
            processed_data = {
                'system_info': {
                    'system_sid': self.trading_system.system_sid,
                    'name': self.trading_system.name,
                    'symbol': self.trading_system.symbol,
                    'timeframes_count': self.trading_system.timeframes_count,
                    'time_offset_minutes': self.trading_system.time_offset_minutes
                },
                'file_info': {
                    'filename': filename,
                    'processed_at': timezone.now().isoformat(),
                    'delimiter': delimiter
                },
                'timeframes': {}
            }
            
            # Обрабатываем каждый таймфрейм
            for timeframe in self.trading_system.timeframes.all():
                timeframe_data = self._process_timeframe_data(file_path, timeframe, delimiter)
                processed_data['timeframes'][f'timeframe_{timeframe.id}'] = timeframe_data
            
            # Сохраняем в базу данных если требуется
            if save_to_db:
                data_file, created = DataFile.objects.get_or_create(
                    trading_system=self.trading_system,
                    filename=filename,
                    defaults={
                        'file_path': file_path,
                        'json_data': processed_data,
                        'is_processed': True,
                        'processed_at': timezone.now()
                    }
                )
                
                if not created:
                    # Обновляем существующий файл
                    data_file.json_data = processed_data
                    data_file.is_processed = True
                    data_file.processed_at = timezone.now()
                    data_file.save()
                
                processed_data['data_file_id'] = data_file.id
            
            return {
                'success': True,
                'processed_data': processed_data,
                'total_records': sum(
                    len(tf['data']) for tf in processed_data['timeframes'].values()
                ),
                'filename': filename
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error processing CSV file: {str(e)}'
            }
    
    def _process_timeframe_data(self, file_path: str, timeframe: TimeFrame, delimiter: str) -> Dict[str, Any]:
        """
        Обрабатывает данные для конкретного таймфрейма
        
        Args:
            file_path: Путь к CSV файлу
            timeframe: Экземпляр модели TimeFrame
            delimiter: Разделитель CSV
            
        Returns:
            Обработанные данные таймфрейма
        """
        timeframe_data = {
            'config': {
                'open_column': timeframe.open_column,
                'high_column': timeframe.high_column,
                'low_column': timeframe.low_column,
                'close_column': timeframe.close_column,
                'volume_column': timeframe.volume_column,
                'datetime_column': timeframe.datetime_column,
                'datetime_format': timeframe.datetime_format
            },
            'data': [],
            'statistics': {
                'total_rows': 0,
                'valid_rows': 0,
                'invalid_rows': 0,
                'errors': []
            }
        }
        
        with open(file_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file, delimiter=delimiter)
            
            for row_number, row in enumerate(reader, start=2):  # Начинаем с 2, учитывая заголовки
                if not any(row.values()):  # Пропускаем пустые строки
                    continue
                
                timeframe_data['statistics']['total_rows'] += 1
                
                try:
                    # Формируем данные OHLC
                    ohlc_data = {}
                    
                    # Обрабатываем дату/время
                    if timeframe.datetime_column and timeframe.datetime_column in row:
                        datetime_value = row[timeframe.datetime_column]
                        if datetime_value:
                            # Применяем смещение времени если задано
                            if self.trading_system.time_offset_minutes:
                                try:
                                    if timeframe.datetime_format:
                                        dt = datetime.strptime(datetime_value, timeframe.datetime_format)
                                    else:
                                        dt = datetime.fromisoformat(datetime_value)
                                    
                                    # Добавляем смещение
                                    from datetime import timedelta
                                    dt += timedelta(minutes=self.trading_system.time_offset_minutes)
                                    ohlc_data['datetime'] = dt.isoformat()
                                except:
                                    ohlc_data['datetime'] = datetime_value
                            else:
                                ohlc_data['datetime'] = datetime_value
                    
                    # Обрабатываем OHLC данные
                    numeric_fields = [
                        ('open', timeframe.open_column),
                        ('high', timeframe.high_column),
                        ('low', timeframe.low_column),
                        ('close', timeframe.close_column),
                        ('volume', timeframe.volume_column)
                    ]
                    
                    for field_name, column_name in numeric_fields:
                        if column_name and column_name in row and row[column_name]:
                            try:
                                ohlc_data[field_name] = float(row[column_name])
                            except (ValueError, TypeError):
                                ohlc_data[field_name] = None
                                timeframe_data['statistics']['errors'].append(
                                    f'Row {row_number}: Invalid {field_name} value: {row[column_name]}'
                                )
                    
                    # Проверяем валидность данных
                    required_fields = ['open', 'high', 'low', 'close']
                    if all(ohlc_data.get(field) is not None for field in required_fields):
                        timeframe_data['data'].append(ohlc_data)
                        timeframe_data['statistics']['valid_rows'] += 1
                    else:
                        timeframe_data['statistics']['invalid_rows'] += 1
                        timeframe_data['statistics']['errors'].append(
                            f'Row {row_number}: Missing required OHLC data'
                        )
                    
                except Exception as e:
                    timeframe_data['statistics']['invalid_rows'] += 1
                    timeframe_data['statistics']['errors'].append(
                        f'Row {row_number}: Processing error: {str(e)}'
                    )
        
        return timeframe_data
    
    def get_available_csv_files(self) -> List[Dict[str, Any]]:
        """
        Получает список доступных CSV файлов в директории TS_EXPORTS
        
        Returns:
            Список CSV файлов с их свойствами
        """
        files = []
        
        if not os.path.exists(self.csv_exports_path):
            return files
        
        try:
            for filename in os.listdir(self.csv_exports_path):
                if filename.lower().endswith('.csv'):
                    file_path = os.path.join(self.csv_exports_path, filename)
                    file_stat = os.stat(file_path)
                    
                    # Проверяем, обработан ли уже этот файл
                    is_processed = DataFile.objects.filter(
                        trading_system=self.trading_system,
                        filename=filename,
                        is_processed=True
                    ).exists()
                    
                    files.append({
                        'filename': filename,
                        'size': file_stat.st_size,
                        'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        'is_processed': is_processed
                    })
            
            # Сортируем по дате модификации (новые сначала)
            files.sort(key=lambda x: x['modified'], reverse=True)
            
        except Exception as e:
            # Логируем ошибку, но возвращаем пустой список
            pass
        
        return files
    
    def get_processed_data(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Получает обработанные данные для файла из базы данных
        
        Args:
            filename: Имя CSV файла
            
        Returns:
            Обработанные данные или None если не найдены
        """
        try:
            data_file = DataFile.objects.get(
                trading_system=self.trading_system,
                filename=filename,
                is_processed=True
            )
            return data_file.json_data
        except DataFile.DoesNotExist:
            return None
