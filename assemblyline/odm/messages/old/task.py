from assemblyline import odm

MSG_TYPES = {"Task"}
LOADER_CLASS = "assemblyline.odm.messages.task.TaskMessage"


@odm.model()
class FileInfo(odm.Model):
    # ascii = odm.Text()      # Dot-escaped first 64 characters
    # hex = odm.Keyword()     # Hex dump of first 64 bytes
    # magic = odm.Keyword()   # The output from libmagic which was used to determine the tag
    # md5 = odm.Keyword()     # MD5 of the file
    mime = odm.Keyword()    # The libmagic mime type
    sha1 = odm.Keyword()    # SHA1 hash of the file
    sha256 = odm.Keyword()  # SHA256 hash of the file
    size = odm.Integer()    # Size of the file
    # tag = odm.Keyword()     # The file type or tag


@odm.model()
class Task(odm.Model):
    sid = odm.Keyword()
    fileinfo = odm.Compound(FileInfo)   # File info block
    service_name = odm.Keyword()
    service_config = odm.Keyword()      # Service specific parameters


@odm.model()
class TaskMessage(odm.Model):
    msg = odm.Compound(Task)                                            # Body of the message
    msg_loader = odm.Enum(values={LOADER_CLASS}, default=LOADER_CLASS)  # Class to use to load the message as an object
    msg_type = odm.Enum(values=MSG_TYPES, default="Task")               # Type of message
    sender = odm.Keyword()                                              # Sender of the message
