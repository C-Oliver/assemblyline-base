from assemblyline import odm

RULE_STATUSES = {"DEPLOYED", "TESTING", "NOISY", "DISABLED", "STAGING", "INVALID"}
RULE_TYPES = {"rule", "private rule", "global rule", "global private rule"}
VALID_GROUPS = {"technique", "exploit", "implant", "info", "tool"}


@odm.model(index=True, store=True)
class RequiredMeta(odm.Model):
    al_status = odm.Enum(values=RULE_STATUSES)  # Status of the rule in Assemblyline
    classification = odm.Classification()       # Classification of the rule
    description = odm.Text(store=False)         # Description of the rule
    organisation = odm.Keyword(store=False)     # Organisation acronym which created the rule
    origin = odm.Keyword(store=False)           # Organisation acronym which created the rule
    poc = odm.Keyword()                         # Point of contact for the rule
    rule_group = odm.Enum(values=VALID_GROUPS)  # Group that the rule is part of
    rule_group_value = odm.Keyword()            # Value of the rule group (replaces: tech, info, implant ...)
    rule_id = odm.Keyword()                     # ID of the rule
    rule_version = odm.Integer()                # Version of the rule
    yara_verion = odm.Keyword()                 # Version of Yara the rule was built for


@odm.model(index=True, store=False)
class Signature(odm.Model):
    comments = odm.List(odm.Keyword())       # Comments for the signature
    condition = odm.Keyword()                # List of conditions for the signature
    depends = odm.List(odm.Keyword())        # other signature names that the signature depends on
    meta = odm.Compound(RequiredMeta)        # Required metadata
    meta_extra = odm.Mapping(odm.Keyword())  # Optional metadata
    modules = odm.List(odm.Keyword())        # Modules that the signature needs
    name = odm.Keyword(store=True)                     # Name of the signature
    strings = odm.Keyword()                  # Search strings for the signature
    tags = odm.List(odm.Keyword())           # Tags associated to the signature
    type = odm.Enum(values=RULE_TYPES)       # Type of rule
    warning = odm.Keyword()                  # Optimization warnings thrown by the yara process when the rule was tested
