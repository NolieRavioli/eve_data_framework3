

the `io` module is a data persistence framework for the whole codebase. all data is encrypted at rest.  
It holds the data in accessible memory buffers that get copied to disk as fast as possible for persistent data storage.  
The data is stored in very fast duckDB files. There is one file for all public data, and there are 'entity_db's that are one file for each corp_id/alliance_id/character_id.

`io` has a framework for collectors and analysis tasks to define new tables themselves. There should be no need to modify any core systems to implement new analysis tables / esi collector tables.  
Also, analysis and collectors should be able to modify an existing table to create new fields (columns) for 'enrichment'.

`io/` has ephemeral writer and reader threads that are created and destroyed as needed.  
These threads work on individual databases. SINGLE database files only. There can be upto n active threads (`config.yml` assigned value)

writing data has a few different ways in which we handle data. I know these terms may not be standard but these are the different 'write states' i came up with off the dome:
 - bulk insertion where ALL current data is present in the new data (remove all old data (i.e. filtered rows OR whole table) and dumb wite all new data)
 - existing tables are passed rows containing new field(s) that dont already exist (create new table fields and write those fields with the given data)
 - known row may or may not get new data in one or more field(s)
 - row may or may not exist and may or may not get new data in one or more field(s)
 - non-existant row dumb appended

Reading data is also somewhat complicated:
 - data read requests will come into the `io` module as a database query.
 - RAM buffer AND duckDB must return any data that matches the database query.
 - there should be no duplicated data between the ram buffers and the written data.
 
 ---

data write requests or data read requests will enter the `io` module with some info:
 - what owner_id asked for this data write/read (`0` meaning SYSTEM, `-1` meaning SCHEDULER, etc. )
 - what task_id asked for this data write/read
 - which file will be written/read to?
 - what table will be written/read to?
 - for write tasks only:
   - what is the write method? (bulk insertion, existing row may or may not get new data in one or more fields, non-existant row dumb appended, row may or may not exist and may or may not get new data in one or more fields, etc...)
   - data to be written

---

the `io` module has a tracking feature that tracks the usage of reading and writing data (to/from RAM and to/from disk)
 - RAM usage is low cost. all writes into the ram buffer kind of costs the same amount per byte of data, right? there arent different operations that cost different amounts for the ram buffer writing process.
 - disk reading is also pretty low cost. just a flat 'usage per row' constant value i would think.
 - Writing to *disk*, however, will depend on how you actually write. Theres deletion, appending, overwriting, updating, etc.. that all have a different per-row cost.
 - Data is written to disk and the RAM buffer is emptied (only empty the buffer that had been written).
   - it is imparitive that we do not return duplicate data and that we do not miss data.

---

Here is how i imagine the flow (after initalization, before population of all tables):
1. a collector creates a table.
2. data enters `io` from the `core/esi` module through a collector (to be written to a given database).
3. data is added to a RAM buffer that is specific to the target database. a writer task is woken up to read the ram buffer fully.
4. the writer task reads the full RAM buffer and writes the database in the givem method.
5. reader task asks for data and data is returned from BOTH the ram buffers (if there is any) AND the database.

---

i imagine this:
```
io/
    __init__.py
    writer.py       # write data engine, functions and helpers
    reader.py       # read data engine, functions and helpers
    usage.py        # usage tracking engine via writer and reader
    modelEngine.py  # table framework engine functions and helpers invoked in core, collectors, and analysis.
    encryption.py   # database encryption functions and helpers
    public.py       # framework for _publicData/public.duckDB . Owns the file creation.
    entity.py       # framework for _privateData/*.duckDB . Owns the file creation.
```

remove the non-framework shit from `core/io/`.

You can read more about the rest of the system elsewhere in `development_active/`.
