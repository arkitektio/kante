from django.db import models

# Create your models here.


class TestModel(models.Model):
    """A simple test model."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Test Model"
        verbose_name_plural = "Test Models"
