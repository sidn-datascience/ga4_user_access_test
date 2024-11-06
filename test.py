from googleapiclient.discovery import build, Resource
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_FILE = './service_account.json'
API_NAME = "analyticsadmin"
API_VERSION = "v1alpha"
SCOPES = [
    'https://www.googleapis.com/auth/analytics.manage.users',
]
ACCEPTED_ENTITY_TYPES = [
    "account",
    "property"
]
ACCEPTED_OPERATION_TYPES = [
    "create",
    "update", # includes deletion
    "list"
]
ACCEPTED_ROLES = [
    'predefinedRoles/admin',
    'predefinedRoles/editor',
    'predefinedRoles/analyst',
    'predefinedRoles/viewer',
    'predefinedRoles/no-cost-data',
    'predefinedRoles/no-revenue-data'
]

def get_credentials(service_account_file:str, scopes:list[str]) -> Credentials:
    """Retrieves Google API credentials from a service account file.

    Args:
        service_account_file (str): Path to the service account JSON key file.
        scopes (list[str]): List of OAuth 2.0 scopes to request.

    Returns:
        Credentials: A Google API credentials object.

    Raises:
        google.oauth2.service_account.CredentialsError: If there's an error
            loading the credentials from the file or the scopes are invalid.
    """
    creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    return creds

def prepare_accessBindings_service(entity_type:str, roles:list[str], operation_type:str) -> tuple[Resource,str]:
    """Prepares the service object and resource name for accessBindings operations.

    This function validates user-provided inputs and builds the appropriate service object and resource name
    for interacting with Google Cloud Access Control (IAM) based on the specified entity type and operation.

    Args:
        entity_type (str): The type of entity for which access bindings are being managed.
            Must be one of: `, `.join(ACCEPTED_ENTITY_TYPES)
        roles (list[str]): A list of roles to be assigned or checked (depending on operation).
            Each role must be among: `, `.join(ACCEPTED_ROLES)
        operation_type (str): The operation to perform on access bindings.
            Must be one of: `, `.join(ACCEPTED_OPERATION_TYPES)

    Returns:
        tuple[Resource, str]: A tuple containing the prepared service object and the resource name.

    Raises:
        Exception: If the provided entity_type, roles, or operation_type is invalid.
    """
    # Input checks
    if entity_type not in ACCEPTED_ENTITY_TYPES:
        raise Exception("The entity_type must be one of: "+', '.join(ACCEPTED_ENTITY_TYPES))
    if next((role for role in roles if role not in ACCEPTED_ROLES), False):
        raise Exception("Invalid roles. Must be among: "+', '.join(ACCEPTED_ROLES))
    if operation_type not in ACCEPTED_OPERATION_TYPES:
        raise Exception("The operation_type must be one of: "+', '.join(ACCEPTED_OPERATION_TYPES))
    
    # Retrieving credentials and building the service
    creds = get_credentials(SERVICE_ACCOUNT_FILE, SCOPES)
    service = build(API_NAME, API_VERSION, credentials=creds)

    # Preparing the service and resource_name based on entity_type
    if entity_type == 'account':
        service = service.accounts().accessBindings()
        resource_name = "accounts"
    elif entity_type == 'property':
        service = service.properties().accessBindings()
        resource_name = "properties"

    # Preparing the service based on operation_type
    if operation_type == 'create':
        service = service.create
    elif operation_type == 'delete':
        service = service.delete
    elif operation_type == 'update':
        service = service.patch
    elif operation_type == 'list':
        service = service.list

    return service, resource_name

def create_new_user_access(entity_type:str, entity_id:str, email:str, roles:list[str]) -> dict:
    """Creates a new user access binding for a specified entity.

    This function prepares the necessary service object and resource name, then creates a new access binding
    for the given entity, assigning the specified roles to the provided email address.

    Args:
        entity_type (str): The type of entity (e.g., 'account', 'property').
        entity_id (str): The ID of the entity.
        email (str): The email address of the user to grant access to.
        roles (list[str]): A list of roles to assign to the user.

    Returns:
        dict: The API response from the Google Analytics 4 Admin API call.

    Raises:
        Exception: If there's an error preparing the service or executing the API call.
    """
    operation, resource_name = prepare_accessBindings_service(entity_type, roles, 'create')
    response = operation(
        parent=f"{resource_name}/{entity_id}",
        body={
            "roles": roles,
            "user":email
        }
    ).execute()

    return response

def get_user_access_by_email(entity_type:str, entity_id:str, email:str) -> dict:
    """Retrieves the access binding for a specific user on a given entity.

    This function lists all access bindings for the specified entity and filters them to find the one associated with the given email address.

    Args:
        entity_type (str): The type of entity (e.g., 'account', 'property').
        entity_id (str): The ID of the entity.
        email (str): The email address of the user to find.

    Returns:
        dict: The access binding information for the specified user.

    Raises:
        StopIteration: If no access binding is found for the given email.
        Exception: If there's an error preparing the service or executing the API call.
    """
    operation, resource_name = prepare_accessBindings_service(entity_type, [], 'list')
    response = operation(
        parent=f"{resource_name}/{entity_id}",
    ).execute()

    return next((accessBinding for accessBinding in response['accessBindings'] if accessBinding['user']==email))

def update_user_access(entity_type:str, entity_id:str, email:str, roles:list[str]) -> dict:
    """Updates a user's access to a specified entity.

    This function retrieves the existing access binding for the given user and entity,
    then updates the roles associated with that binding.

    Args:
        entity_type (str): The type of entity (e.g., 'account', 'property').
        entity_id (str): The ID of the entity.
        email (str): The email address of the user to update access for.
        roles (list[str]): A list of roles to assign to the user.

    Returns:
        dict: The API response from the Google Analytics 4 Admin API call.

    Raises:
        Exception: If there's an error retrieving the access binding, preparing the service, or executing the API call.
    """
    accessBinding = get_user_access_by_email(entity_type, entity_id, email)
    operation, _ = prepare_accessBindings_service(entity_type, roles, 'update')
    response = operation(
        name=accessBinding['name'],
        body={
            "name": accessBinding['name'],
            "roles": roles,
            "user": email
        }
    ).execute()

    return response

def delete_user_access(entity_type:str, entity_id:str, email:str) -> dict:
    """Deletes a user's access to a specified entity.

    This function updates the access binding for the given entity, removing the specified user's roles.
    Effectively, this deletes the user's access to the entity.

    Args:
        entity_type (str): The type of entity (e.g., 'account', 'property').
        entity_id (str): The ID of the entity.
        email (str): The email address of the user to remove access for.

    Returns:
        dict: The API response from the Google Analytics 4 Admin API call.

    Raises:
        Exception: If there's an error preparing the service or executing the API call.
    """
    return update_user_access(entity_type, entity_id, email, [])