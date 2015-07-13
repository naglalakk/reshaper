from progressbar import ProgressBar, Bar, Percentage
from .transformers import *

class Manager:
    def __init__(self, source_db=None, destination_db=None):
        self.source_db = source_db
        self.destination_db = destination_db
        self.transformers = [] 
        self.cache = []
        self.stats = False
        self.mwidgets = [Bar('=','[',']'),' ',Percentage()]

    def add_transformer(self, transformer):
        self.transformers.append(transformer)

    def get_from_unique(self, table, unique, value, db='source_db'):
        dest_db = self.source_db
        if db == 'destination_db':
            dest_db = self.destination_db

        return dest_db.get_row_from_field(
            table, unique, value
        )

    def add_relation(self, table, data):
        """
        Adds relation data to table cache
        """
        self.cache.append({table:data})

    def resolve_relationtransformerfield(self, field, value, transformers):
        """
        Resolve a RelationTransformerField
        """
        
        if type(transformers) is not list:
            transformers = [transformers]

        for transformer in transformers:
            if transformer.source_table:
                row = self.source_db.get_row_from_pk(
                    transformer.source_table,
                    value
                )
                transformer.set_values(row)
            data = self.insert(transformer)
            if transformer.commit:
                self.add_relation(
                    field.relation_table,
                    {transformer.destination_id: data.get('id')}
                )
            else:
                self.add_relation(field.relation_table, data)
        return 0

    def resolve_subtransformerfield(self, field, value, transformer):
        """
        Resolve SubTransformerField (foreign keys)
        """
        pk = 0

        if transformer.source_table:
            row = self.source_db.get_row_from_pk(
                transformer.source_table,
                value
            )
        else:
            row = transformer.to_dict()
        if not field.create:
            if transformer.unique:
                unique_value = row.get(transformer.unique)
                dest_row = self.get_from_unique(
                    transformer.destination_table,
                    transformer.unique,
                    unique_value,
                    db='destination_db'
                )
                pk = dest_row.get('id')
        else:
            transformer.set_values(row)
            pk = self.insert(transformer).get('id')
        return pk

    def insert(self, transformer):
        """
        Insert a single row from resolved transformer data

        :param Transformer transformer: Transformer object
        :param dict row: Transformed data

        :return: A dictionary containing id: primary_key if data was commited, otherwise a dictionary containing transformed columns
        """
        pk = None
        transformed = {}
        for key, value in transformer.to_dict().items():
            field = transformer.to_field(key)
            if field:
                if isinstance(field, RelationTransformerField):
                    pk = self.resolve_relationtransformerfield(
                        field,
                        value,
                        field.transform(transformer)
                    )
                elif isinstance(field, SubTransformerField):
                    pk = self.resolve_subtransformerfield(
                        field,
                        value,
                        field.transform(transformer)
                    )
                    transformed[key] = pk
                elif isinstance(field, TransformerField):
                    transformed[key] = value
        if transformer.commit:
            if pk != 0:
                pk = self.destination_db.insert_single(
                    transformer.destination_table, transformed
                )
                return pk
        else:
            return transformed

    def transform(self, transformer):
        """
        Performs transformation of all fields declared
        in transformer

        :param Transformer transformer: Transformer object
        """
        count = 0
        source_table = transformer.source_table
        rows = self.source_db.get_table_rows(source_table)
        if self.stats:
            pbar = ProgressBar(
                widgets=self.mwidgets, 
                maxval=len(rows)
            ).start()
            print("%s - Transforming %i objects" % (
                transformer.__class__.__name__,len(rows)
            ))
        for row in rows:
            row.pop('id')
            transformer.set_values(row)
            pk = self.insert(transformer)
            if self.cache:
                for relation in self.cache:
                    for key,value in relation.items():
                        table = key
                        value[transformer.destination_id] = pk
                        self.destination_db.insert_single(
                            table, value
                        )
                self.cache = []
            if self.stats:
                count += 1
                pbar.update(count)

        if self.stats:
            pbar.finish()

    def transformAll(self):
        for transformer in self.transformers:
            self.transform(transformer)
