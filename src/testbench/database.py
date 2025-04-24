from peewee import CharField, DateTimeField, Model
from playhouse.sqlite_ext import JSONField  # pyright: ignore [reportMissingTypeStubs]

from testbench.context import Context

context = Context.get()
logger = context.logger


class Status(Model):
    on = DateTimeField()
    kind = CharField()
    params = JSONField(default={})
    results = JSONField(defaul={})

    class Meta:
        database = context.db
