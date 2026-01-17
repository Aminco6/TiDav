#from django.apps import AppConfig


#class UserdashboardConfig(AppConfig):
   # name = 'UserDashboard'
    
    
# apps.py
from django.apps import AppConfig

class UserDashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'UserDashboard'
    
   # def ready(self):
        #import UserDashboard.signals    
    
