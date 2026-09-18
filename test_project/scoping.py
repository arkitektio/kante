"""The test project's scoper, as a service would keep its own.

``TestModel`` has no organization and is served unscoped on purpose;
``OrphanThing`` has none either and is *not* declared, which is what a model
added without a tenancy story looks like.
"""

from kante.scoping import OrganizationScoper

scoper = OrganizationScoper(unscoped_models={"TestModel"})

reference_queryset = scoper.for_org
