from typing import Optional, Dict, List
import json
import validations
import sqlite3
from sqlite3 import OperationalError
from typing import Optional, Dict


""" Shani Strauss 
jjj
lll

2222 """

def is_valid_engineName(engine_name: str) -> bool:
    """Check if the engineName is valid."""
    valid_engine_names = {
        "db2-ae", "db2-se", "mariadb", "mysql", "oracle-ee",
        "oracle-ee-cdb", "oracle-se2", "oracle-se2-cdb",
        "postgres", "sqlserver-ee", "sqlserver-se",
        "sqlserver-ex", "sqlserver-web"
    }

    return validations.string_in_dict(engine_name, valid_engine_names)

def is_valid_optionGroupName(option_group_name: str) -> bool:
    """
    Check if the optionGroupName is valid based on the pattern and length.

    The optionGroupName must:
    - Be between 1 and 255 characters in length.
    - Start with a letter.
    - Contain only letters, digits, or hyphens.
    - Not contain two consecutive hyphens.
    - End with a letter or digit.

    Args:
        option_group_name (str): The name of the option group to validate.

    Returns:
        bool: True if the optionGroupName is valid, False otherwise.
    """
    pattern = r'^[a-zA-Z](?!.*--)[a-zA-Z0-9-]{0,253}[a-zA-Z0-9]$'
    return validations.is_valid_length(option_group_name, 1, 255) and validations.is_valid_pattern(option_group_name, pattern)

def option_group_exists(conn: sqlite3.Connection, option_group_name: str) -> bool:
    """Check if an option group with the given name already exists."""
    return validations.exist_key_value_in_json_column(conn, "object_management", "metadata", "optionGroupName", option_group_name)

def get_option_group_count(conn: sqlite3.Connection) -> int:
    """Get the number of option groups in the table."""
    c = conn.cursor()
    c.execute('''
    SELECT COUNT(*) FROM object_management
    WHERE type_object = 'OptionGroup'
    ''')
    return c.fetchone()[0]

def insert_new_option_group_to_object_management_table(
    conn: sqlite3.Connection,
    engine_name: str, 
    major_engine_version: str, 
    option_group_description: str, 
    option_group_name: str, 
    tags: Optional[Dict] = None
) -> None:
    """Insert a new option group into the object_management table."""

    metadata_dict = {
        "engineName": engine_name,
        "majorEngineVersion": major_engine_version,
        "optionGroupDescription": option_group_description,
        "optionGroupName": option_group_name,
        "available": 'True'
    }
    
    if tags is not None:
        metadata_dict["tags"] = tags
    
    metadata = json.dumps(metadata_dict)
    
    try:
        c = conn.cursor()
        c.execute('''
        INSERT INTO object_management (type_object, metadata)
        VALUES (?, ?)
        ''', ('OptionGroup', metadata))

        conn.commit()
    except OperationalError as e:
        print(f"Error: {e}")
    
def is_option_group_available(conn: sqlite3.Connection, option_group_name: str) -> bool:
    """Check if an option group with the specified name and availability status exists."""
    c = conn.cursor()
    c.execute('''
    SELECT metadata FROM object_management
    WHERE type_object = 'OptionGroup'
    ''')
    
    rows = c.fetchall()
    for row in rows:
        metadata = json.loads(row[0])
        if (metadata.get("optionGroupName") == option_group_name and 
                metadata.get("available") == 'True'):
            return True
    
    return False

def delete_option_group_from_object_management_table(conn: sqlite3.Connection, option_group_name: str) -> None:
    """Delete option group from object management table."""
    try:
        c = conn.cursor()
        c.execute(f'''
        DELETE FROM object_management
        WHERE type_object = ? AND metadata LIKE ?
        ''', ('OptionGroup', f'%"OptionGroupName": "{option_group_name}"%',))

        conn.commit()
    except OperationalError as e:
        print(f"Error: {e}")

def delete_option_group_name_from_DBInstance_metadata(conn: sqlite3.Connection, option_group_name: str) -> None:
    """Delete the 'optionGroupName' key and its value from metadata where type_object is 'DBInstance' and the value equals option_group_name."""
    try:
        c = conn.cursor()
        c.execute('''
        SELECT object_id, metadata FROM object_management 
        WHERE type_object = ?
        ''', ('DBInstance',))
        
        rows = c.fetchall()
        
        for row in rows:
            object_id = row[0]
            metadata = json.loads(row[1])
            
            if 'optionGroupName' in metadata and metadata['optionGroupName'] == option_group_name:
                del metadata['optionGroupName']
                updated_metadata = json.dumps(metadata)
                
                c.execute('''
                UPDATE object_management 
                SET metadata = ?
                WHERE object_id = ?
                ''', (updated_metadata, object_id))
        
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")

def CreateOptionGroup(
    conn: sqlite3.Connection,
    engine_name: str, 
    major_engine_version: str, 
    option_group_description: str, 
    option_group_name: str,
    tags: Optional[Dict] = None
) -> str:
    """Create a new option group and insert it into the object_management table."""
    if not is_valid_engineName(engine_name):
        raise ValueError(f"Invalid engineName: {engine_name}")
    if not is_valid_optionGroupName(option_group_name):
        raise ValueError(f"Invalid optionGroupName: {option_group_name}")
    
    if option_group_exists(conn, option_group_name):
        return {
            "Error": {
                "Code": "OptionGroupAlreadyExistsFault",
                "Message": f"Option group '{option_group_name}' already exists.",
                "HTTPStatusCode": 400
            }
        }
    if get_option_group_count(conn) >= 20:
        return {
            "Error": {
                "Code": "OptionGroupQuotaExceededFault",
                "Message": f"Quota of 20 option groups exceeded for this AWS account.",
                "HTTPStatusCode": 400
            }
        }
    

    try:
        insert_new_option_group_to_object_management_table(
            conn, engine_name, major_engine_version, option_group_description, option_group_name, tags
        )
        return{
            "CreateOptionGroupResponse": {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                }
            }
        }
    except OperationalError as e:
        return {
            "Error": {
                "Code": "InternalError",
                "Message": f"An internal error occurred: {str(e)}",
                "HTTPStatusCode": 500
            }
        }

def DeleteOptionGroup(conn: sqlite3.Connection, option_group_name: str) -> str:
    """
    Deletes an existing option group.
    The function checks if the option group exists and if it is in the 'available' state.
    If the option group does not exist or is not available, the function returns an appropriate error message in JSON format.
    If the option group is successfully deleted, the function returns a success response in JSON format.
    """
    if not option_group_exists(conn, option_group_name):
        return {
            "Error": {
                "Code": "OptionGroupNotFoundFault",
                "Message": f"The specified option group '{option_group_name}' could not be found.",
                "HTTPStatusCode": 404
            }
        }

    if not is_option_group_available(conn, option_group_name):
        return {
            "Error": {
                "Code": "InvalidOptionGroupStateFault",
                "Message": f"The option group '{option_group_name}' isn't in the available state.",
                "HTTPStatusCode": 400
            }
        }
    try:
        delete_option_group_name_from_DBInstance_metadata(conn, option_group_name)
        delete_option_group_from_object_management_table(conn, option_group_name)
        return{
            "DeleteOptionGroupResponse": {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                }
            }
        }
    except OperationalError as e:
        return {
            "Error": {
                "Code": "InternalError",
                "Message": f"An internal error occurred: {str(e)}",
                "HTTPStatusCode": 500
            }
        }

def ModifyOptionGroup(
    conn: sqlite3.Connection, 
    option_group_name: str,
    apply_immediately: bool = False,
    options_to_include: Optional[List[Dict]] = None,
    options_to_remove: Optional[List[str]] = None
) -> str:
    """Modify Option Group."""
    if not option_group_exists(conn, option_group_name):
        return {
            "Error": {
                "Code": "OptionGroupNotFoundFault",
                "Message": f"The specified option group '{option_group_name}' could not be found.",
                "HTTPStatusCode": 404
            }
        }

    if not is_option_group_available(conn, option_group_name):
        return {
            "Error": {
                "Code": "InvalidOptionGroupStateFault",
                "Message": f"The option group '{option_group_name}' isn't in the available state.",
                "HTTPStatusCode": 400
            }
        }

    try:
        c = conn.cursor()
        c.execute('''
        SELECT object_id, metadata FROM object_management 
        WHERE type_object = 'OptionGroup' AND metadata LIKE ?
        ''', (f'%"optionGroupName": "{option_group_name}"%',))
        
        row = c.fetchone()
        if not row:
            return {
                "Error": {
                    "Code": "OptionGroupNotFoundFault",
                    "Message": f"The specified option group '{option_group_name}' could not be found.",
                    "HTTPStatusCode": 404
                }
            }

        object_id = row[0]
        metadata = json.loads(row[1])

        current_options = metadata.get("options", [])

        if options_to_include:
            for option in options_to_include:
                current_options = [opt for opt in current_options if opt["option_name"] != option["option_name"]]
                current_options.append(option)

        if options_to_remove:
            current_options = [opt for opt in current_options if opt["option_name"] not in options_to_remove]

        metadata["options"] = current_options
        metadata["apply_immediately"] = apply_immediately

        updated_metadata = json.dumps(metadata)

        c.execute('''
        UPDATE object_management 
        SET metadata = ?
        WHERE object_id = ?
        ''', (updated_metadata, object_id))

        conn.commit()
        
        return {
            "ModifyOptionGroupResponse": {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                }
            }
        }
    except OperationalError as e:
        return {
            "Error": {
                "Code": "InternalError",
                "Message": f"An internal error occurred: {str(e)}",
                "HTTPStatusCode": 500
            }
        }
    
def CopyOptionGroup(
        conn: sqlite3.Connection,
        source_option_group_identifier: str,
        target_option_group_description: str,
        target_option_group_identifier: str,
        tags: Optional[Dict] = None
    ) -> str:
    """Copy an existing option group and insert it into the object_management table."""
    if not is_valid_optionGroupName(target_option_group_identifier):
        raise ValueError(f"Invalid optionGroupName: {target_option_group_identifier}")
    
    if option_group_exists(conn, target_option_group_identifier):
        return {
            "Error": {
                "Code": "OptionGroupAlreadyExistsFault",
                "Message": f"Option group '{target_option_group_identifier}' already exists.",
                "HTTPStatusCode": 400
            }
        }
    if not option_group_exists(conn, source_option_group_identifier):
        return {
            "Error": {
                "Code": "OptionGroupNotFoundFault",
                "Message": f"The specified option group '{source_option_group_identifier}' could not be found.",
                "HTTPStatusCode": 404
            }
        }
    if get_option_group_count(conn) >= 20:
        return {
            "Error": {
                "Code": "OptionGroupQuotaExceededFault",
                "Message": f"Quota of 20 option groups exceeded for this AWS account.",
                "HTTPStatusCode": 400
            }
        }

    try:
        c = conn.cursor()
        c.execute('''
        SELECT metadata FROM object_management 
        WHERE type_object = 'OptionGroup' AND metadata LIKE ?
        ''', (f'%"optionGroupName": "{source_option_group_identifier}"%',))

        row = c.fetchone()
        if not row:
            return {
                "Error": {
                    "Code": "OptionGroupNotFoundFault",
                    "Message": f"The specified option group '{source_option_group_identifier}' could not be found.",
                    "HTTPStatusCode": 404
                }
            }

        source_metadata = json.loads(row[0])
        target_metadata = source_metadata.copy()
        target_metadata["optionGroupName"] = target_option_group_identifier
        target_metadata["optionGroupDescription"] = target_option_group_description
        
        if tags is not None:
            target_metadata["tags"] = tags

        target_metadata = json.dumps(target_metadata)

        c.execute('''
        INSERT INTO object_management (type_object, metadata)
        VALUES (?, ?)
        ''', ('OptionGroup', target_metadata))

        conn.commit()

        return {
            "CopyOptionGroupResponse": {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                }
            }
        }
    except OperationalError as e:
        return {
            "Error": {
                "Code": "InternalError",
                "Message": f"An internal error occurred: {str(e)}",
                "HTTPStatusCode": 500
            }
        }

def DescribeOptionGroups(
    conn: sqlite3.Connection,
    engine_name: Optional[str] = None,
    major_engine_version: Optional[str] = None,
    marker: Optional[str] = None,
    max_records: int = 100,
    option_group_name: Optional[str] = None
) -> dict:
    """
    Describe the available option groups.
    
    :param conn: SQLite connection object
    :param engine_name: Filter to include option groups associated with this database engine
    :param major_engine_version: Filter to include option groups associated with this database engine version
    :param marker: Pagination token from a previous request
    :param max_records: Maximum number of records to include in the response (default 100, min 20, max 100)
    :param option_group_name: Name of the option group to describe
    :return: Dictionary containing the list of option groups and an optional pagination marker
    """
    if not is_valid_engineName(engine_name):
        raise ValueError(f"Invalid engineName: {engine_name}")
    if not validations.is_valid_number(max_records, 20, 100):
        raise ValueError(f"Invalid max_records: {max_records}. max_records must be between 20 to 100.")
    if option_group_name is not None:
        if not option_group_exists(conn, option_group_name):
            return {
            "Error": {
                "Code": "OptionGroupNotFoundFault",
                "Message": f"The specified option group '{option_group_name}' could not be found.",
                "HTTPStatusCode": 404
            }
        }
    
    query = '''
    SELECT object_id, metadata FROM object_management 
    WHERE type_object = 'OptionGroup'
    '''
    params = []

    if option_group_name:
        query += ' AND metadata LIKE ?'
        params.append(f'%"{option_group_name}"%')
    else:
        if engine_name:
            query += ' AND metadata LIKE ?'
            params.append(f'%"{engine_name}"%')
            if major_engine_version:
                query += ' AND metadata LIKE ?'
                params.append(f'%"{major_engine_version}"%')

    query += ' ORDER BY object_id LIMIT ? OFFSET ?'
    offset = int(marker) if marker else 0
    params.append(max_records)
    params.append(offset)

    try:
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()

        option_groups_list = []
        for row in rows:
            metadata = json.loads(row[1])
            option_groups_list.append(metadata)

        next_marker = offset + max_records if len(rows) == max_records else None

        return {
            "DescribeOptionGroupsResponse": {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                },
                "OptionGroupsList": option_groups_list,
                "Marker": next_marker
            }
        }
    except OperationalError as e:
        return {
            "Error": {
                "Code": "InternalError",
                "Message": f"An internal error occurred: {str(e)}",
                "HTTPStatusCode": 500
            }
        }
    
def DescribeOptionGroupOptions(
    conn: sqlite3.Connection,
    engine_name: str,
    major_engine_version: Optional[str] = None,
    marker: Optional[str] = None,
    max_records: int = 100
) -> dict:
    """Describes all available options for the specified engine."""
    if not engine_name:
        raise ValueError("Engine name is required.")
    if not is_valid_engineName(engine_name):
        raise ValueError(f"Invalid engineName: {engine_name}")
    if not validations.is_valid_number(max_records, 20, 100):
        raise ValueError(f"Invalid max_records: {max_records}. max_records must be between 20 to 100.")

    try:
        c = conn.cursor()
        query = '''
        SELECT metadata FROM object_management 
        WHERE type_object = 'OptionGroup' AND metadata LIKE ?
        '''
        params = [f'%"engineName": "{engine_name}"%']
        
        if major_engine_version:
            query += ' AND metadata LIKE ?'
            params.append(f'%"majorEngineVersion": "{major_engine_version}"%')
        
        c.execute(query, params)
        
        rows = c.fetchall()
        options = [json.loads(row[0]) for row in rows]

        if marker:
            options = options[int(marker):]
        
        response_options = options[:max_records]
        next_marker = str(max_records) if len(options) > max_records else None
        
        return {
            "DescribeOptionGroupOptionsResponse": {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                },
                "Marker": next_marker,
                "OptionGroupOptions": response_options
            }
        }
    
    except OperationalError as e:
        return {
            "Error": {
                "Code": "InternalError",
                "Message": f"An internal error occurred: {str(e)}",
                "HTTPStatusCode": 500
            }
        }

