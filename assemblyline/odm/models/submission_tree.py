from assemblyline import odm

# TODO: Apply proper index and store values


@odm.model(index=True, store=True)
class File(odm.Model):
    depth = odm.Integer()           # Depth in the tree
    file_id = odm.Integer()         # ID of the file
    name = odm.List(odm.Keyword())  # Name of the file
    parent_id = odm.Integer()       # ID of the parent file
    score = odm.Integer()           # Score of the file
    sha256 = odm.Keyword()          # SHA256 hash of the file
    truncated = odm.Boolean()       # is the file truncated


@odm.model(index=True, store=True)
class SubmissionTree(odm.Model):
    expiry_ts = odm.Date()               # Expiry date
    sid = odm.Keyword()                  # Submission ID of the tree
    tree = odm.List(odm.Compound(File))  # List of files
