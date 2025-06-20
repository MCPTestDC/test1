from psycopg2 import sql, pool, DatabaseError
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
import os
from typing import Dict, Any, Optional, Union
from enum import Enum

class ConfigurationError(Exception):
    pass

def get_config_value(db_key: str) -> str:
    prop_file = "database-props"
    db_value = os.getenv(db_key)
    if db_value is not None and db_value != "":
        return db_value
    else:
        if os.path.exists(prop_file):
            with open(prop_file, "r", encoding='utf-8') as config_file:
                for line in config_file:
                    key, _, value = line.strip().partition("=")
                    if key == db_key:
                        if not value:
                            raise ConfigurationError(f"Configuration value for '{db_key}' is empty.")
                        return value
                raise ConfigurationError(f"Configuration key '{db_key}' is not found.")
        else:
            raise ConfigurationError(f"Configuration file '{prop_file}' not found.")

DB_HOST = get_config_value("DB_HOST")
DB_NAME = get_config_value("DB_NAME")
DB_USER = get_config_value("DB_USER")
DB_PASSWORD = get_config_value("DB_PASSWORD")
DB_PORT = get_config_value("DB_PORT")

class HTTPMethod(str, Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"

db_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    port=DB_PORT
)

def get_db_connection():
    try:
        return db_pool.getconn()
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

def release_db_connection(conn):
    if conn:
        db_pool.putconn(conn)

def db_operation_handler(
    schema: str, 
    table: str, 
    http_method: HTTPMethod, 
    path_params: Optional[Dict[str, Any]] = None, 
    query_params: Optional[Dict[str, Any]] = None, 
    body_params: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, Any], list]:
    conn = None
    try:
        conn = get_db_connection()
        combined_params = {**(path_params or {}), **(query_params or {})}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            schema_table_name = sql.SQL("{}.{}").format(
                sql.Identifier(schema),
                sql.Identifier(table)
            )

            if http_method == HTTPMethod.POST:
                if not body_params:
                    raise HTTPException(status_code=400, detail="No data provided for POST operation.")
                
                columns = body_params.keys()
                values = list(body_params.values())

                insert_query = sql.SQL(
                    "INSERT INTO {table} ({fields}) VALUES ({placeholders}) RETURNING *"
                ).format(
                    table=schema_table_name,
                    fields=sql.SQL(', ').join(map(sql.Identifier, columns)),
                    placeholders=sql.SQL(', ').join(sql.Placeholder() for _ in values)
                )
                
                cursor.execute(insert_query, values)
                conn.commit()
                return cursor.fetchone()

            elif http_method == HTTPMethod.GET:
                filters = [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in combined_params.keys()]
                values = list(combined_params.values())
                where_clause = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(filters)) if filters else sql.SQL("")

                query = sql.SQL("SELECT * FROM {table} {where_clause}").format(
                    table=schema_table_name,
                    where_clause=where_clause
                )
                
                cursor.execute(query, values)
                results = cursor.fetchall()

                if not results:
                    raise HTTPException(status_code=404, detail="No records found")
                return results if len(results) > 1 else results[0]

            elif http_method == HTTPMethod.PUT:
                if not body_params:
                    raise HTTPException(status_code=400, detail="No data provided for PUT operation.")
                if not path_params:
                    raise HTTPException(status_code=400, detail="No parameters provided for PUT operation.")

                updates = [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in body_params.keys()]
                filters = [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in path_params.keys()]
                
                values = list(body_params.values()) + list(path_params.values())

                update_query = sql.SQL(
                    "UPDATE {table} SET {updates} WHERE {filters} RETURNING *"
                ).format(
                    table=schema_table_name,
                    updates=sql.SQL(", ").join(updates),
                    filters=sql.SQL(" AND ").join(filters)
                )

                cursor.execute(update_query, values)
                conn.commit()
                result = cursor.fetchall()
                if not result:
                    raise HTTPException(status_code=404, detail="No records found to update.")
                
                return result[0]

            elif http_method == HTTPMethod.DELETE:
                filters = [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in combined_params.keys()]
                values = list(combined_params.values())
                
                where_clause = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(filters)) if filters else sql.SQL("")

                delete_query = sql.SQL(
                    "DELETE FROM {table} {where_clause} RETURNING 1"
                ).format(
                    table=schema_table_name,
                    where_clause=where_clause
                )

                cursor.execute(delete_query, values)
                conn.commit()
                deleted_records = cursor.fetchall()
                results = len(deleted_records)

                if results == 0:
                    raise HTTPException(status_code=404, detail="No records found to delete.")
                
                return {"deleted_count": results, "message": f"{results} records deleted successfully"}

            else:
                raise HTTPException(status_code=400, detail="Unsupported HTTP method")

    except DatabaseError as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        if conn:
            release_db_connection(conn)
