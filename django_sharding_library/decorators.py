from django.conf import settings

from django_sharding_library.exceptions import NonExistentDatabaseException, ShardedModelInitializationException
from django_sharding_library.fields import ShardedIDFieldMixin
from django_sharding_library.manager import ShardManager
from django.db.models import Manager


def model_config(shard_group=None, database=None, sharded_by_field=None):
    """
    A decorator for marking a model as being either sharded or stored on a
    particular database. When sharding, it does some verification to ensure
    that the model is defined correctly.
    """
    def configure(cls):
        if database and shard_group:
            raise ShardedModelInitializationException('A model cannot be both sharded and stored on a particular database.')

        if not database and not shard_group:
            raise ShardedModelInitializationException('The model should be either sharded or stored on a database in the `model_config` decorator is used.')

        if database:
            if database not in settings.DATABASES or settings.DATABASES[database].get('PRIMARY'):
                raise NonExistentDatabaseException(
                    'Unable to place {} in {} as that is not an existing primary database in the system.'.format(cls._meta.model_name, database)
                )
            setattr(cls, 'django_sharding__database', database)

        if shard_group:
            sharded_fields = list(filter(lambda field: issubclass(type(field), ShardedIDFieldMixin), cls._meta.fields))
            if not sharded_fields:
                raise ShardedModelInitializationException('All sharded models require a ShardedIDFieldMixin.')

            if not list(filter(lambda field: field == cls._meta.pk, sharded_fields)):
                raise ShardedModelInitializationException('All sharded models require the ShardedAutoIDField to be the primary key. Set primary_key=True on the field.')

            if not callable(getattr(cls, 'get_shard', None)):
                raise ShardedModelInitializationException('You must define a get_shard method on the sharded model.')

            setattr(cls, 'django_sharding__shard_group', shard_group)
            setattr(cls, 'django_sharding__is_sharded', True)

            # If the sharded by field is set, we will make our custom manager the default manager.
            if sharded_by_field:
                try:
                    if not isinstance(cls.objects, ShardManager):
                        if type(cls.objects) == Manager:
                            cls.add_to_class('objects', ShardManager())
                            cls._base_manager = cls.objects
                        else:
                            raise ShardedModelInitializationException('You must use the default Django model manager or'
                                                                      ' your custom manager must inherit from '
                                                                      '``ShardManager``')
                except AttributeError as e:
                    if cls._meta.abstract:
                        if not len(cls._meta.abstract_managers) > 0:
                            cls.add_to_class('objects', ShardManager())
                        elif not any([isinstance(x[2], ShardManager) for x in cls._meta.abstract_managers]):
                            raise ShardedModelInitializationException('Please either do not specify a manager in your '
                                                                      'abstract base class %s, or if you are using a '
                                                                      'custom manager, your custom manager must '
                                                                      'inherit from ``ShardManager``' % cls.__name__)
                    else:
                        # If it gets to this point, the error is a Django error and not a library one. Pass it through.
                        raise e
                setattr(cls, 'django_sharding__sharded_by_field', sharded_by_field)
                if not callable(getattr(cls, 'get_shard_from_id', None)):
                    raise ShardedModelInitializationException('You must define a get_shard_from_id method on the '
                                                              'sharded model if you define a "sharded_by_field".')

        return cls
    return configure
