from django.urls import path, re_path

from . import views

app_name = 'monitor'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('add/', views.AddMonitorView.as_view(), name='add'),
    path('graph/', views.GraphView.as_view(), name='graph'),
    re_path(r'^device/(?P<device_id>[0-9a-fA-F]+)$',
            views.DetailView.as_view(), name='detail'),
]
