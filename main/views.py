from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def home(request):
    """Главная страница проекта GCE_3"""
    return HttpResponse("""
    <html>
        <head>
            <title>Project GCE 3</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                h1 { color: #2c3e50; }
                .info { background: #ecf0f1; padding: 20px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Добро пожаловать в Project GCE 3!</h1>
                <div class="info">
                    <p><strong>Django успешно установлен и работает!</strong></p>
                    <p>Этот базовый фреймворк готов к разработке.</p>
                    <p>Структура проекта:</p>
                    <ul>
                        <li>Django проект: <code>gce_project</code></li>
                        <li>Основное приложение: <code>main</code></li>
                        <li>Виртуальная среда активна</li>
                        <li>Git репозиторий настроен</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """)

def about(request):
    """Страница о проекте"""
    return HttpResponse("""
    <html>
        <head>
            <title>О проекте GCE 3</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                h1 { color: #2c3e50; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>О проекте Project GCE 3</h1>
                <p>Этот проект создан с использованием Django и готов к дальнейшей разработке.</p>
                <a href="/">← Вернуться на главную</a>
            </div>
        </body>
    </html>
    """)
