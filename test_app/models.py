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


class Organization(models.Model):
    """A stand-in tenant, shaped like the real one (id + slug)."""

    slug = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.slug


class ScopedThing(models.Model):
    """A model owning its organization directly."""

    name = models.CharField(max_length=100)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="things"
    )


class NestedThing(models.Model):
    """A model reaching its organization through a required FK."""

    name = models.CharField(max_length=100)
    thing = models.ForeignKey(
        ScopedThing, on_delete=models.CASCADE, related_name="nested"
    )


class NullableThing(models.Model):
    """A model whose only route to an organization is a NULLABLE FK.

    The walk must refuse this: filtering across a nullable path would silently
    drop rows whose FK is NULL rather than scope them.
    """

    name = models.CharField(max_length=100)
    thing = models.ForeignKey(
        ScopedThing, on_delete=models.CASCADE, null=True, blank=True
    )


class OrphanThing(models.Model):
    """A model with no route to an organization at all."""

    name = models.CharField(max_length=100)
