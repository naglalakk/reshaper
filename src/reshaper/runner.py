import redis
from progressbar import ProgressBar, Bar, Percentage, RotatingMarker, FileTransferSpeed, ETA, Counter
from .manager import Manager


class Runner():
    def __init__(self, source_db, destination_db, cache=False):
        self.mwidgets = [ 
            Percentage(), ' ', 
            Bar(marker=RotatingMarker()),' ',
            Counter(), ' ',
            ETA(), ' ', 
        ]
        self.cache = None
        if cache:
            self.cache = redis.StrictRedis(
                host='localhost',
                port=6379,
                db=0
            )
        self.source_db = source_db
        self.destination_db = destination_db
        self.manager = Manager(
            source_db=source_db,
            destination_db=destination_db
        )

    def run(self, transformer, query=''):
        last_source_index = 0
        last_destination_index = 0
        count = 0
        transformer_name = transformer.__class__.__name__

        if self.cache:
            if not query:
                query = 'WHERE id >'
            last_source_index = self.cache.get(
                '%s_last_source_index' % transformer_name
            )
            last_destination_index = self.cache.get(
                '%s_last_destination_index' % transformer_name
            )
            query = '%s %s' % (query, last_source_index)

        source_table = transformer.source_table
        row_len = self.source_db.get_table_row_count(
            source_table, query
        )
        pbar = ProgressBar(
            widgets = self.mwidgets,
            maxval = row_len
        ).start()
        
        print("%s - Transforming %i objects" % (transformer_name, row_len))

        cursor = self.source_db.cursor()
        cursor.execute(
            """ SELECT * FROM %s %s""" % (source_table, query)
        )

        for row in cursor:
            last_destination_index = self.manager.transform(
                transformer, row
            )
            last_source_index = row.get('id')
            count += 1
            pbar.update(count)

        if self.cache:
            self.cache.set(
                '%s_last_source_index' % transformer_name,
                last_source_index
            )
            self.cache.set(
                '%s_last_destination_index' % transformer_name,
                last_destination_index
            )
        pbar.finish()
