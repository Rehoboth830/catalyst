
def parse_pg_uuid_array(pg_str):
    '''Postgres returns uuid[] via psycopg2 as a raw string like {id1,id2}, not a list.'''
    if not pg_str or pg_str == "{}":
        return set()
    return set(pg_str.strip("{}").split(","))
