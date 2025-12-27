from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    user_id = models.CharField(max_length=11,unique=True,verbose_name="学工号")
    USERNAME_FIELD = 'user_id'

    REQUIRED_FIELDS = ['username']