import yaml
from fastapi import (
    FastAPI,
    HTTPException
)
import copy
from openapi_server.main import app

def load_existing_openapi(file_path: str) -> dict:
    try:
        with open(file_path, 'r') as openapi_file:
            existing_openapi = yaml.load(openapi_file, Loader=yaml.CLoader)
        return existing_openapi
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Existing OpenAPI file not found.")

def generate_new_openapi(app: FastAPI) -> dict:
    return app.openapi()

def find_and_apply_updates(new_openapi: dict, existing_openapi: dict) -> dict:
    merged_openapi = copy.deepcopy(existing_openapi)
    for field in ["openapi", "info", "servers"]:
        if field in new_openapi:
            merged_openapi[field] = merge_with_extensions(existing_openapi.get(field, {}), new_openapi[field])
    merged_openapi["security"] = new_openapi.get("security", merged_openapi.pop("security", None))
    if "paths" in new_openapi:
        merged_openapi["paths"] = merge_paths(new_openapi.get("paths", {}), merged_openapi.get("paths", {}))
    if "components" in new_openapi:
        merged_openapi["components"] = merge_components(merged_openapi.get("components", {}), new_openapi["components"])
    clean_removed_keys(new_openapi, merged_openapi)
    return merged_openapi

def merge_with_extensions(existing_item, new_item):
    if isinstance(existing_item, dict) and isinstance(new_item, dict):
        merged = {**new_item}
        merged.update({k: v for k, v in existing_item.items() if k.startswith("x-") and k not in merged})
        return merged
    return new_item

def merge_paths(new_paths: dict, existing_paths: dict) -> dict:
    methods = ['get', 'post', 'put', 'delete', 'options', 'head', 'patch', 'trace']
    for path, new_item in new_paths.items():
        existing_item = existing_paths.get(path, {})
        merged_item = merge_with_extensions(existing_item, new_item)
        for method in methods:
            existing_op = existing_item.get(method)
            new_op = new_item.get(method)
            if existing_op and new_op:
                merged_op = merge_with_extensions(existing_op, new_op)
                merge_operation(merged_op, existing_op, new_op)
                merged_item[method] = merged_op
            elif new_op:
                merged_item[method] = new_op
            elif existing_op:
                merged_item[method] = existing_op
        existing_paths[path] = merged_item
    return existing_paths

def merge_operation(merged_op: dict, existing_op: dict, new_op: dict):
    merged_op.update({k: v for k, v in new_op.items() if not k.startswith("x-")})
    merge_responses(merged_op, existing_op.get("responses", {}), new_op.get("responses", {}))
    merge_parameters(merged_op, existing_op.get("parameters", []), new_op.get("parameters", []))
    merge_security(merged_op, existing_op.get("security", []), new_op.get("security", []))

def merge_responses(merged_op: dict, existing_responses: dict, new_responses: dict):
    merged_op["responses"] = merge_dicts(existing_responses, new_responses, merge_with_extensions)

def merge_parameters(merged_op: dict, existing_params: list, new_params: list):
    merged_params = merge_lists_by_name(existing_params, new_params, merge_with_extensions)
    if merged_params:
        merged_op["parameters"] = merged_params
    else:
        merged_op.pop("parameters", None)

def merge_security(merged_op: dict, existing_security: list, new_security: list):
    new_set = {listed_security_requirement(s) for s in new_security}
    merged_security = new_security + [s for s in existing_security if listed_security_requirement(s) not in new_set]
    if merged_security:
        merged_op["security"] = merged_security
    else:
        merged_op.pop("security", None)

def merge_components(existing_components: dict, new_components: dict) -> dict:
    merged_components = copy.deepcopy(existing_components)
    for key in ["schemas", "parameters", "securitySchemes"]:
        existing_items = existing_components.get(key, {})
        new_items = new_components.get(key, {})
        if new_items:
            if key == "schemas":
                function_to_use = merge_schemas
            else:
                function_to_use = merge_with_extensions
            merged_components[key] = merge_dicts(existing_items, new_items, function_to_use)
    return merged_components

def merge_schemas(existing_schema: dict, new_schema: dict) -> dict:
    merged_schema = merge_with_extensions(existing_schema, new_schema)
    existing_props = existing_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    if new_props or existing_props:
        merged_schema["properties"] = merge_dicts(existing_props, new_props, merge_with_extensions)
    return merged_schema

def merge_dicts(existing: dict, new: dict, merge_func):
    return {
        key: merge_func(existing.get(key, {}), new.get(key, {}))
        for key in set(existing) | set(new)
    }

def merge_lists_by_name(existing_list: list, new_list: list, merge_func):
    existing_dict = {item['name']: item for item in existing_list if 'name' in item}
    new_dict = {item['name']: item for item in new_list if 'name' in item}
    names = set(existing_dict) | set(new_dict)
    return [
        merge_func(existing_dict.get(name, {}), new_dict.get(name, {}))
        for name in names
    ]

def clean_removed_keys(new_openapi: dict, merged_openapi: dict):
    merged_paths = merged_openapi.get("paths", {})
    new_paths = new_openapi.get("paths", {})
    for path in list(merged_paths):
        if path not in new_paths:
            del merged_paths[path]
        else:
            clean_operations(new_paths[path], merged_paths[path])
    if "components" in merged_openapi:
        clean_components(merged_openapi.get("components", {}), new_openapi.get("components", {}))

def clean_operations(new_ops: dict, existing_ops: dict):
    methods = ['get', 'post', 'put', 'delete', 'options', 'head', 'patch', 'trace']
    for method in methods:
        if method in existing_ops:
            if method not in new_ops:
                del existing_ops[method]
            else:
                clean_responses(new_ops[method], existing_ops[method])
                clean_parameters(new_ops[method], existing_ops[method])
                clean_security(new_ops[method], existing_ops[method])

def clean_responses(new_op: dict, existing_op: dict):
    existing_responses = existing_op.get("responses", {})
    new_responses = new_op.get("responses", {})
    for code in list(existing_responses):
        if code not in new_responses:
            del existing_responses[code]

def clean_parameters(new_op: dict, existing_op: dict):
    new_params = {
        param.get('name') or param.get('$ref')
        for param in new_op.get("parameters", [])
        if 'name' in param or '$ref' in param
    }
    existing_params = existing_op.get("parameters", [])
    existing_op["parameters"] = [
        param for param in existing_params
        if ('name' in param and param['name'] in new_params) or
           ('$ref' in param and param['$ref'] in new_params)
    ]
    if not existing_op["parameters"]:
        existing_op.pop("parameters", None)

def clean_security(new_op: dict, existing_op: dict):
    new_security = new_op.get("security", [])
    existing_security = existing_op.get("security", [])
    new_set = {listed_security_requirement(s) for s in new_security}
    existing_op["security"] = [s for s in existing_security if listed_security_requirement(s) in new_set]
    if not existing_op["security"]:
        existing_op.pop("security", None)

def clean_components(existing_components: dict, new_components: dict):
    for key in ["schemas", "parameters", "securitySchemes"]:
        existing_items = existing_components.get(key, {})
        new_items = new_components.get(key, {})
        for item in list(existing_items):
            if item not in new_items:
                del existing_items[item]
            elif key == "schemas":
                clean_schema_properties(existing_items[item], new_items[item])

def clean_schema_properties(existing_schema: dict, new_schema: dict):
    existing_props = existing_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    existing_schema["properties"] = {k: v for k, v in existing_props.items() if k in new_props}
    if not existing_schema["properties"]:
        existing_schema.pop("properties", None)

def listed_security_requirement(scheme):
        return frozenset((k, tuple(v)) for k, v in scheme.items())

def save_openapi(file_path: str, openapi_data: dict):
    with open(file_path, 'w') as openapi_file:
        yaml.dump(openapi_data, openapi_file, Dumper=yaml.CDumper)

def main():    
    existing_file = './openapi.yaml'
    output_file = './regenerated-openapi.yaml'
    try:
        new_openapi = generate_new_openapi(app)
        existing_openapi = load_existing_openapi(existing_file)
        updated_openapi = find_and_apply_updates(new_openapi, existing_openapi)
        save_openapi(output_file, updated_openapi)
    except Exception as e:
        print(e)
        exit
    print(f"OpenAPI schema saved to {output_file}")

if __name__ == "__main__":
    main()